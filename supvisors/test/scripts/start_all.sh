#!/bin/bash

# directories
SCRIPTS_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPTS_DIR/..`

# start all instances
for host in cliche81 cliche82 cliche83
do
    echo "start Supervisor on host" $host
    ping -c 1 $host && ssh -X $host "cd $TEST_DIR ; export DISPLAY=:0 ; rm -rf log/* ; supervisord"
done

# tail on supervisor & supvisors logs
tail -f log/sup*visor..log
