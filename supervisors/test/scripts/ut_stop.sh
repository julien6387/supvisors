#!/bin/bash


# directories
SCRIPT_DIR=`dirname $(readlink -e $0)`
DISTRIB_DIR=`readlink -e $SCRIPT_DIR/..`

# kill previous supervisor
PID_FILE=/tmp/supervisord.pid

if [ -e $PID_FILE ]
then
	echo "kill previous supervisord daemon"
	supervisorctl shutdown

	while [ -e $PID_FILE ]
	do
		echo "wait for supervisord termination"
		sleep 5
	done
fi
