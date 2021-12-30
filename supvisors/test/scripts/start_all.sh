#!/bin/bash

# directories
SCRIPTS_DIR=`dirname $(readlink -e $0)`
TEST_DIR=`readlink -e $SCRIPTS_DIR/..`

# start all instances
for host in ${@:-cliche81 cliche82 cliche83}
do
    echo "start Supervisor on host" $host
    ping -c 1 $host 2>&1 >/dev/null && ssh -fX $host "cd $TEST_DIR ; rm -rf log/*
      export DISPLAY=:0
      export IDENTIFIER=$host
      sed -i 's/identifier=.*$/identifier='\$IDENTIFIER'/' etc/supervisord.conf
      supervisord"
done

cd $TEST_DIR
pwd
sleep 1
tail -f -n +1 log/sup*
