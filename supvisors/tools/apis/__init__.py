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

from flask_restx import Api
from supervisor.compat import xmlrpclib

from .system_namespace import api as system_api
from .supervisor_namespace import api as supervisor_api
from .supvisors_namespace import api as supvisors_api

# create Api with all namespaces
api = Api(title='Supvisors Flask interface')
api.add_namespace(system_api)
api.add_namespace(supervisor_api)
api.add_namespace(supvisors_api)


@api.errorhandler
def default_error_handler(error):
    """ Default error handler. """
    return {'message': str(error)}, getattr(error, 'code', 500)


@api.errorhandler(xmlrpclib.Fault)
def supervisor_error_handler(error):
    """ Supervisor error handler. """
    return {'message': error.faultString, 'code': error.faultCode}, 400

