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
        # get applicable conciliation strategies (USER excluded)
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
        for strategy in self.strategies:
            elt = contents_elt.findmeld(f'{strategy}_strategy_a_mid')
            # conciliation requests MUST be sent to MASTER and namespec MUST be reset
            master = self.sup_ctx.master_identifier
            parameters = {NAMESPEC: '', ACTION: strategy}
            url = self.view_ctx.format_url(master, CONCILIATION_PAGE, **parameters)
            elt.attributes(href=url)

    def get_conciliation_data(self):
        """ Get information about all conflicting processes. """
        data = []
        for process in self.sup_ctx.conflicts():
            data.append({'row_type': ProcessRowTypes.APPLICATION_PROCESS,
                         'namespec': process.namespec,
                         'nb_items': len(process.running_identifiers)})
            for identifier in sorted(process.running_identifiers):
                data.append({'row_type': ProcessRowTypes.INSTANCE_PROCESS,
                             'namespec': process.namespec,
                             'identifier': identifier,
                             'uptime': process.info_map[identifier]['uptime']})
        return data

    def write_conciliation_table(self, contents_elt):
        """ Rendering of the conflicts table. """
        conflicts_div_mid = contents_elt.findmeld('conflicts_div_mid')
        if self.supvisors.fsm.state == SupvisorsStates.CONCILIATION and self.sup_ctx.conflicts():
            # get data for table
            data = self.get_conciliation_data()
            # create a row per conflict
            shaded_proc_tr, shaded_detail_tr = False, False  # used to invert background style
            for tr_elt, info in conflicts_div_mid.findmeld('conflict_tr_mid').repeat(data):
                if info['row_type'] == ProcessRowTypes.APPLICATION_PROCESS:
                    self._write_conflict_process(tr_elt, info, shaded_proc_tr)
                    # set line background and invert
                    apply_shade(tr_elt, shaded_proc_tr)
                    shaded_proc_tr = not shaded_proc_tr
                    shaded_detail_tr = shaded_proc_tr
                elif info['row_type'] == ProcessRowTypes.INSTANCE_PROCESS:
                    self._write_conflict_detail(tr_elt, info)
                    # set line background and invert
                    apply_shade(tr_elt, shaded_detail_tr)
                    shaded_detail_tr = not shaded_detail_tr
        else:
            # remove conflicts table
            conflicts_div_mid.replace('No conflict')

    def _write_conflict_process(self, tr_elt, info, shaded_tr):
        """ In a conflicts table, write the process entry in conflict. """
        section_elt = tr_elt.findmeld('section_td_mid')
        section_elt.attrib['rowspan'] = str(info['nb_items'] + 1)
        apply_shade(section_elt, shaded_tr)
        # write process row
        tr_elt.findmeld('process_td_mid').content(info['namespec'])
        tr_elt.findmeld('conflict_instance_td_mid').content('')
        tr_elt.findmeld('pstop_td_mid').content('')
        tr_elt.findmeld('pkeep_td_mid').content('')
        self._write_conflict_strategies(tr_elt, info, shaded_tr)

    def _write_conflict_detail(self, tr_elt, info):
        """ In a conflicts table, write the process entry in conflict. """
        tr_elt.findmeld('section_td_mid').replace('')
        tr_elt.findmeld('process_td_mid').content(SUB_SYMBOL)
        self._write_conflict_identifier(tr_elt, info)
        self._write_conflict_uptime(tr_elt, info)
        self._write_conflict_process_actions(tr_elt, info)
        tr_elt.findmeld('strategy_td_mid').replace('')

    def _write_conflict_identifier(self, tr_elt, info):
        """ In a conflicts table, write the Supvisors instance identifier where runs the process in conflict. """
        identifier = info['identifier']
        nick_identifier = self.supvisors.mapper.get_nick_identifier(identifier)
        elt = tr_elt.findmeld('conflict_instance_a_mid')
        url = self.view_ctx.format_url(identifier, PROC_INSTANCE_PAGE)
        elt.attributes(href=url)
        elt.content(nick_identifier)

    @staticmethod
    def _write_conflict_uptime(tr_elt, info):
        """ In a conflicts table, write the uptime of the process in conflict. """
        elt = tr_elt.findmeld('uptime_td_mid')
        elt.content(simple_duration(info['uptime']))

    def _write_conflict_process_actions(self, tr_elt, info):
        """ In a conflicts table, write the actions that can be requested on the process in conflict. """
        namespec = info['namespec']
        identifier = info.get('identifier', '')
        for action in self.process_methods:
            elt = tr_elt.findmeld(action + '_a_mid')
            parameters = {NAMESPEC: namespec, IDENTIFIER: identifier, ACTION: action}
            url = self.view_ctx.format_url('', CONCILIATION_PAGE, **parameters)
            elt.attributes(href=url)

    def _write_conflict_strategies(self, tr_elt, info, shaded_tr):
        """ In a conflicts table, write the strategies that can be requested on the process in conflict. """
        # extract info
        namespec = info['namespec']
        # update element structure
        td_elt = tr_elt.findmeld('strategy_td_mid')
        # apply shade logic to td element too for background-image to work
        apply_shade(td_elt, shaded_tr)
        # fill the strategies
        td_elt.attrib['rowspan'] = str(info['nb_items'] + 1)
        for strategy in self.strategies:
            elt = td_elt.findmeld(f'{strategy}_local_strategy_a_mid')
            # conciliation requests MUST be sent to the Supvisors Master
            master = self.sup_ctx.master_identifier
            parameters = {NAMESPEC: namespec, ACTION: strategy}
            url = self.view_ctx.format_url(master, CONCILIATION_PAGE, **parameters)
            elt.attributes(href=url)

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
