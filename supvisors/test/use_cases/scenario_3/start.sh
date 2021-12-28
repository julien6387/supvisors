#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")

HOSTS="cliche81 cliche82 cliche83"

# configure / clear logs
for i in $HOSTS
do
  ssh $i "cd $test_dir ; rm -rf log ; mkdir log ; ./configure.sh"
done

# start supervisor on all servers
for i in $HOSTS
do
  x=`echo "$i" | tail -c 2`
	echo "start Supvisors on $i as server_$x"
	ssh $i "export DISPLAY=:0 ; export IDENTIFIER=server_$x
	  cd $test_dir
	  sed -i 's/identifier=.*$/identifier='\$IDENTIFIER'/' etc/supervisord_server.conf
	  supervisord -c etc/supervisord_server.conf -i \$IDENTIFIER"
done

# start supervisor on all consoles
for i in $HOSTS
do
  x=`echo "$i" | tail -c 2`
	echo "start Supvisors on $i as console_$x"
	ssh $i "export DISPLAY=:0 ; export IDENTIFIER=console_$x
	cd $test_dir
	sed -i 's/identifier=.*$/identifier='\$IDENTIFIER'/' etc/supervisord_console.conf
	supervisord -c etc/supervisord_console.conf -i \$IDENTIFIER"
done

# start firefox to get the Web UI
firefox http://localhost:61000 &
