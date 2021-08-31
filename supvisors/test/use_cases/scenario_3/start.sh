#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")

# start supervisor on all servers
for i in cliche81 cliche82
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; rm -rf log ; mkdir log ; supervisord -c etc/supervisord_server.conf"
done

# start supervisor on all consoles
for i in cliche83
do
	echo "start Supvisors on" $i
	ssh $i "export DISPLAY=:0 ; cd $test_dir ; rm -rf log ; mkdir log ; ./configure.sh ; supervisord -c etc/supervisord_console.conf"
done

# start firefox to get the Web UI
firefox http://localhost:61000 &
