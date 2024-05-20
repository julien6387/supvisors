# ======================================================================
# Copyright 2024 Julien LE CLEACH
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

from typing import List

from supvisors.strategy import conciliate_conflicts
from supvisors.ttypes import ConciliationStrategies, SupvisorsStates
from supvisors.utils import simple_duration
from .viewcontext import *
from .viewmain import MainView
from .webutils import *


class ConciliationView(MainView):
    """ Class ensuring the rendering of the Conciliation page with:

        - a navigation menu towards Supvisors instances contents and applications,
        - the state of Supvisors,
        - actions on Supvisors,
        - a table of conflicts with tools to solve them.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        MainView.__init__(self, context)
        self.page_name: str = CONCILIATION_PAGE
        # get applicable conciliation strategies
        self.strategies: List[str] = [x.name.lower() for x in ConciliationStrategies]
        self.strategies.remove(ConciliationStrategies.USER.name.lower())
        # process actions
        self.process_methods = {'pstop': self.stop_action,
                                'pkeep': self.keep_action}

    def write_contents(self, contents_elt) -> None:
        """ Rendering of the contents of the Supvisors main page.
        This builds either a synoptic of the processes running on the Supvisors instances or the table of conflicts. """
        self.write_conciliation_strategies(contents_elt)
        self.write_conciliation_table(contents_elt)

    # Conciliation part
    def write_conciliation_strategies(self, contents_elt):
        """ Rendering of the global conciliation actions. """
        global_strategy_li_mid = contents_elt.findmeld('global_strategy_li_mid')
        for li_elt, item in global_strategy_li_mid.repeat(self.strategies):
            elt = li_elt.findmeld('global_strategy_a_mid')
            # conciliation requests MUST be sent to MASTER and namespec MUST be reset
            master = self.sup_ctx.master_identifier
            parameters = {NAMESPEC: '', ACTION: item}
            url = self.view_ctx.format_url(master, CONCILIATION_PAGE, **parameters)
            elt.attributes(href=url)
            elt.content(item.title())

    def get_conciliation_data(self):
        """ Get information about all conflicting processes. """
        return [{'namespec': process.namespec,
                 'rowspan': len(process.running_identifiers) if idx == 0 else 0,
                 'identifier': identifier,
                 'uptime': process.info_map[identifier]['uptime']}
                for process in self.sup_ctx.conflicts()
                for idx, identifier in enumerate(sorted(process.running_identifiers))]

    def write_conciliation_table(self, contents_elt):
        """ Rendering of the conflicts table. """
        conflicts_div_mid = contents_elt.findmeld('conflicts_div_mid')
        if self.supvisors.fsm.state == SupvisorsStates.CONCILIATION and self.sup_ctx.conflicts():
            # get data for table
            data = self.get_conciliation_data()
            # create a row per conflict
            shaded_tr = True
            for tr_elt, item in conflicts_div_mid.findmeld('conflict_tr_mid').repeat(data):
                # first get the rowspan and change shade when rowspan is 0 (first line of conflict)
                rowspan = item['rowspan']
                if rowspan:
                    shaded_tr = not shaded_tr
                # set row background
                apply_shade(tr_elt, shaded_tr)
                # write information and actions
                self._write_conflict_name(tr_elt, item, shaded_tr)
                self._write_conflict_identifier(tr_elt, item)
                self._write_conflict_uptime(tr_elt, item)
                self._write_conflict_process_actions(tr_elt, item)
                self._write_conflict_strategies(tr_elt, item, shaded_tr)
        else:
            # remove conflicts table
            conflicts_div_mid.replace('No conflict')

    @staticmethod
    def _write_conflict_name(tr_elt, info, shaded_tr):
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

    def _write_conflict_identifier(self, tr_elt, info):
        """ In a conflicts table, write the Supvisors instance identifier where runs the process in conflict. """
        identifier = info['identifier']
        elt = tr_elt.findmeld('conflict_instance_a_mid')
        url = self.view_ctx.format_url(identifier, PROC_INSTANCE_PAGE)
        elt.attributes(href=url)
        elt.content(identifier)

    @staticmethod
    def _write_conflict_uptime(tr_elt, info):
        """ In a conflicts table, write the uptime of the process in conflict. """
        elt = tr_elt.findmeld('uptime_td_mid')
        elt.content(simple_duration(info['uptime']))

    def _write_conflict_process_actions(self, tr_elt, info):
        """ In a conflicts table, write the actions that can be requested on the process in conflict. """
        namespec = info['namespec']
        identifier = info['identifier']
        for action in self.process_methods:
            elt = tr_elt.findmeld(action + '_a_mid')
            parameters = {NAMESPEC: namespec, IDENTIFIER: identifier, ACTION: action}
            url = self.view_ctx.format_url('', CONCILIATION_PAGE, **parameters)
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
                master = self.sup_ctx.master_identifier
                parameters = {NAMESPEC: namespec, ACTION: st_item}
                url = self.view_ctx.format_url(master, CONCILIATION_PAGE, **parameters)
                elt.attributes(href=url)
                elt.content(st_item.title())
        else:
            td_elt.replace('')

    def make_callback(self, namespec: str, action: str):
        """ Triggers processing iaw action requested. """
        # strategy actions
        if action in self.strategies:
            return self.conciliation_action(namespec, action.upper())
        # process actions
        if action in self.process_methods:
            identifier = self.view_ctx.identifier
            return self.process_methods[action](namespec, identifier)
        # parent actions
        return super().make_callback(namespec, action)

    def stop_action(self, namespec: str, identifier: str) -> Callable:
        """ Stop the conflicting process. """
        # get running instances of process
        running_identifiers = self.sup_ctx.get_process(namespec).running_identifiers
        self.supvisors.rpc_handler.send_stop_process(identifier, namespec)

        def on_wait():
            if identifier in running_identifiers:
                return NOT_DONE_YET
            return info_message(f'process {namespec} stopped on {identifier}')

        on_wait.delay = 0.1
        return on_wait

    def keep_action(self, namespec: str, kept_identifier: str) -> Callable:
        """ Stop the conflicting processes excepted the one running on kept_identifier. """
        # get running instances of process
        running_identifiers = self.sup_ctx.get_process(namespec).running_identifiers
        # send stop requests based on copy but check on source
        identifiers = running_identifiers.copy()
        identifiers.remove(kept_identifier)
        for identifier in identifiers:
            self.supvisors.rpc_handler.send_stop_process(identifier, namespec)

        def on_wait():
            if len(running_identifiers) > 1:
                return NOT_DONE_YET
            return info_message(f'processes {namespec} stopped but on {kept_identifier}')

        on_wait.delay = 0.1
        return on_wait

    def conciliation_action(self, namespec, action):
        """ Performs the automatic conciliation to solve the conflicts. """
        if namespec:
            # conciliate only one process
            conciliate_conflicts(self.supvisors, ConciliationStrategies[action], [self.sup_ctx.get_process(namespec)])
            return delayed_info(f'{action} in progress for {namespec}')
        else:
            # conciliate all conflicts
            conciliate_conflicts(self.supvisors, ConciliationStrategies[action], self.sup_ctx.conflicts())
            return delayed_info(f'{action} in progress for all conflicts')
