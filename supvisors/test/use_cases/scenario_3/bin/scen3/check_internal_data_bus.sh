#!/bin/bash

function internal_data_bus_running() {
  local result=`supervisorctl -s http://localhost:61000 status scen3_internal_data_bus | awk '{print $2}'`
  echo $result
}

while [ $(internal_data_bus_running) != "RUNNING" ]
do
  echo "Waiting for scen3_internal_data_bus to be RUNNING"
  sleep 1
done

echo "scen3_internal_data_bus is RUNNING"
