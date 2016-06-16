#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from supervisors.options import options
from supervisors.rpcinterface import _RPCInterface

from supervisor.http import NOT_DONE_YET
from supervisor.options import VERSION, make_namespec
from supervisor.process import ProcessStates
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.web import *

import datetime, urllib

class SupervisorsView(MeldView):
    def __init__(self, context):
        # supersedes MeldView constructor
        options.logger.info(context.template)
        if not os.path.isabs(context.template):
            here = os.path.abspath(os.path.dirname(__file__))
            options.logger.info(here)
            context.template = os.path.join(here, context.template)
            options.logger.info(context.template)
        MeldView.__init__(self, context)

    def css_class_for_state(self, state):
        if state == ProcessStates.RUNNING:
            return 'statusrunning'
        elif state in (ProcessStates.FATAL, ProcessStates.BACKOFF):
            return 'statuserror'
        else:
            return 'statusnominal'

    def make_callback(self, namespec, action):
        supervisord = self.context.supervisord

        # the rpc interface code is already written to deal properly in a
        # deferred world, so just use it
        supervisors =   ('supervisor', _RPCInterface(supervisord))
        main =   ('supervisor', SupervisorNamespaceRPCInterface(supervisord))
        system = ('system', SystemNamespaceRPCInterface([main, supervisors]))

        rpcinterface = RootRPCInterface([supervisors, main, system])

        if action:
            if action == 'toto':
                callback = rpcinterface.supervisors.toto()
#                def wait():
#                    if callback() is NOT_DONE_YET:
#                        return NOT_DONE_YET
#                    else:
#                        return 'All stopped at %s' % time.ctime()
#                wait.delay = 0.1
#                return wait
        return 'toto DONE'
        raise ValueError(action)

    def render(self):
        form = self.context.form
        response = self.context.response
        processname = form.get('processname')
        action = form.get('action')
        message = form.get('message')

        if action:
            if not self.callback:
                self.callback = self.make_callback(processname, action)
                return NOT_DONE_YET

            message =  self.callback()
            if message is NOT_DONE_YET: return NOT_DONE_YET
 
            if message is not None:
                server_url = form['SERVER_URL']
                location = server_url + '?message=%s' % urllib.quote(message)
                response['headers']['Location'] = location

        # TODO: get interface through SupervisorInfoSource
        supervisord = self.context.supervisord
        supervisors =   ('supervisors', _RPCInterface(supervisord))
        rpcinterface = RootRPCInterface([supervisors])

        data = [{'status':'RUNNING',
                'name':'toto',
                'group':'JLC',
                'actions':[],
                'state':ProcessStates.FATAL,
                'description':'essai de meld3'}]

        root = self.clone()

        if message is not None:
            statusarea = root.findmeld('statusmessage')
            statusarea.attrib['class'] = 'status_msg'
            statusarea.content(message)

        if data:
            iterator = root.findmeld('tr').repeat(data)
            shaded_tr = False

            for tr_element, item in iterator:
                status_text = tr_element.findmeld('status_text')
                status_text.content(item['status'].lower())
                status_text.attrib['class'] = self.css_class_for_state(item['state'])

                info_text = tr_element.findmeld('info_text')
                info_text.content(item['description'])

                anchor = tr_element.findmeld('name_anchor')
                processname = make_namespec(item['group'], item['name'])
                anchor.attributes(href='tail.html?processname=%s' % urllib.quote(processname))
                anchor.content(processname)

                actions = item['actions']
                actionitem_td = tr_element.findmeld('actionitem_td')

                for li_element, actionitem in actionitem_td.repeat(actions):
                    anchor = li_element.findmeld('actionitem_anchor')
                    if actionitem is None:
                        anchor.attrib['class'] = 'hidden'
                    else:
                        anchor.attributes(href=actionitem['href'],
                                          name=actionitem['name'])
                        anchor.content(actionitem['name'])
                        if actionitem['target']:
                            anchor.attributes(target=actionitem['target'])
                if shaded_tr:
                    tr_element.attrib['class'] = 'shade'
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('statustable')
            table.replace('No programs to manage')

        root.findmeld('sup_version').content(VERSION)
        copyright_year = str(datetime.date.today().year)
        root.findmeld('copyright_date').content(copyright_year)

        return root.write_xhtmlstring()


def updateUiHandler():
    # update Supervisor VIEWS entry
    # TODO: replace Supervisor main entry (not ready yet)
    #VIEWS['status.html'] = VIEWS['index.html']
    #VIEWS['index.html'] =  { 'template':'ui/supervisors.html', 'view':SupervisorsView }
    VIEWS['supervisors.html'] =  { 'template':'ui/supervisors.html', 'view':SupervisorsView }
