#! /bin/bash

function sendRequest() {
    echo "===================================================================="
    echo "# Testing: supervisorctl" $@
    echo "===================================================================="
    supervisorctl help $1
    echo
    supervisorctl $@
    echo
}


# print global help
sendRequest help

# status requests
sendRequest sversion
sendRequest sstate
sendRequest master
sendRequest address_status
sendRequest address_status $HOSTNAME
sendRequest application_info
sendRequest application_info database
sendRequest sstatus
sendRequest sstatus database:*
sendRequest sstatus database:movie_server_01 database:movie_server_02 database:movie_server_03
sendRequest conflicts
sendRequest rules
sendRequest rules database:movie_server_02

# command requests on processes
sendRequest start_process CONFIG database:movie_server_01
sendRequest restart_process LESS_LOADED database:movie_server_01
sendRequest stop_process database:movie_server_01

sendRequest start_args database:movie_server_01 -x 3
sleep 3

sendRequest start_process_args MOST_LOADED database:movie_server_01 -x 3
sleep 3

# command requests on applications
sendRequest start_application LESS_LOADED database
sendRequest restart_application MOST_LOADED database
sendRequest stop_application database

# command requests on Supervisor
sendRequest sreload
sleep 30

sendRequest sshutdown

