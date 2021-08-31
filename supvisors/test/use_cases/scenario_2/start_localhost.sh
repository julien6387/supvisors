#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")
cd $test_dir

# clear log folder
rm -rf log
mkdir log

# configure 3 applications
supvisors_breed -d etc -t template_etc -b scen2_srv=3 scen2_hci=3 -x -v

# start firefox to get the Web UI
firefox http://localhost:61000 &

# start non-daemonized supervisor
echo "start Supvisors on" `hostname`
supervisord -c etc/supervisord_localhost.conf -n
