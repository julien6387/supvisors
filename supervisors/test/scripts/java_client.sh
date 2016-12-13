#! /bin/bash

ANT_FILE=../client/java/build.xml

# test JAVA supervisors events
ant -f $ANT_FILE run_supervisor_evt

# test JAVA system XML-RPC
ant -f $ANT_FILE run_system_rpc

# test JAVA supervisors XML-RPC
ant -f $ANT_FILE run_supervisors_rpc

# test JAVA supervisor XML-RPC
ant -f $ANT_FILE run_supervisor_rpc
