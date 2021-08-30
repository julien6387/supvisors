#!/bin/bash

supvisors_breed -d etc -t template_etc -b scen2_srv=3 scen2_hci=3 -x -v

# start firefox to get the Web UI
firefox http://localhost:61000 &

# start non-daemonized supervisor
rm -f log/*
supervisord -c etc/supervisord_localhost.conf -n
