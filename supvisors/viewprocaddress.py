#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from supervisor.options import make_namespec
from supervisor.xmlrpc import RPCError

from supvisors.viewcontext import *
from supvisors.viewsupstatus import SupvisorsAddressView
from supvisors.webutils import *


class ProcAddressView(SupvisorsAddressView):
    """ View renderer of the Process section of the Supvisors Address page.
    Inheritance is made from supervisor.web.StatusView to benefit from the action methods.
    Note that StatusView inheritance has been patched dynamically in supvisors.plugin.make_supvisors_rpcinterface
    so that StatusView inherits from ViewHandler instead of MeldView.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        SupvisorsAddressView.__init__(self, context, PROC_NODE_PAGE)

    # RIGHT SIDE / BODY part
    def write_contents(self, root):
        """ Rendering of the contents part of the page. """
        data = self.get_process_data()
        self.write_process_table(root, data)
        # check selected Process Statistics
        namespec = self.view_ctx.parameters[PROCESS]
        if namespec:
            status = self.view_ctx.get_process_status(namespec)
            if not status or self.view_ctx.local_node_name not in status.running_nodes:
                self.logger.warn('unselect Process Statistics for {}'.format(namespec))
                # form parameter is not consistent. remove it
                # form parameter is not consistent. remove it
                self.view_ctx.parameters[PROCESS] = ''
        # write selected Process Statistics
        namespec = self.view_ctx.parameters[PROCESS]
        info = next(filter(lambda x: x['namespec'] == namespec, data), {})
        self.write_process_statistics(root, info)

    def get_process_data(self):
        """ Collect sorted data on processes. """
        # use Supervisor to get local information on all processes
        data = []
        rpc_intf = self.supvisors.info_source.supervisor_rpc_interface
        try:
            all_info = rpc_intf.getAllProcessInfo()
        except RPCError as e:
            self.logger.warn('ProcAddressView.get_process_data: failed to get all process info from {}: {}'
                             .format(self.local_node_name, e.text))
            return data
        # extract what is useful to display
        for info in all_info:
            namespec = make_namespec(info['group'], info['name'])
            status = self.view_ctx.get_process_status(namespec)
            expected_load = status.rules.expected_load if status else '?'
            nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec)
            data.append({'application_name': info['group'],
                         'process_name': info['name'],
                         'namespec': namespec,
                         'node_name': self.view_ctx.local_node_name,
                         'statename': info['statename'],
                         'statecode': info['state'],
                         'description': info['description'],
                         'expected_load': expected_load,
                         'nb_cores': nb_cores,
                         'proc_stats': proc_stats})
        # re-arrange data
        return self.sort_processes_by_config(data)

    def write_process_table(self, root, data):
        """ Rendering of the processes managed through Supervisor """
        if data:
            # loop on all processes
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False  # used to invert background style
            for tr_elt, info in iterator:
                # write common status
                # (shared between this process view and application view)
                self.write_common_process_status(tr_elt, info)
                # print process name
                self.write_process(tr_elt, info)
                # set line background and invert
                apply_shade(tr_elt, shaded_tr)
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    def write_process(self, tr_elt, info):
        """ Rendering of the cell corresponding to the process name. """
        # print process name (as namespec)
        namespec = info['namespec']
        elt = tr_elt.findmeld('name_a_mid')
        elt.content(namespec)
        url = self.view_ctx.format_url(self.local_node_name, TAIL_PAGE, **{PROCESS: namespec})
        elt.attributes(href=url)
