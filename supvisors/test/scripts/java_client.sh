#! /bin/bash

ANT_FILE=../client/java/build.xml

# test JAVA supvisors events
ant -f $ANT_FILE run_supvisors_evt

# test JAVA system XML-RPC
ant -f $ANT_FILE run_system_rpc

# test JAVA supervisor XML-RPC
ant -f $ANT_FILE run_supervisor_rpc

sleep 100

# test JAVA supvisors XML-RPC
ant -f $ANT_FILE run_supvisors_rpc
