#!/bin/bash
export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`

test_dir=$(dirname "$(readlink -f "$0")")

echo "start Supvisors on" `hostname`
cd $test_dir
rm -f log/* etc/supervisord.conf
ln -s supervisord_localhost.conf etc/supervisord.conf
supervisord

firefox http://localhost:61000 &
