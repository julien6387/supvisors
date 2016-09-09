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

import time
import zmq

from supervisor import events

from supervisors.mainloop import SupervisorsMainLoop
from supervisors.process import stringToProcessStates
from supervisors.statistics import instant_statistics
from supervisors.utils import TICK_HEADER, PROCESS_HEADER, STATISTICS_HEADER, supervisors_short_cuts


# class for ZMQ publication of event
class EventPublisher(object):

    def __init__(self, supervisors, zmqContext):
        self.supervisors = supervisors
        # shortcuts for source code readability
        supervisors_short_cuts(self, ['logger'])
        self.address = self.supervisors.address_mapper.local_address
        # create ZMQ socket
        self.socket = zmqContext.socket(zmq.PUB)
        url = 'tcp://*:{}'.format(self.supervisors.options.internalPort)
        self.logger.info('binding EventPublisher to %s' % url)
        self.socket.bind(url)

    def sendTickEvent(self, payload):
        # publish ZMQ tick
        self.logger.debug('send TickEvent {}'.format(payload))
        self.socket.send_string(TICK_HEADER, zmq.SNDMORE)
        self.socket.send_pyobj((self.address, payload))

    def sendProcessEvent(self, payload):
        # publish ZMQ process state
        self.logger.debug('send ProcessEvent {}'.format(payload))
        self.socket.send_string(PROCESS_HEADER, zmq.SNDMORE)
        self.socket.send_pyobj((self.address, payload))

    def sendStatistics(self, payload):
        # publish ZMQ process state
        self.logger.debug('send Statistics {}'.format(payload))
        self.socket.send_string(STATISTICS_HEADER, zmq.SNDMORE)
        self.socket.send_pyobj((self.address, payload))


# class for listening Supervisor events
class SupervisorListener(object):

    def __init__(self, supervisors):
        self.supervisors = supervisors
        # shortcuts for source code readability
        supervisors_short_cuts(self, ['logger'])
        self.address = self.supervisors.address_mapper.local_address
        # subscribe to internal events
        events.subscribe(events.SupervisorRunningEvent, self.runningListener)
        events.subscribe(events.SupervisorStoppingEvent, self.stoppingListener)
        events.subscribe(events.ProcessStateEvent, self.processListener)
        events.subscribe(events.Tick5Event, self.tickListener)
        # ZMQ context definition
        self.zmqContext = zmq.Context.instance()
        self.zmqContext.setsockopt(zmq.LINGER, 0)

    def stoppingListener(self, event):
        # Supervisor is STOPPING: start Supervisors in this supervisord
        self.logger.warn('local supervisord is STOPPING')
        # unsubscribe
        events.clear()
        # stop and join main loop
        self.mainLoop.stop()
        self.mainLoop.join()
        self.logger.warn('cleaning resources')
       # close zmq sockets
        self.publisher.socket.close()
        # close zmq context
        self.zmqContext.term()
        # finally, close logger
        self.logger.close()

    def runningListener(self, event):
        # Supervisor is RUNNING: start Supervisors main loop
        self.mainLoop = SupervisorsMainLoop(self.supervisors, self.zmqContext)
        self.mainLoop.start()
        # replace the default handler for web ui
        self.supervisors.infoSource.replaceDefaultHandler()
        # create publisher
        self.publisher = EventPublisher(self.supervisors, self.zmqContext)

    def processListener(self, event):
        eventName = events.getEventNameByType(event.__class__)
        self.logger.debug('got Process event from supervisord: {} {}'.format(eventName, event))
        # create payload to get data
        payload = {'processname': event.process.config.name,
            'groupname': event.process.group.config.name,
            'state': stringToProcessStates(eventName.split('_')[-1]),
            'now': int(time.time()), 
            'pid': event.process.pid,
            'expected': event.expected }
        self.logger.debug('payload={}'.format(payload))
        self.publisher.sendProcessEvent(payload)

    def tickListener(self, event):
        self.logger.debug('got Tick event from supervisord: {}'.format(event))
        self.publisher.sendTickEvent(event.when)
        # get and publish statistics at tick time
        pid_list = [ (process.getNamespec(), process.processes[self.address]['pid'])
            for process in self.supervisors.context.getPidProcesses(self.address)]
        self.publisher.sendStatistics(instant_statistics(pid_list))

