#!/bin/bash
export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`

test_dir=$(dirname "$(readlink -f "$0")")

echo "start Supvisors on" `hostname`
cd $test_dir
rm -f log/*
supervisord -c etc/supervisord_localhost.conf

firefox http://localhost:61000 &
