#!/bin/bash

export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`

test_dir=$(dirname "$(readlink -f "$0")")
cd $test_dir
./configure.sh

# start firefox to get the Web UI
firefox http://localhost:61000 &

# start non-daemonized supervisor
rm -f log
mkdir log
supervisord -c etc/supervisord_localhost.conf -n
