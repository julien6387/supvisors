#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")

# configure 3 applications
SRV_CONFIG_CMD="supvisors_breed -d etc -t template_etc -p server/*.ini -b scen2_srv=3 -x -v"
HCI_CONFIG_CMD="supvisors_breed -d etc -t template_etc -p console/*ini -b scen2_hci=3 -x -v"

# start supervisor on all servers
for i in cliche81 cliche82
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; rm -rf log ; mkdir log ; $SRV_CONFIG_CMD ; supervisord -c etc/supervisord_server.conf"
done

# start supervisor on all consoles
for i in cliche83
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; rm -rf log ; mkdir log ; $HCI_CONFIG_CMD ; supervisord -c etc/supervisord_console.conf"
done

# start firefox to get the Web UI
firefox http://localhost:61000 &
