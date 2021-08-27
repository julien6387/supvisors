#!/bin/bash

supvisors_breed -d etc -t template_etc -p server/*.ini -b scen2_srv=3 -v
supvisors_breed -d etc -t template_etc -p console/*ini -b scen2_hci=3 -v

# start firefox to get the Web UI
firefox http://localhost:61000 &

# start non-daemonized supervisor
rm -f log/*
supervisord -c etc/supervisord_localhost.conf -n
