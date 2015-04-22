#!/usr/bin/python

"""Hello world Nagios check."""

import nagiosplugin
import requests
import argparse
from nagiosplugin.performance import Performance


class CBBucketGet(nagiosplugin.Context):
    def performance(self, metric, resource):
        return Performance('hitratio', metric.value['hit_ratio'].pop()) 

    def evaluate(self, metric, resource):
        cmd_get = metric.value['cmd_get'].pop()
        hit_ratio = metric.value['hit_ratio'].pop()
        if cmd_get > 30:
            if hit_ratio < 0.7:
                return self.result_cls(nagiosplugin.state.Warn, "hit ratio low")
        return self.result_cls(nagiosplugin.state.Ok, "hit ratio ok or not enough request to measure")

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

class CXdcrErrors(nagiosplugin.Context):
    def evaluate(self, metric, resource):
        errors = 0
        for element in metric.value:
            if element.has_key('errors'):
                if len(element['errors']) > 0:
                    errors = errors + len(element['errors'])
        if errors == 0:
            return self.result_cls(nagiosplugin.state.Ok, "No alerts")
        else:
            return self.result_cls(nagiosplugin.state.Warn, "Found %s XDCR errors" % (errors))

class CBXdcrPaused(nagiosplugin.Context):
    def evaluate(self, metric, resource):
        paused = []
        for element in metric.value:
            if element.has_key('status'):
                if element['status'] == 'paused':
                    paused.append(element['target'])
        if len(paused) == 0:
            return self.result_cls(nagiosplugin.state.Ok, "No alerts")
        else:
            return self.result_cls(nagiosplugin.state.Warn, "Replications paused for targets: %s" % (";".join(paused)))


class Cluster(nagiosplugin.Resource):
    def __init__(self, data, tasks):
 
        self.data = data
        self.tasks = tasks

    def probe(self):
        ramratio = ( self.data['storageTotals']['ram']['used'] ) * 1.00 / self.data['storageTotals']['ram']['total']  * 100.00
        quotaratio = ( self.data['storageTotals']['ram']['quotaUsed'] ) * 1.00 / self.data['storageTotals']['ram']['quotaTotal']  * 100.00
        diskratio = ( self.data['storageTotals']['hdd']['used'] ) * 1.00 / self.data['storageTotals']['ram']['total']  * 100.00
        yield nagiosplugin.Metric('alerts', self.data['alerts'])
        yield nagiosplugin.Metric('taskerrors', self.tasks)
        yield nagiosplugin.Metric('xdcrpaused', self.tasks)
        yield nagiosplugin.Metric('nodes', self.data['nodes'])
        yield nagiosplugin.Metric('ramratio', ramratio)       
        yield nagiosplugin.Metric('quotaratio', quotaratio)
        yield nagiosplugin.Metric('diskratio', diskratio)         

class Status(nagiosplugin.Resource):
    def __init__(self, data):
 
        self.data = data

    def probe(self):
        for element in self.data:
            print element['type']
            if element.has_key('errors'):
                yield nagiosplugin.Metric('alerts', self.data['errors'])
                 

class Bucket(nagiosplugin.Resource):
    def __init__(self, data):
 
        self.data = data

    def probe(self):
        samples = self.data['op']['samples']
        low_wat = ( samples['mem_used'].pop() ) * 1.00 / samples['ep_mem_low_wat'].pop()  * 100
        high_wat = ( samples['mem_used'].pop() ) * 1.00 / samples['ep_mem_high_wat'].pop()  * 100
        yield nagiosplugin.Metric('low_wat', low_wat)       
        yield nagiosplugin.Metric('low_wat', high_wat)
        yield nagiosplugin.Metric('get', samples)


def main():
    argp = argparse.ArgumentParser()
    argp.add_argument('-H', '--host', help="host to connect to")
    argp.add_argument('-p', '--port', help="port to connect to", default='8091')
    argp.add_argument("-U", "--user", help="username for authentication")
    argp.add_argument("-P", "--password", help="password for authentication")
    argp.add_argument("-b", "--bucket",  help="couchbase bucket name")
    argp.add_argument("--ramratio_w", help="ram ratio warning", default='60')
    argp.add_argument("--ramratio_c", help="ram ratio critical", default='80')
    argp.add_argument("--quotaratio_w", help="quota ratio warning", default='60')
    argp.add_argument("--quotaratio_c", help="quota ratio critical", default='80')
    argp.add_argument("--diskratio_w", help="disk ratio warning", default='60')
    argp.add_argument("--diskratio_c",  help="d ratio critical", default='80')

    
    args = argp.parse_args()
    if args.bucket == None:
        taskurl = "http://%s:%s/pools/default/tasks" % (args.host, args.port)
        r = requests.get("http://%s:%s/pools/default" % (args.host, args.port),
                         auth=(args.user, args.password))
        if r.status_code != 200:
            print "####  HTTP Status %s ####" % (r.status_code   )
            raise RuntimeError
        data = r.json()
        r = requests.get(taskurl,
                          auth=(args.user, args.password))
        if r.status_code != 200:
            print "####  HTTP Status %s ####" % (r.status_code   )
            raise RuntimeError
        tasks = r.json()
        check = nagiosplugin.Check( Cluster(data, tasks) )
        check.add(nagiosplugin.ScalarContext("ramratio", args.ramratio_w, args.ramratio_c, fmt_metric='{value}% total memory usage'))
        check.add(nagiosplugin.ScalarContext("quotaratio", args.quotaratio_w, args.quotaratio_c, fmt_metric='{value}% quota memory usage'))
        check.add(nagiosplugin.ScalarContext("diskratio", args.diskratio_w, args.diskratio_c, fmt_metric='{value}% quota disk usage'))       
        check.add(CouchBaseAlerts('alerts'))
        check.add(CXdcrErrors('taskerrors'))
        check.add(CBXdcrPaused('xdcrpaused'))
        check.add(CBNodeStatus('nodes'))
        check.main()       
        r = requests.get("http://%s:%s/pools/default/tasks" % (args.host, args.port),
                          auth=(args.user, args.password))
        data = r.json()
        check = nagiosplugin.Check( Status(data) )
        check.add(CouchBaseAlerts('alerts'))
        check.main()
    else:
        r = requests.get("http://%s:%s/pools/default/buckets/%s/stats" % (args.host, args.port, args.bucket),
                         auth=(args.user, args.password))
        if r.status_code != 200:
            print "####  HTTP Status %s ####" % (r.status_code   )
            raise RuntimeError
        data = r.json()
        check = nagiosplugin.Check( Bucket(data) )
        check.add(nagiosplugin.ScalarContext("low_wat", 80, 90, fmt_metric='{value}%  of low watermark reached'))
        check.add(nagiosplugin.ScalarContext("high_wat", 50, 70, fmt_metric='{value}%  of high watermark reached'))
        check.add(CBBucketGet('get'))
        check.main()
        
    

if __name__ == '__main__':
    main()
        
        
    
