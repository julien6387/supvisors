#!/bin/bash

# directories
SCRIPT_DIR=`dirname $(readlink -e $0)`
DISTRIB_DIR=`readlink -e $SCRIPT_DIR/..`

# change working directory
pushd .
cd $DISTRIB_DIR

# change links
rm -rf log/* etc/deployment.xml

# configure UT deployment file iaw host name
sed "s/cliche01/$HOSTNAME/g" etc/deployment_ut.xml > etc/deployment.xml

# stop previous supervisor
$SCRIPT_DIR/ut_stop.sh

# start new supervisor
echo "start test application"
supervisord

# back to ref directory
popd

