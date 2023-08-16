#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ======================================================================


from io import StringIO

# Contents of a minimal Supervisor configuration file without Supvisors
NoSupvisors = StringIO('''
[inet_http_server]
port=:60000

[supervisord]
''')

# Contents of a minimal Supervisor configuration file including program definitions
ProgramConfiguration = StringIO('''
[inet_http_server]
port=:60000

[supervisord]

[group:dummy_group]
programs=dummy,dummies

[program:dummy]
command=ls

[program:dummies]
command=ls
process_name=dummy_%(process_num)d
numprocs=3

[fcgi-program:dumber]
command=ls
process_name=dumber_%(process_num)d
numprocs=2
numprocs_start=10
socket=tcp://localhost:9002

[eventlistener:dummy_ears]
command=ls
process_name=dummy_ears_%(process_num)d
events=EVENT
buffer_size=10
numprocs=2
numprocs_start=20
''')

# Contents of a rules file including schema errors
InvalidXmlTest = b'''\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<root>
    <alias name="not used">nodes_prg_B3, nodes_appli_D</alias>
    <alias name="not used too">#, 10.0.0.1, 192.168.12.20</alias>
    <alias name="nodes_prg_B1">#</alias>
    <alias name="nodes_prg_B3">*, 10.0.0.4, 192.168.12.20</alias>
    <alias name="nodes_appli_D"> </alias>

    <model name="dummy_model_01">
        <stop_sequence>0</stop_sequence>
        <required>false</required>
        <wait_exit>false</wait_exit>
        <expected_loading>25</expected_loading>
        <running_failure_strategy>RESTART</running_failure_strategy>
    </model>

    <model name="dummy_model_02">
        <identifiers>#</identifiers>
        <start_sequence>1</start_sequence>
        <required>true</required>
        <wait_exit>true</wait_exit>
    </model>

    <model name="dummy_model_03">
        <identifiers>10.0.0.4, 10.0.0.2</identifiers>
        <stop_sequence>100</stop_sequence>
        <expected_loading>10</expected_loading>
    </model>

    <model name="dummy_model_04">
        <reference>dummy_model_01</reference>
    </model>

    <application name="dummy_application_A">
    </application>

    <application name="dummy_application_B">
        <starting_failure_strategy>STOP</starting_failure_strategy>
        <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
        <distribution>non</distribution>
        <start_sequence>1</start_sequence>
        <stop_sequence>4</stop_sequence>

        <programs>
            <program name="dummy_program_B0"/>

            <program name="dummy_program_B1">
                <identifiers>nodes_prg_B1</identifiers>
                <start_sequence>3</start_sequence>
                <stop_sequence>50</stop_sequence>
                <required>true</required>
                <wait_exit>false</wait_exit>
                <expected_loading>5</expected_loading>
                <running_failure_strategy>CONTINUE</running_failure_strategy>
             </program>
    
            <program name="dummy_program_B2">
                <identifiers>10.0.0.3</identifiers>
                <required>true</required>
                <expected_loading>-1</expected_loading>
                <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
            </program>

            <program name="dummy_program_B3">
                <identifiers>nodes_prg_B3</identifiers>
                <required>false</required>
                <expected_loading>100</expected_loading>
                <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>
            </program>
    
            <program name="dummy_program_B4">
                <identifiers>10.0.0.1, 10.0.0.2</identifiers>
                <start_sequence>-1</start_sequence>
                <stop_sequence>-2</stop_sequence>
                <required>28</required>
                <wait_exit>77</wait_exit>
                <expected_loading>-1</expected_loading>
                <running_failure_strategy>RESTART_APPLICATION</running_failure_strategy>
            </program>

            <program name="dummy_program_B5">
                <identifiers>10.0.0.3, 10.0.0.1, 10.0.0.5</identifiers>
                <start_sequence>start</start_sequence>
                <stop_sequence>stop</stop_sequence>
                <required>req</required>
                <wait_exit>wait</wait_exit>
                <expected_loading>fifty</expected_loading>
                <running_failure_strategy>BACK</running_failure_strategy>
            </program>
        </programs>

    </application>

    <application pattern="_C">
        <distribution>SINGLE_INSTANCE</distribution>
        <identifiers>192.256.16.10,*</identifiers>
        <start_sequence>20</start_sequence>
        <stop_sequence>0</stop_sequence>
        <starting_failure_strategy>ABORT</starting_failure_strategy>
        <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>

        <programs>
            <program name="dummy_program_C0">
                <reference></reference>
            </program>
    
            <program name="dummy_program_C1">
                <reference>unknown</reference>
            </program>
    
            <program name="dummy_program_C2">
                <reference>dummy_model_01</reference>
            </program>
    
            <program name="dummy_program_C3">
                <reference>dummy_model_02</reference>
            </program>
    
            <program name="dummy_program_C4">
                <reference>dummy_model_03</reference>
                <identifiers>#,@</identifiers>
                <start_sequence>3</start_sequence>
                <required>true</required>
                <wait_exit>false</wait_exit>
                <expected_loading>5</expected_loading>
            </program>
        </programs>

    </application>

    <application name="dummy_application_D">
        <start_sequence>-1</start_sequence>
        <stop_sequence>100</stop_sequence>
        <starting_failure_strategy>CONTINUE</starting_failure_strategy>
        <running_failure_strategy>RESTART_APPLICATION</running_failure_strategy>

        <programs>
            <program pattern="dummies_">
                <reference>dummy_model_03</reference>
            </program>
    
            <program pattern="^dummies_01_">
                <identifiers>#</identifiers>
                <start_sequence>1</start_sequence>
                <stop_sequence>1</stop_sequence>
                <required>false</required>
                <wait_exit>true</wait_exit>
                <expected_loading>75</expected_loading>
            </program>

            <program pattern="d.*02.*">
                <reference>dummy_model_04</reference>
            </program>
        </programs>

    </application>

</root>
'''

# Contents of a rules file with no schema error
XmlTest = b'''\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<root>
    <alias name="nodes_model_03">10.0.0.4, 10.0.0.2</alias>
    <alias name="nodes_appli_D">10.0.0.1, 10.0.0.5</alias>
    <alias name="not used">10.0.0.2, nodes_appli_D</alias>

    <model name="dummy_model_01">
        <stop_sequence>0</stop_sequence>
        <required>false</required>
        <wait_exit>false</wait_exit>
        <expected_loading>25</expected_loading>
        <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>
    </model>

    <model name="dummy_model_02">
        <identifiers>#</identifiers>
        <start_sequence>1</start_sequence>
        <required>true</required>
        <wait_exit>true</wait_exit>
    </model>

    <model name="dummy_model_03">
        <identifiers>nodes_model_03</identifiers>
        <stop_sequence>100</stop_sequence>
        <expected_loading>10</expected_loading>
    </model>

    <model name="dummy_model_04">
        <reference>dummy_model_01</reference>
        <expected_loading>20</expected_loading>
    </model>

    <model name="dummy_model_05">
        <reference>dummy_model_04</reference>
        <expected_loading>15</expected_loading>
    </model>

    <application name="dummy_application_A">
    </application>

    <application name="dummy_application_B">
        <distribution>SINGLE_NODE</distribution>
        <start_sequence>1</start_sequence>
        <stop_sequence>4</stop_sequence>
        <starting_strategy>CONFIG</starting_strategy>
        <starting_failure_strategy>STOP</starting_failure_strategy>
        <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>

        <programs>
            <program name="dummy_program_B0"/>
    
            <program name="dummy_program_B1">
                <identifiers>@</identifiers>
                <start_sequence>3</start_sequence>
                <stop_sequence>50</stop_sequence>
                <required>true</required>
                <wait_exit>false</wait_exit>
                <expected_loading>5</expected_loading>
                <running_failure_strategy>CONTINUE</running_failure_strategy>
             </program>
    
            <program name="dummy_program_B2">
                <identifiers>10.0.0.3</identifiers>
                <required>true</required>
                <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
            </program>
    
            <program name="dummy_program_B3">
                <identifiers>*</identifiers>
                <required>false</required>
                <expected_loading>100</expected_loading>
                <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>
            </program>
    
            <program name="dummy_program_B4">
                <identifiers>10.0.0.3, 10.0.0.1, 10.0.0.5</identifiers>
                <running_failure_strategy>RESTART_APPLICATION</running_failure_strategy>
            </program>
        </programs>

    </application>

    <application name="dummy_application_C">
        <distribution>ALL_INSTANCES</distribution>
        <start_sequence>20</start_sequence>
        <stop_sequence>0</stop_sequence>
        <starting_strategy>LOCAL</starting_strategy>
        <starting_failure_strategy>ABORT</starting_failure_strategy>
        <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>

        <programs>
            <program name="dummy_program_C0">
                <reference></reference>
            </program>
    
            <program name="dummy_program_C1">
                <reference>unknown</reference>
            </program>
    
            <program name="dummy_program_C2">
                <reference>dummy_model_01</reference>
            </program>
    
            <program name="dummy_program_C3">
                <reference>dummy_model_02</reference>
            </program>
        </programs>

    </application>

    <application pattern="application_D">
        <distribution>SINGLE_INSTANCE</distribution>
        <identifiers>nodes_appli_D</identifiers>
        <start_sequence>-1</start_sequence>
        <stop_sequence>100</stop_sequence>
        <starting_strategy>LESS_LOADED</starting_strategy>
        <starting_failure_strategy>CONTINUE</starting_failure_strategy>
        <running_failure_strategy>SHUTDOWN</running_failure_strategy>

        <programs>
            <program pattern="dummies_">
                <reference>dummy_model_03</reference>
                <start_sequence>50</start_sequence>
            </program>
    
            <program pattern="^d.*s_01_">
                <identifiers>#, 10.0.0.1, 10.0.0.5</identifiers>
                <start_sequence>1</start_sequence>
                <stop_sequence>1</stop_sequence>
                <required>false</required>
                <wait_exit>true</wait_exit>
                <expected_loading>75</expected_loading>
            </program>

            <program pattern="dum+ies_02_">
                <reference>dummy_model_04</reference>
            </program>
        </programs>

    </application>

    <application name="dummy_application_E">
        <starting_strategy>MOST_LOADED</starting_strategy>
        <programs>
            <program name="dummy_program_E">
                <reference>dummy_model_05</reference>
            </program>
        </programs>
    </application>

</root>
'''
