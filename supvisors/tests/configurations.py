#!/usr/bin/python
#-*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
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


from StringIO import StringIO

# Contents of a minimal Supervisor configuration file without Supvisors
NoSupvisors = StringIO("""
[inet_http_server]
port=:60000

[supervisord]
""")


# Contents of a minimal Supervisor configuration file including program definitions
ProgramConfiguration = StringIO("""
[inet_http_server]
port=:60000

[supervisord]
[supvisors]

[program:dummy]
command=ls

[program:dummies]
command=ls
process_name=dummy_%(process_num)d
numprocs=3

[program:dumber]
command=ls
process_name=dumber_%(process_num)d
numprocs=2
numprocs_start=10
""")


# Contents of a minimal Supervisor configuration file without
#  Supvisors options defined
DefaultOptionConfiguration = StringIO("""
[inet_http_server]
port=:60000

[supervisord]
[supvisors]
""")


# Contents of a minimal Supervisor configuration file including
#  Supvisors options defined
DefinedOptionConfiguration = StringIO("""
[inet_http_server]
port=:60000

[supervisord]

[supvisors]
address_list=cliche01,cliche03,cliche02
deployment_file=my_movies.xml
auto_fence=true
internal_port=60001
event_port=60002
synchro_timeout=20
deployment_strategy=MOST_LOADED
conciliation_strategy=SENICIDE
stats_periods=5,60,600
stats_histo=100
stats_irix_mode=true
logfile=/tmp/supvisors.log
logfile_maxbytes=50KB
logfile_backups=5
loglevel=error
""")
