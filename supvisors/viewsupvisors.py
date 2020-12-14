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

        * a navigation menu towards addresses contents and applications,
        * the state of Supvisors,
        * actions on Supvisors,
        * a synoptic of the processes running on the different addresses,
        * in CONCILIATION state only, the synoptic is replaced by a table of
        conflicts with tools to solve them.
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
        root.findmeld('state_mid').content(self.fsm.state_string())

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
            self.write_address_boxes(root)

    def write_address_boxes(self, root):
        """ Rendering of the addresses boxes. """
        address_div_mid = root.findmeld('address_div_mid')
        addresses = self.address_mapper.addresses
        for div_elt, address in address_div_mid.repeat(addresses):
            # get address status from Supvisors context
            status = self.sup_ctx.addresses[address]
            # set address
            elt = div_elt.findmeld('address_tda_mid')
            if status.state == AddressStates.RUNNING:
                # go to web page located on address, so as to reuse
                # Supervisor StatusView
                url = self.view_ctx.format_url(address, PROC_ADDRESS_PAGE)
                elt.attributes(href=url)
                elt.attrib['class'] = 'on'
            elt.content(address)
            # set state
            elt = div_elt.findmeld('state_td_mid')
            elt.attrib['class'] = status.state_string() + ' state'
            elt.content(status.state_string())
            # set loading
            elt = div_elt.findmeld('percent_td_mid')
            elt.content('{}%'.format(status.loading()))
            # fill with running processes
            process_li_mid = div_elt.findmeld('process_li_mid')
            data = status.running_processes()
            for li_elt, process in process_li_mid.repeat(data):
                li_elt.content(process.namespec())

    def write_conciliation_strategies(self, root):
        """ Rendering of the global conciliation actions. """
        div_elt = root.findmeld('conflicts_div_mid')
        global_strategy_li_mid = div_elt.findmeld('global_strategy_li_mid')
        for li_elt, item in global_strategy_li_mid.repeat(self.strategies):
            elt = li_elt.findmeld('global_strategy_a_mid')
            # conciliation requests MUST be sent to MASTER
            master = self.sup_ctx.master_address
            url = self.view_ctx.format_url(master, SUPVISORS_PAGE, **{ACTION: item})
            elt.attributes(href=url)
            elt.content(item.title())

    def write_conciliation_table(self, root):
        """ Rendering of the conflicts table. """
        div_elt = root.findmeld('conflicts_div_mid')
        # get data for table
        data = [{'namespec': process.namespec(),
                 'rowspan': len(process.addresses) if idx == 0 else 0,
                 'address': address,
                 'uptime': process.infos[address]['uptime']}
                for process in self.sup_ctx.conflicts()
                for idx, address in enumerate(process.addresses)]
        tr_mid = div_elt.findmeld('tr_mid')
        shaded_tr = True
        for tr_elt, item in tr_mid.repeat(data):
            # first get the rowspan
            rowspan = item['rowspan']
            if rowspan:
                shaded_tr = not shaded_tr
            # set row background
            if shaded_tr:
                tr_elt.attrib['class'] = 'shaded'
            else:
                tr_elt.attrib['class'] = 'brightened'
            # set process name
            elt = tr_elt.findmeld('name_td_mid')
            if rowspan > 0:
                namespec = item['namespec']
                elt.attrib['rowspan'] = str(rowspan)
                elt.content(namespec)
                # apply shaded / brightened to td element too for background-image to work
                if shaded_tr:
                    elt.attrib['class'] = 'shaded'
                else:
                    elt.attrib['class'] = 'brightened'
            else:
                elt.replace('')
            # set address
            address = item['address']
            elt = tr_elt.findmeld('caddress_a_mid')
            url = self.view_ctx.format_url(address, PROC_ADDRESS_PAGE)
            elt.attributes(href=url)
            elt.content(address)
            # set uptime
            elt = tr_elt.findmeld('uptime_td_mid')
            elt.content(simple_gmtime(item['uptime']))
            # set detailed process action links
            for action in self.process_methods.keys():
                elt = tr_elt.findmeld(action + '_a_mid')
                parameters = {NAMESPEC: namespec,
                              ADDRESS: address,
                              ACTION: action}
                url = self.view_ctx.format_url('', SUPVISORS_PAGE, **parameters)
                elt.attributes(href=url)
            # set process action links
            td_elt = tr_elt.findmeld('strategy_td_mid')
            if rowspan > 0:
                # apply shaded / brightened to td element too for background-image to work
                if shaded_tr:
                    td_elt.attrib['class'] = 'shaded'
                else:
                    td_elt.attrib['class'] = 'brightened'
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
        if action in self.global_methods.keys():
            return self.global_methods[action]()
        # strategy actions
        if action in self.strategies:
            return self.conciliation_action(namespec, action.upper())
        # process actions
        if action in self.process_methods.keys():
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
            return info_message('process {} stopped on {}'
                                .format(namespec, address))

        on_wait.delay = 0.1
        return on_wait

    def keep_action(self, namespec, address):
        """ Stop the conflicting processes excepted the one running
        on address. """
        # get running addresses of process
        addresses = self.sup_ctx.processes[namespec].addresses
        running_addresses = addresses.copy()
        running_addresses.remove(address)
        for address in running_addresses:
            self.supvisors.zmq.pusher.send_stop_process(address, namespec)

        def on_wait():
            if len(addresses) > 1:
                return NOT_DONE_YET
            return info_message('processes {} stopped but on {}'
                                .format(namespec, address))

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
