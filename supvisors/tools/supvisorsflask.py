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

import sys

from flask import Flask, g
from supervisor.childutils import getRPCInterface

from .apis import api
from .apis.utils import parse_args


# Create the Flask application
app = Flask(__name__)
api.init_app(app)


@app.before_request
def get_supervisor_proxy():
    """ Get Supervisor proxy before any request. """
    # get the Supervisor proxy
    supervisor_url = app.config.get('url')
    g.proxy = getRPCInterface({'SUPERVISOR_SERVER_URL': supervisor_url})
    # provide version information
    api.version = g.proxy.supvisors.get_api_version()


def main():
    # read the arguments
    args = parse_args(sys.argv[1:])
    if args.debug:
        print(f'ArgumentParser: {args}')
    # start the Flask application
    app.config['url'] = args.supervisor_url
    flask_options = {k: v for k, v in vars(args).items()
                     if k in ['host', 'port', 'debug'] and v is not None}
    app.run(**flask_options)
