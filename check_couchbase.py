#!/usr/bin/python

"""Hello world Nagios check."""

import nagiosplugin
import requests
import argparse

class CBBucketGet(nagiosplugin.Context):
    def evaluate(self, metric, resource):
        cmd_get = metric.value['cmd_get'].pop()
        hit_ratio = metric.value['hit_ratio'].pop()
        if cmd_get < 30:
            if hit_ratio < 0.7:
                return self.result_cls(nagiosplugin.state.Warn, "hit ratio low")
        return self.result_cls(nagiosplugin.state.Ok, "hit ratio ok or not enough request to measure")
    def performance(self, metric, resource):
        return self.result_cls(nagiosplugin.Performance('hit_ratio', metric.value['hit_ratio'].pop()))

class CBNodeStatus(nagiosplugin.Context):
    def evaluate(self, metric, resource):
        count = 0
        nodes = []
        for node in metric.value:
            if node['status'] == 'unhealthy':
                nodes.append(node['hostname'])
                count = count + 1
        if count == 0:
            return self.result_cls(nagiosplugin.state.Ok, "All nodes healthy")
        else:    
            return self.result_cls(nagiosplugin.state.Critical, "Unhealthy nodes: %s" % ("; ".join(nodes)))

class CouchBaseAlerts(nagiosplugin.Context):
    def evaluate(self, metric, resource):
        alerts = metric.value
        if len(alerts) == 0:
            return self.result_cls(nagiosplugin.state.Ok, "No alerts")
        else:    
            return self.result_cls(nagiosplugin.state.Warn, "Active alerts: %s" % (";".join(alerts)))


class Cluster(nagiosplugin.Resource):
    def __init__(self, data):
 
        self.data = data

    def probe(self):
        ramratio = ( self.data['storageTotals']['ram']['used'] ) * 1.00 / self.data['storageTotals']['ram']['total']  * 100.00
        quotaratio = ( self.data['storageTotals']['ram']['quotaUsed'] ) * 1.00 / self.data['storageTotals']['ram']['quotaTotal']  * 100.00
        diskratio = ( self.data['storageTotals']['hdd']['used'] ) * 1.00 / self.data['storageTotals']['ram']['total']  * 100.00
        yield nagiosplugin.Metric('alerts', self.data['alerts'])
        yield nagiosplugin.Metric('nodes', self.data['nodes'])
        yield nagiosplugin.Metric('ramratio', ramratio)       
        yield nagiosplugin.Metric('quotaratio', quotaratio)
        yield nagiosplugin.Metric('diskratio', diskratio)         

class Bucket(nagiosplugin.Resource):
    def __init__(self, data):
 
        self.data = data

    def probe(self):
#print data['op']['samples']['mem_used'].pop()
#print data['op']['samples']['ep_mem_low_wat'].pop()
        samples = self.data['op']['samples']
        low_wat = ( samples['mem_used'].pop() ) * 1.00 / samples['ep_mem_low_wat'].pop()  * 100
        high_wat = ( samples['mem_used'].pop() ) * 1.00 / samples['ep_mem_high_wat'].pop()  * 100
        yield nagiosplugin.Metric('low_wat', low_wat)       
        yield nagiosplugin.Metric('low_wat', high_wat)
        yield nagiosplugin.Metric('get', samples)


def main():
    argp = argparse.ArgumentParser()
    argp.add_argument('-H', '--host', help="host to connect to", default='couchbase-qs-1.mm.br.de')
    argp.add_argument('-p', '--port', help="port to connect to", default='8091')
    argp.add_argument("-U", "--user", help="username for authentication", default='nagios')
    argp.add_argument("-P", "--password", dest="password", 
                      help="password for authentication", default='nagios')
    argp.add_argument("-b", "--bucket", dest="bucket", 
                      help="couchbase bucket name")
    argp.add_argument("--ramratio_w", help="ram ratio warning", default='60')
    argp.add_argument("--ramratio_c", help="ram ratio critical", default='80')
    argp.add_argument("--quotaratio_w", help="quota ratio warning", default='60')
    argp.add_argument("--quotaratio_c", help="quota ratio critical", default='80')
    argp.add_argument("--diskratio_w", help="disk ratio warning", default='60')
    argp.add_argument("--diskratio_c",  help="d ratio critical", default='80')

    
    args = argp.parse_args()
    if args.bucket == None: 
        r = requests.get("http://%s:%s/pools/default" % (args.host, args.port),
                         auth=(args.user, args.password))
        if r.status_code != 200:
            raise RuntimeError
        data = r.json()
        print data['alerts']
        check = nagiosplugin.Check( Cluster(data) )
        check.add(nagiosplugin.ScalarContext("ramratio", args.ramratio_w, args.ramratio_c, fmt_metric='{value}% total memory usage '))
        check.add(nagiosplugin.ScalarContext("quotaratio", args.quotaratio_w, args.quotaratio_c, fmt_metric='{value}% quota memory usage '))
        check.add(nagiosplugin.ScalarContext("diskratio", args.diskratio_w, args.diskratio_c, fmt_metric='{value}% quota memory usage '))       
        check.add(CouchBaseAlerts('alerts'))
        check.add(CBNodeStatus('nodes'))
        check.main()
    else:
        r = requests.get("http://%s:%s/pools/default/buckets/%s/stats" % (args.host, args.port, args.bucket),
                         auth=(args.user, args.password))
        if r.status_code != 200:
            raise RuntimeError
        data = r.json()
        check = nagiosplugin.Check( Bucket(data) )
        check.add(nagiosplugin.ScalarContext("low_wat", 80, 90, fmt_metric='{value}%  of low watermark reached'))
        check.add(nagiosplugin.ScalarContext("high_wat", 50, 70, fmt_metric='{value}%  of high watermark reached'))
        check.add(CBBucketGet('get'))
        check.main()
        
        #print data['op']['samples']['mem_used'].pop()
        #print data['op']['samples']['ep_mem_low_wat'].pop()
        #print data['op']['samples']['ep_mem_high_wat'].pop()
        #print data['op']['samples']['ep_flusher_todo'].pop()
        #print data['op']['samples']['get_misses'].pop()
        #print data['op']['samples']['hit_ratio'].pop()
        #print data['op']['samples']['evictions'].pop()
        
        
        

if __name__ == '__main__':
    main()
        
        
    