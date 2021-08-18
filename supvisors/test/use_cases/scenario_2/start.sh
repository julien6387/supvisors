#!/bin/bash

CONFIG_CMD="python ../../../tools/breed.py -d etc -t template_etc -b scen2_services=5 scen2_hci=5"

test_dir=$(dirname "$(readlink -f "$0")")

# start supervisor on all nodes
for i in cliche81 cliche82 cliche83
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; $CONFIG_CMD ; rm -f log/* ; supervisord"
done

firefox http://localhost:61000 &
