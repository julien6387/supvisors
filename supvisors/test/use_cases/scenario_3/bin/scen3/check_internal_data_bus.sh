#!/bin/bash

function internal_data_bus_running() {
  local result=`supvisorsctl -s ${SUPERVISOR_SERVER_URL} sstatus scen3_internal_data_bus | tail -1 | awk '{print $3}'`
  echo $result
}

while [ $(internal_data_bus_running) != "RUNNING" ]
do
  echo "Waiting for scen3_internal_data_bus to be RUNNING"
  sleep 1
done

echo "scen3_internal_data_bus is RUNNING"
