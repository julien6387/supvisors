#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")

# environmental variables for log file names
export CUR_DATE=`date +'%y%m%d'`
export CUR_TIME=`date +'%H%M%S'`

# set default hosts if not provided in command line
HOSTS=${@:-cliche81 cliche82 cliche83}

# clear logs / start server + console on each host
for host in $HOSTS
do
  x=`echo "$host" | tail -c 2`
  ping -c 1 $host 2>&1 >/dev/null && ssh $host "cd $test_dir
    rm -rf log ; mkdir log
	  export DISPLAY=:0
	  export CUR_DATE=$CUR_DATE
	  export CUR_TIME=$CUR_TIME
  	echo \"start Supvisors on $host as server_$x\"
	  export IDENTIFIER=server_$x
	  supervisord -c etc/supervisord_server.conf -i \$IDENTIFIER
  	echo \"start Supvisors on $host as console_$x\"
	  export IDENTIFIER=console_$x
	  supervisord -c etc/supervisord_console.conf -i \$IDENTIFIER"
done

# start firefox to get the Web UI
firefox http://localhost:61000 &
