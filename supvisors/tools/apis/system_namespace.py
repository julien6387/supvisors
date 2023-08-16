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

from flask import g, jsonify
from flask_restx import Namespace, Resource
from supervisor.xmlrpc import SystemNamespaceRPCInterface

from .utils import get_docstring_description, get_docstring_parameters

# Supervisor System part
api = Namespace('system', description='System operations')


@api.route('/listMethods', methods=('GET',))
@api.doc(description=get_docstring_description(SystemNamespaceRPCInterface.listMethods))
class SystemListMethods(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.system.listMethods())


@api.route('/methodHelp/<string:name>', methods=('GET',))
@api.doc(description=get_docstring_description(SystemNamespaceRPCInterface.methodHelp))
class SystemMethodHelp(Resource):
    @api.doc(params=get_docstring_parameters(SystemNamespaceRPCInterface.methodHelp))
    def get(self, name):
        return g.proxy.system.methodHelp(name)


@api.route('/methodSignature/<string:name>', methods=('GET',))
@api.doc(description=get_docstring_description(SystemNamespaceRPCInterface.methodSignature))
class SystemMethodSignature(Resource):
    @api.doc(params=get_docstring_parameters(SystemNamespaceRPCInterface.methodSignature))
    def get(self, name):
        return jsonify(g.proxy.system.methodSignature(name))
