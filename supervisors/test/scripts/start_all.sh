#!/bin/bash

# directories
SCRIPT_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPT_DIR/..`

# start all instances
for host in cliche01 cliche02
do
	echo "start Supervisor on host" $host
	ping -c 1 $host && ssh -X $host "cd $TEST_DIR ; rm -rf log/* ; \
		cp -f etc/deployment_ut.xml etc/deployment.xml ; supervisord"
done

