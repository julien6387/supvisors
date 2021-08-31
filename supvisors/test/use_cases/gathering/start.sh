#!/bin/bash

export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`

test_dir=$(dirname "$(readlink -f "$0")")

# start supervisor on all servers
for i in cliche81 cliche82
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; rm -f log/* ; export CUR_DATE=$CUR_DATE ; export CUR_TIME=$CUR_TIME ; supervisord -c etc/supervisord_server.conf"
done

# start supervisor on all consoles
for i in cliche83
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; ./configure.sh ; rm -f log/* ; export CUR_DATE=$CUR_DATE ; export CUR_TIME=$CUR_TIME ; supervisord -c etc/supervisord_console.conf"
done

firefox http://localhost:61000 &
