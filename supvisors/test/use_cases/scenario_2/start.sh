#!/bin/bash

CONFIG_CMD="python ../../../tools/breed.py -d etc -t template_etc -b scen2_srv=3 scen2_hci=3"

test_dir=$(dirname "$(readlink -f "$0")")

# start supervisor on all servers
for i in cliche81 cliche82
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; $CONFIG_CMD ; rm -f log/* ; supervisord -c etc/supervisord_server.conf"
done

# start supervisor on all consoles
for i in cliche83
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; $CONFIG_CMD ; rm -f log/* ; supervisord -c etc/supervisord_console.conf"
done

firefox http://localhost:61000 &
