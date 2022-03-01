#!/bin/bash

# directories
SCRIPT_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPT_DIR/..`

# change working directory
pushd .
cd $TEST_DIR

# stop all instances
for host in ${@:-rocky51 rocky52}
do
	echo "stop Supervisor ${host}1 on host" $host
  ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $TEST_DIR ; supervisorctl shutdown"
	echo "stop Supervisor ${host}2 on host" $host
  ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $TEST_DIR ; supervisorctl -c etc/supervisord_alt.conf shutdown"
done

# back to ref directory
popd
