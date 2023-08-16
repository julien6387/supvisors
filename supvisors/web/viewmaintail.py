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

from urllib.parse import quote

from supervisor.compat import as_string
from supervisor.web import MeldView
from supervisor.xmlrpc import Faults, RPCError


class MainTailView(MeldView):
    """ Adaptation of supervisor.web.TailView to display the logs of Supervisor. """

    def render(self):
        """ Rendering of the Main tail page. """
        supvisors = self.context.supervisord.supvisors
        form = self.context.form
        # get log limit to read
        limit = form.get('limit', '1024')
        limit = min(-1024, int(limit) * -1 if limit.isdigit() else -1024)
        # read Supervisor logs from RPC interface
        rpc_intf = supvisors.supervisor_data.supervisor_rpc_interface
        try:
            tail = rpc_intf.readLog(limit, 0)
        except RPCError as e:
            if e.code == Faults.NO_FILE:
                tail = 'No file for Supervisor'
            else:
                tail = f'ERROR: unexpected rpc fault [{e.code}] {e.text}'
        # generate page
        root = self.clone()
        root.findmeld('title').content('Supervisor tail')
        root.findmeld('tailbody').content(tail)
        url = f'maintail.html?limit={quote(str(abs(limit)))}'
        root.findmeld('refresh_anchor').attributes(href=url)
        return as_string(root.write_xhtmlstring())
