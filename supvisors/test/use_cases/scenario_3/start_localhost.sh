#!/bin/bash

# go to script folder
test_dir=$(dirname "$(readlink -f "$0")")
cd $test_dir

# clear log folder
rm -rf log
mkdir log

# configure N HCI (N is number of consoles)
./configure.sh

# start firefox to get the Web UI
firefox http://localhost:61000 &

# Due to Supervisor issue#1483, it is impossible to assign the identifier using the command line
# identifier is not part of the possible expansions
sed -i 's/identifier=.*$/identifier=console_1/' etc/supervisord_console.conf
export IDENTIFIER=console_1
echo "start Supvisors $IDENTIFIER on" `hostname`
supervisord -c etc/supervisord_console.conf -i $IDENTIFIER

sed -i 's/identifier=.*$/identifier=server_1/' etc/supervisord_server.conf
export IDENTIFIER=server_1
echo "start Supvisors $IDENTIFIER on" `hostname`
supervisord -c etc/supervisord_server.conf -i $IDENTIFIER -n
