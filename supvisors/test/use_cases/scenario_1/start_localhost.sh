#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")
cd $test_dir

# clear log folder
rm -rf log
mkdir log

# environmental variables for log file names
export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`

# start firefox to get the Web UI
firefox http://localhost:61000 &

# start non-daemonized supervisor
echo "start Supvisors on" `hostname`
supervisord -c etc/supervisord_localhost.conf -n
