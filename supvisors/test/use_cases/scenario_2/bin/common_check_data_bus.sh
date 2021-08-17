#!/bin/bash

function common_data_bus_running() {
    local result=`supervisorctl status common_data_bus | awk '{print $2}'`
    echo $result
}

while [ $(common_data_bus_running) != "RUNNING" ]
do
    sleep 1
done
