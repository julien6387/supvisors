#!/bin/bash

# directories
SCRIPT_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPT_DIR/..`

# change working directory
pushd .
cd $TEST_DIR

# stop all instances
for host in cliche01 cliche02
do
	echo "stop Supervisor on host" $host
        ping -c 1 $host && ssh $host "cd $TEST_DIR ; supervisorctl shutdown"
done

# back to ref directory
popd

