#!/bin/bash

# The following test is designed to run on supv-01, but requesting supv-03
BASE_ROUTE=http://localhost:5000

function printResult() {
  echo "# ===================================================================="
  echo "# Testing: supvisorsflask" "$@"
  echo "# ===================================================================="
  curl -s -X $1 $BASE_ROUTE/$2 -H 'accept: application/json' -d ''
  echo
}


##########
# System #
##########

printResult GET 'system/listMethods'
printResult GET 'system/methodHelp/supvisors.start_any_process'
printResult GET 'system/methodSignature/supvisors.start_any_process'


##############
# Supervisor #
##############

GROUP=player
NAMESPEC=$GROUP:movie_player

printResult GET 'supervisor/getAPIVersion'
printResult GET 'supervisor/getSupervisorVersion'
printResult GET 'supervisor/getIdentification'
printResult GET 'supervisor/getState'
printResult GET 'supervisor/getPID'

printResult GET  'supervisor/readLog/-100/0'
printResult POST 'supervisor/clearLog'

printResult POST 'supervisor/removeProcessGroup/'$GROUP
printResult POST 'supervisor/addProcessGroup/'$GROUP
printResult POST 'supervisor/reloadConfig'

printResult GET 'supervisor/getAllProcessInfo'
printResult GET 'supervisor/getProcessInfo/'$NAMESPEC

printResult POST 'supervisor/startAllProcesses?wait=True'
sleep 1
printResult POST 'supervisor/stopAllProcesses?wait=True'
sleep 1

printResult POST 'supervisor/startProcessGroup/'$GROUP'?wait=True'
printResult POST 'supervisor/stopProcessGroup/'$GROUP'?wait=True'

printResult POST 'supervisor/startProcess/'$NAMESPEC'?wait=True'
printResult POST 'supervisor/stopProcess/'$NAMESPEC'?wait=True'

printResult POST 'supervisor/startProcessGroup/'$GROUP'?wait=True'

printResult POST 'supervisor/signalProcessGroup/'$GROUP'/STOP'
printResult POST 'supervisor/signalProcess/'$NAMESPEC'/CONT' 
printResult POST 'supervisor/signalAllProcesses/18'

printResult GET 'supervisor/readProcessStdoutLog/'$NAMESPEC'/0/100'
printResult GET 'supervisor/readProcessStderrLog/'$NAMESPEC'/0/100'
printResult GET 'supervisor/tailProcessStdoutLog/'$NAMESPEC'/0/100'
printResult GET 'supervisor/tailProcessStderrLog/'$NAMESPEC'/0/100'

printResult POST 'supervisor/clearProcessLogs/'$NAMESPEC
printResult POST 'supervisor/clearAllProcessLogs'

printResult POST 'supervisor/sendProcessStdin/'$NAMESPEC'/hello'

printResult POST 'supervisor/sendRemoteCommEvent/hello/world'

printResult POST 'supervisor/restart'
sleep 60

# !!! NOT TESTED !!!
# printResult POST 'supervisor/shutdown'


#############
# Supvisors #
#############

IDENTIFIER=supv-01
GROUP=database
NAMESPEC=my_movies:converter_01

printResult POST 'supvisors/change_log_level/debug'

printResult GET 'supvisors/api_version'
printResult GET 'supvisors/supvisors_state'
printResult GET 'supvisors/master_identifier'
printResult GET 'supvisors/strategies'
printResult GET 'supvisors/statistics_status'
printResult GET 'supvisors/local_supvisors_info'

printResult GET 'supvisors/all_instances_state_modes'
printResult GET 'supvisors/instance_state_modes/'$IDENTIFIER

printResult GET 'supvisors/all_instances_info'
printResult GET 'supvisors/instance_info/'$IDENTIFIER

printResult GET 'supvisors/application_rules/'$GROUP
printResult GET 'supvisors/process_rules/'$NAMESPEC

printResult GET 'supvisors/all_applications_info'
printResult GET 'supvisors/application_info/'$GROUP

printResult GET 'supvisors/all_process_info'
printResult GET 'supvisors/process_info/'$NAMESPEC

printResult GET 'supvisors/all_local_process_info'
printResult GET 'supvisors/local_process_info/'$NAMESPEC

printResult GET 'supvisors/all_inner_process_info/'$IDENTIFIER
printResult GET 'supvisors/inner_process_info/'$IDENTIFIER'/'$NAMESPEC

printResult POST 'supvisors/test_start_process/CONFIG/'$NAMESPEC
printResult POST 'supvisors/start_process/CONFIG/'$NAMESPEC'?wait=true'
printResult POST 'supvisors/restart_process/LESS_LOADED/'$NAMESPEC'?wait=true'
printResult POST 'supvisors/stop_process/'$NAMESPEC'?wait=true'

printResult POST 'supvisors/start_process/MOST_LOADED/'$NAMESPEC'?extra_args=-x%203%20-d%20%22additional%20arguments%22&wait=true'
printResult POST 'supvisors/stop_process/'$NAMESPEC'?wait=true'

printResult POST 'supvisors/start_args/'$NAMESPEC'?extra_args=-x%203%20-d%20%22additional%20arguments%22&wait=true'
printResult POST 'supvisors/stop_process/'$NAMESPEC'?wait=true'
printResult POST 'supvisors/stop_process/my_movies:*?wait=true'

printResult POST 'supvisors/start_any_process/CONFIG/converter_1?extra_args=-x%203&wait=true'

# the following command creates a conflict
printResult POST 'supervisor/startProcess/database:movie_server_02?wait=true'
sleep 2

printResult GET  'supvisors/conflicts'
printResult POST 'supvisors/conciliate/INFANTICIDE'
sleep 10
printResult GET  'supvisors/conflicts'

printResult POST 'supvisors/lazy_update_numprocs/converter/12'
printResult POST 'supvisors/update_numprocs/converter/10'
printResult POST 'supvisors/update_numprocs/converter/15'

printResult POST 'supvisors/disable/converter'
printResult POST 'supvisors/enable/converter'

printResult POST 'supvisors/restart_application/MOST_LOADED/'$GROUP'?wait=true'
printResult POST 'supvisors/stop_application/'$GROUP'?wait=true'
printResult POST 'supvisors/test_start_application/LESS_LOADED/'$GROUP
printResult POST 'supvisors/start_application/LESS_LOADED/'$GROUP'?wait=true'

printResult GET  'supvisors/statistics_status'
printResult POST 'supvisors/disable_host_statistics'
printResult POST 'supvisors/disable_process_statistics'
printResult POST 'supvisors/update_collecting_period/7.7'
printResult GET  'supvisors/statistics_status'
printResult POST 'supvisors/enable_host_statistics'
printResult POST 'supvisors/enable_process_statistics'
printResult GET  'supvisors/statistics_status'

printResult POST 'supvisors/restart_sequence'
printResult POST 'supvisors/restart'

# !!! NOT TESTED !!!
# printResult POST 'supvisors/end_sync'
# printResult POST 'supvisors/end_sync/'$IDENTIFIER
# printResult POST 'supvisors/shutdown'
