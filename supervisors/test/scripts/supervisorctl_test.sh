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

sleep 1

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
sendRequest start_process CONFIG my_movies:converter_01
sendRequest restart_process LESS_LOADED my_movies:converter_01
sendRequest stop_process my_movies:converter_01

sendRequest start_args my_movies:converter_02 -x 3 -d \'additional arguments\'
sleep 3

sendRequest start_process_args MOST_LOADED my_movies:converter_02 -x 3 -d \'additional arguments\'
sleep 3

# command requests on applications
sendRequest restart_application MOST_LOADED database
sendRequest stop_application database
sendRequest start_application LESS_LOADED database

# command requests on Supervisor
sendRequest sreload

# WARN: cannot test anything after sreload because script is being killed
# so a shell fork is done for this last test
(sleep 60 ; sendRequest sshutdown) &
