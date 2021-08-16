#!/bin/bash

test_dir=$(dirname "$(readlink -f "$0")")

# start supervisor on remote machines
for i in cliche81 cliche82 cliche83
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; rm -f log/* etc/supervisord.conf ; supervisord"
done

firefox http://localhost:61000 &
