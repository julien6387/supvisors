#!/bin/bash

function common_data_bus_running() {
  local result=`supervisorctl -s http://localhost:61000 status common_data_bus | awk '{print $2}'`
  echo $result
}

while [ $(common_data_bus_running) != "RUNNING" ]
do
  echo "Waiting for common_data_bus to be RUNNING"
  sleep 1
done

echo "common_data_bus is RUNNING"
