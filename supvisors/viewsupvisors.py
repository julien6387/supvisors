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

from supervisor.http import NOT_DONE_YET
from supervisor.xmlrpc import RPCError

from supvisors.strategy import conciliate_conflicts
from supvisors.ttypes import (AddressStates,
                              ConciliationStrategies,
                              SupvisorsStates)
from supvisors.utils import simple_gmtime
from supvisors.viewcontext import *
from supvisors.viewhandler import ViewHandler
from supvisors.webutils import *


class SupvisorsView(ViewHandler):
    """ Class ensuring the rendering of the Supvisors main page with:

        - a navigation menu towards addresses contents and applications,
        - the state of Supvisors,
        - actions on Supvisors,
        - a synoptic of the processes running on the different addresses,
        - in CONCILIATION state only, the synoptic is replaced by a table of conflicts with tools to solve them.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        ViewHandler.__init__(self, context)
        self.page_name = SUPVISORS_PAGE
        # get applicable conciliation strategies
        self.strategies = {str.lower(x) for x in ConciliationStrategies.strings()}
        user = ConciliationStrategies.to_string(ConciliationStrategies.USER)
        self.strategies.remove(user.lower())
        # global actions (no parameter)
        self.global_methods = {'refresh': self.refresh_action,
                               'sup_restart': self.sup_restart_action,
                               'sup_shutdown': self.sup_shutdown_action}
        # process actions
        self.process_methods = {'pstop': self.stop_action,
                                'pkeep': self.keep_action}

    def write_navigation(self, root):
        """ Rendering of the navigation menu. """
        self.write_nav(root)

    def write_header(self, root):
        """ Rendering of the header part of the Supvisors main page. """
        # set Supvisors state
        elt = root.findmeld('state_mid')
        elt.content(self.fsm.state_string())

    def write_contents(self, root):
        """ Rendering of the contents of the Supvisors main page.
        This builds either a synoptic of the processes running on the addresses
        or the table of conflicts if any. """
        if self.fsm.state == SupvisorsStates.CONCILIATION and self.sup_ctx.conflicts():
            # remove address boxes
            root.findmeld('boxes_div_mid').replace('')
            # write conflicts
            self.write_conciliation_strategies(root)
            self.write_conciliation_table(root)
        else:
            # remove conflicts table
            root.findmeld('conflicts_div_mid').replace('')
            # write address boxes
            self.write_node_boxes(root)

    # Standard part
    def _write_node_box_title(self, node_div_elt, status):
        """ Rendering of the node box title. """
        # set node name
        elt = node_div_elt.findmeld('node_tda_mid')
        if status.state == AddressStates.RUNNING:
            # go to web page located on address
            url = self.view_ctx.format_url(status.address_name, PROC_ADDRESS_PAGE)
            elt.attributes(href=url)
            elt.attrib['class'] = 'on' + (' master' if status.address_name == self.sup_ctx.master_address else '')
        elt.content(status.address_name)
        # set state
        elt = node_div_elt.findmeld('state_td_mid')
        elt.attrib['class'] = status.state_string() + ' state'
        elt.content(status.state_string())
        # set loading
        elt = node_div_elt.findmeld('percent_td_mid')
        elt.content('{}%'.format(status.loading()))

    @staticmethod
    def _write_node_box_processes(node_div_elt, status):
        """ Rendering of the node box running processes. """
        appli_tr_mid = node_div_elt.findmeld('appli_tr_mid')
        running_processes = status.running_processes()
        application_names = {process.application_name for process in running_processes}
        if application_names:
            shaded_tr = False
            for appli_tr_elt, application_name in appli_tr_mid.repeat(application_names):
                # set row shading
                apply_shade(appli_tr_elt, shaded_tr)
                shaded_tr = not shaded_tr
                # set application name
                app_name_td_mid = appli_tr_elt.findmeld('app_name_td_mid')
                app_name_td_mid.content(application_name)
                # set running process list
                process_li_mid = appli_tr_elt.findmeld('process_li_mid')
                processes = filter(lambda x: x.application_name == application_name, running_processes)
                for li_elt, process in process_li_mid.repeat(processes):
                    process_a_mid = li_elt.findmeld('process_a_mid')
                    process_a_mid.content(process.process_name)
        else:
            # keep an empty line
            process_li_mid = appli_tr_mid.findmeld('process_li_mid')
            process_li_mid.replace('')

    def write_node_boxes(self, root):
        """ Rendering of the node boxes. """
        node_div_mid = root.findmeld('node_div_mid')
        addresses = self.address_mapper.addresses
        for node_div_elt, node in node_div_mid.repeat(addresses):
            # get node status from Supvisors context
            status = self.sup_ctx.addresses[node]
            # write box_title
            self._write_node_box_title(node_div_elt, status)
            # fill with running processes
            self._write_node_box_processes(node_div_elt, status)

    # Conciliation part
    def write_conciliation_strategies(self, root):
        """ Rendering of the global conciliation actions. """
        div_elt = root.findmeld('conflicts_div_mid')
        global_strategy_li_mid = div_elt.findmeld('global_strategy_li_mid')
        for li_elt, item in global_strategy_li_mid.repeat(self.strategies):
            elt = li_elt.findmeld('global_strategy_a_mid')
            # conciliation requests MUST be sent to MASTER and namespec MUST be reset
            master = self.sup_ctx.master_address
            parameters = {NAMESPEC: '', ACTION: item}
            url = self.view_ctx.format_url(master, SUPVISORS_PAGE, **parameters)
            elt.attributes(href=url)
            elt.content(item.title())

    def get_conciliation_data(self):
        """ Get information about all conflicting processes. """
        return [{'namespec': process.namespec(),
                 'rowspan': len(process.addresses) if idx == 0 else 0,
                 'address': address,
                 'uptime': process.infos[address]['uptime']}
                for process in self.sup_ctx.conflicts()
                for idx, address in enumerate(process.addresses)]

    def write_conciliation_table(self, root):
        """ Rendering of the conflicts table. """
        # get data for table
        data = self.get_conciliation_data()
        # get meld elements
        div_elt = root.findmeld('conflicts_div_mid')
        shaded_tr = True
        for tr_elt, item in div_elt.findmeld('tr_mid').repeat(data):
            # first get the rowspan and change shade when rowspan is 0 (first line of conflict)
            rowspan = item['rowspan']
            if rowspan:
                shaded_tr = not shaded_tr
            # set row background
            apply_shade(tr_elt, shaded_tr)
            # write information and actions
            self._write_conflict_name(tr_elt, item, shaded_tr)
            self._write_conflict_address(tr_elt, item)
            self._write_conflict_uptime(tr_elt, item)
            self._write_conflict_process_actions(tr_elt, item)
            self._write_conflict_strategies(tr_elt, item, shaded_tr)

    def _write_conflict_name(self, tr_elt, info, shaded_tr):
        """ In a conflicts table, write the process name in conflict. """
        elt = tr_elt.findmeld('name_td_mid')
        rowspan = info['rowspan']
        if rowspan > 0:
            namespec = info['namespec']
            elt.attrib['rowspan'] = str(rowspan)
            elt.content(namespec)
            # apply shade logic to td element too for background-image to work
            apply_shade(elt, shaded_tr)
        else:
            elt.replace('')

    def _write_conflict_address(self, tr_elt, info):
        """ In a conflicts table, write the address where runs the process in conflict. """
        address = info['address']
        elt = tr_elt.findmeld('caddress_a_mid')
        url = self.view_ctx.format_url(address, PROC_ADDRESS_PAGE)
        elt.attributes(href=url)
        elt.content(address)

    def _write_conflict_uptime(self, tr_elt, info):
        """ In a conflicts table, write the uptime of the process in conflict. """
        elt = tr_elt.findmeld('uptime_td_mid')
        elt.content(simple_gmtime(info['uptime']))

    def _write_conflict_process_actions(self, tr_elt, info):
        """ In a conflicts table, write the actions that can be requested on the process in conflict. """
        namespec = info['namespec']
        address = info['address']
        for action in self.process_methods.keys():
            elt = tr_elt.findmeld(action + '_a_mid')
            parameters = {NAMESPEC: namespec, ADDRESS: address, ACTION: action}
            url = self.view_ctx.format_url('', SUPVISORS_PAGE, **parameters)
            elt.attributes(href=url)

    def _write_conflict_strategies(self, tr_elt, info, shaded_tr):
        """ In a conflicts table, write the strategies that can be requested on the process in conflict. """
        # extract info
        namespec = info['namespec']
        rowspan = info['rowspan']
        # update element structure
        td_elt = tr_elt.findmeld('strategy_td_mid')
        if rowspan > 0:
            # apply shade logic to td element too for background-image to work
            apply_shade(td_elt, shaded_tr)
            # fill the strategies
            td_elt.attrib['rowspan'] = str(rowspan)
            strategy_iterator = td_elt.findmeld('local_strategy_li_mid').repeat(self.strategies)
            for li_elt, st_item in strategy_iterator:
                elt = li_elt.findmeld('local_strategy_a_mid')
                # conciliation requests MUST be sent to MASTER
                master = self.sup_ctx.master_address
                parameters = {NAMESPEC: namespec, ACTION: st_item}
                url = self.view_ctx.format_url(master, SUPVISORS_PAGE, **parameters)
                elt.attributes(href=url)
                elt.content(st_item.title())
        else:
            td_elt.replace('')

    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested. """
        # global actions (no parameter)
        if action in self.global_methods:
            return self.global_methods[action]()
        # strategy actions
        if action in self.strategies:
            return self.conciliation_action(namespec, action.upper())
        # process actions
        if action in self.process_methods:
            address = self.view_ctx.get_address()
            return self.process_methods[action](namespec, address)

    @staticmethod
    def refresh_action():
        """ Refresh web page. """
        return delayed_info('Page refreshed')

    def sup_restart_action(self):
        """ Restart all Supervisor instances. """
        try:
            cb = self.info_source.supvisors_rpc_interface.restart()
        except RPCError as e:
            return delayed_error('restart: {}'.format(e))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError as exc:
                    return error_message('restart: {}'.format(exc))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                return info_message('Supvisors restarted')

            onwait.delay = 0.1
            return onwait
        return delayed_info('Supvisors restarted')

    def sup_shutdown_action(self):
        """ Stop all Supervisor instances. """
        try:
            cb = self.info_source.supvisors_rpc_interface.shutdown()
        except RPCError as e:
            return delayed_error('shutdown: {}'.format(e))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError as exc:
                    return error_message('shutdown: {}'.format(exc))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                return info_message('Supvisors shut down')

            onwait.delay = 0.1
            return onwait
        return delayed_info('Supvisors shut down')

    def stop_action(self, namespec, address):
        """ Stop the conflicting process. """
        # get running addresses of process
        addresses = self.sup_ctx.processes[namespec].addresses
        self.supvisors.zmq.pusher.send_stop_process(address, namespec)

        def on_wait():
            if address in addresses:
                return NOT_DONE_YET
            return info_message('process {} stopped on {}'.format(namespec, address))

        on_wait.delay = 0.1
        return on_wait

    def keep_action(self, namespec, kept_address):
        """ Stop the conflicting processes excepted the one running on address. """
        # get running addresses of process
        addresses = self.sup_ctx.processes[namespec].addresses
        running_addresses = addresses.copy()
        running_addresses.remove(kept_address)
        for address in running_addresses:
            self.supvisors.zmq.pusher.send_stop_process(address, namespec)

        def on_wait():
            if len(addresses) > 1:
                return NOT_DONE_YET
            return info_message('processes {} stopped but on {}'.format(namespec, kept_address))

        on_wait.delay = 0.1
        return on_wait

    def conciliation_action(self, namespec, action):
        """ Performs the automatic conciliation to solve the conflicts. """
        if namespec:
            # conciliate only one process
            conciliate_conflicts(self.supvisors,
                                 ConciliationStrategies.from_string(action),
                                 [self.sup_ctx.processes[namespec]])
            return delayed_info('{} in progress for {}'.format(action, namespec))
        else:
            # conciliate all conflicts
            conciliate_conflicts(self.supvisors,
                                 ConciliationStrategies.from_string(action),
                                 self.sup_ctx.conflicts())
            return delayed_info('{} in progress for all conflicts'.format(action))
