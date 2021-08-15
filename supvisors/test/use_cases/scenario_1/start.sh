#!/bin/bash
export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`

test_dir=$(dirname "$(readlink -f "$0")")

# start supervisor on remote machines
for i in cliche81 cliche82 cliche83
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; rm -f log/* etc/supervisord.conf ; ln -s supervisord_distributed.conf etc/supervisord.conf ; export CUR_DATE=$CUR_DATE ; export CUR_TIME=$CUR_TIME ; supervisord"
done

firefox http://localhost:61000 &

