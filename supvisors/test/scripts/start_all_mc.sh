#!/bin/bash

# directories
SCRIPTS_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPTS_DIR/..`

# start all instances
for host in ${@:-rocky51 rocky52}
do
    if [ "$host" == "rocky51" ]
    then
      echo "start Supervisor supv-01 on $host"
      ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $TEST_DIR ; rm -rf log/*
      export DISPLAY=:0
      export IDENTIFIER=supv-01
      supervisord -i supv-01 -c etc/supervisord_mc.conf"
      echo "start Supervisor supv-03 on $host"
      ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $TEST_DIR
      export DISPLAY=:0
      export IDENTIFIER=supv-03
      supervisord -i supv-03 -c etc/supervisord_alt_mc.conf"
    else
      echo "start Supervisor on $host"
      ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $TEST_DIR ; rm -rf log/*
      export DISPLAY=:0
      supervisord -c etc/supervisord_mc.conf"
    fi
done

cd $TEST_DIR
pwd
sleep 1
tail -f -n +1 log/supervisord.log
