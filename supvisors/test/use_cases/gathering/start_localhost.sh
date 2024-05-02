#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")

# environmental variables for log file names
export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`
export DISPLAY=:0

# set default hosts if not provided in command line
HOST=`hostname`

# clear logs / start server + console on each host
cd $test_dir
rm -rf log ; mkdir log

echo "start Supvisors on $HOST as server_1"
export IDENTIFIER=server_1
supervisord -c etc/supervisord_server_localhost.conf -i $IDENTIFIER

echo "start Supvisors on $HOST as console_1"
export IDENTIFIER=console_1
supervisord -c etc/supervisord_console_localhost.conf -i $IDENTIFIER

# start firefox to get the Web UI
firefox http://localhost:61000?auto=true &
