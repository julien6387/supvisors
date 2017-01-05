#!/bin/bash

# directories
SCRIPTS_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPTS_DIR/..`

# start all instances
for host in cliche01 cliche02
do
	echo "start Supervisor on host" $host
	ping -c 1 $host && ssh -X $host "cd $TEST_DIR ; export DISPLAY=:0 ; rm -rf log/* ; supervisord"
done

# tail on supervisor logs
tail -f log/supervisord.log ./log/supvisors.log
