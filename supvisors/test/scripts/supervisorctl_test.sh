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
sendRequest strategies
sendRequest instance_status
sendRequest instance_status $HOSTNAME
sendRequest application_info
sendRequest application_info database
sendRequest sstatus
sendRequest sstatus database:*
sendRequest sstatus database:movie_server_01 database:movie_server_02 database:movie_server_03
sendRequest local_status
sendRequest local_status database:*
sendRequest local_status database:movie_server_01 database:movie_server_02 database:movie_server_03
sendRequest conflicts
sendRequest application_rules
sendRequest application_rules database
sendRequest application_rules database player
sendRequest process_rules
sendRequest process_rules database:movie_server_02
sendRequest process_rules database:movie_server_02 player:movie_player

# command requests on processes
sendRequest start_process CONFIG my_movies:converter_01
sendRequest restart_process LESS_LOADED my_movies:converter_01
sendRequest stop_process my_movies:converter_01
sendRequest start_any_process CONFIG converter

sendRequest start_args my_movies:converter_02 -x 3 -d \'additional arguments\'
sleep 3

sendRequest start_process_args MOST_LOADED my_movies:converter_02 -x 3 -d \'additional arguments\'
sleep 3

sendRequest start_any_process_args CONFIG converter -x 3
sleep 3

sendRequest update_numprocs converter 10
sendRequest update_numprocs converter 15
sendRequest disable converter
sendRequest enable converter 15

# command requests on applications
sendRequest restart_application MOST_LOADED database
sendRequest stop_application database
sendRequest start_application LESS_LOADED database

# command requests on Supervisor
sendRequest conciliate INFANTICIDE
sendRequest sreload
sleep 40
sendRequest sshutdown
