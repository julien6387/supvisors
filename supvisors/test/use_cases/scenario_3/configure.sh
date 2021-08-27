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

# duplicate Scenario 3 HCI applications iaw the number of consoles
# option -x is used to separate the definitions
supvisors_breed -d etc -t template_etc -b scen3_hci=$NB_CONSOLES -x -v

# assign one HCI application per console
for console in $CONSOLES
do
    mkdir -p etc/console/$console
    FIRST=`ls etc/console/*.ini | head -1`
    mv -f $FIRST etc/console/$console
done
