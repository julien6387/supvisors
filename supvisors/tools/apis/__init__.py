#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2022 Julien LE CLEACH
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

from xmlrpc.client import Fault

from flask_restx import Api
from supervisor.xmlrpc import Faults

from supvisors.ttypes import SupvisorsFaults
from .supervisor_namespace import api as supervisor_api
from .supvisors_namespace import api as supvisors_api
from .system_namespace import api as system_api

# create Api with all namespaces
api = Api(title='Supvisors Flask interface')
api.add_namespace(system_api)
api.add_namespace(supervisor_api)
api.add_namespace(supvisors_api)


@api.errorhandler
def default_error_handler(error):
    """ Default error handler. """
    return {'message': str(error)}, getattr(error, 'code', 500)


@api.errorhandler(Fault)
def supervisor_error_handler(error):
    """ Supervisor default error handler. """
    if error.faultCode in [Faults.UNKNOWN_METHOD,
                           Faults.SIGNATURE_UNSUPPORTED,
                           Faults.BAD_NAME,
                           Faults.NO_FILE]:
        # resource not found
        http_code = 404
    elif error.faultCode in [Faults.ALREADY_STARTED,
                             Faults.NOT_RUNNING,
                             Faults.ALREADY_ADDED,
                             Faults.SHUTDOWN_STATE,
                             SupvisorsFaults.NOT_MANAGED,
                             SupvisorsFaults.DISABLED,
                             SupvisorsFaults.NOT_APPLICABLE,
                             SupvisorsFaults.BAD_SUPVISORS_STATE]:
        # request rejected due to conflict with Supervisor / Supvisors internal state
        http_code = 409
    elif error.faultCode in [Faults.NOT_EXECUTABLE,
                             Faults.FAILED,
                             Faults.ABNORMAL_TERMINATION,
                             Faults.SPAWN_ERROR,
                             Faults.STILL_RUNNING,
                             Faults.CANT_REREAD,
                             SupvisorsFaults.SUPVISORS_CONF_ERROR,
                             SupvisorsFaults.NOT_INSTALLED]:
        # something wrong with Supervisor / Supvisors configuration
        http_code = 500
    else:
        # INCORRECT_PARAMETERS, BAD_ARGUMENTS, BAD_SIGNAL (, SUCCESS)
        http_code = 400
    return {'message': error.faultString, 'code': error.faultCode}, http_code
