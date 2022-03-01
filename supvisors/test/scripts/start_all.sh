#!/bin/bash

# directories
SCRIPTS_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPTS_DIR/..`

# start all instances
for host in ${@:-rocky51 rocky52}
do
    echo "start Supervisor ${host}1 on $host"
    ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $TEST_DIR ; rm -rf log/*
      export DISPLAY=:0
      export IDENTIFIER=${host}1
      supervisord -i ${host}1"
    echo "start Supervisor ${host}2 on $host"
    ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $TEST_DIR
      export DISPLAY=:0
      export IDENTIFIER=${host}2
      supervisord -i ${host}2 -c etc/supervisord_alt.conf"
done

cd $TEST_DIR
pwd
sleep 1
tail -f -n +1 log/sup*
