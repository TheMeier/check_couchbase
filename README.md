# check_couchbase

A simple nagios/icinga check plugin for couchbase aiming for minimal configuration.

## How to use:
```
define command {
        command_name                    check_couchbase
        command_line                    $USER1$/check_couchbase.py -H $HOSTADDRESS$ -U $ARG1$ -P $ARG2$
        register                        1
}

define command {
        command_name                    check_couchbase_bucket
        command_line                    $USER1$/check_couchbase.py -H $HOSTADDRESS$ -U $ARG1$ -P $ARG2$ -b $ARG3$
        register                        1
}



define service {
        host_name                       somehost
        service_description             Couchbase Cluster Status
        check_command                   check_couchbase!<username>!<password>
        process_perf_data               1
        register                        1
}


define service {
        host_name                       somehost
        service_description             Couchbase Bucket Status
        check_command                   check_couchbase_bucket!<username>!<password>!<bucketname>
        process_perf_data               1
        register                        1
}


```
