#!/bin/bash

test_dir=$(dirname "$(readlink -f "$0")")
cd $test_dir
./configure.sh

# start firefox to get the Web UI
firefox http://localhost:61000 &

# start non-daemonized supervisor
rm -f log/*
supervisord -c etc/supervisord_localhost.conf -n
