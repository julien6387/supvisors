#!/bin/bash

# get consoles from Supvisors rules file
RULES_FILE=etc/supvisors_rules.xml

PY_ALIAS="from xml.etree.ElementTree import parse
root = parse('$RULES_FILE').getroot()
consoles = root.findtext('./alias[@name=\"consoles\"]')
print(consoles.replace(',', ' '))
"

CONSOLES=`python3 -c "$PY_ALIAS"`
NB_CONSOLES=`echo $CONSOLES | wc -w`

# clear configuration files
find etc -name "*.ini" | xargs rm -f

# copy Scenario 1 configuration
mkdir -p etc/scenario_1
for folder in `ls -d ../scenario_1/etc/*/`
do
  cp -rf $folder etc/scenario_1
done

# duplicate Scenario 2 SRV+HCI applications 3 times
supvisors_breed -d etc/scenario_2 -t ../scenario_2/template_etc -b scen2_srv=3 scen2_hci=3 -x -v

# duplicate Scenario 3 HCI applications iaw the number of consoles
# option -x is used to separate the definitions
supvisors_breed -d etc/scenario_3 -t ../scenario_3/template_etc -b scen3_hci=$NB_CONSOLES -x -v

# copy Scenario 3 common + server configurations
cp -rf ../scenario_3/etc/common etc/scenario_3
cp -rf ../scenario_3/etc/server etc/scenario_3

# assign one HCI application per console
for console in $CONSOLES
do
    mkdir -p etc/scenario_3/console/$console
    FIRST=`ls etc/scenario_3/console/group_scen3*.ini | head -1`
    mv -f $FIRST etc/scenario_3/console/$console
done
