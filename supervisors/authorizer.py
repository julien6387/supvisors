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

from supervisors.addressmapper import addressMapper
from supervisors.options import mainOptions as opt

import zmq

# determines if autoFencing required: need authport for that
def autoFence():
    return opt.authport is not None

# authorization thread
class _AuthRequester(object):
    def __init__(self):
        self._sockets = { }

    def connect(self, zmqContext):
        for address in addressMapper.expectedAddresses:
            self._sockets[address] = socket = zmqContext.socket(zmq.DEALER)
            socket.setsockopt(zmq.IDENTITY, addressMapper.localAddress)
            url = 'tcp://{}:{}'.format(address, opt.authport)
            opt.logger.info('connecting Auth DEALER to %s' % url)
            socket.connect(url)
 
    def closeAddresses(self, addresses):
        for address in addresses:
            url = 'tcp://{}:{}'.format(address, opt.authport)
            opt.logger.info('disconnecting Auth DEALER from %s' % url)
            self._sockets[address].close()
            del self._sockets[address]
 
    def close(self):
        for socket in self._sockets.values():
            socket.close()
        self._sockets = { }

    def register(self, poller):
        for socket in self._sockets.values():
            poller.register(socket, zmq.POLLIN)

    def checkPoller(self, polledSocks):
        for (address, socket) in self._sockets.items():
            if socket in polledSocks and polledSocks[socket] == zmq.POLLIN:
                return address

    def sendRequest(self, address):
        if address in self._sockets:
            # send empty message
            self._sockets[address].send('')
            opt.logger.warn('request sent from {} to {}'.format(addressMapper.localAddress, address));

    def recvResponse(self, address):
        if address in self._sockets:
            socket = self._sockets[address]
            socket.recv() # envelope
            permit = socket.recv_pyobj() # response as bool
            opt.logger.warn('received response {} from {}'.format(permit, address));
            return permit

authRequester = _AuthRequester()


# authorization component
class Authorizer(object):
    def __init__(self, zmqContext):
        # configure ZMQ socket
        self._socket = zmqContext.socket(zmq.ROUTER)
        url = 'tcp://*:{0}'.format(opt.authport)
        opt.logger.info('binding Authorizer to %s' % url)
        self._socket.bind(url)

    @property
    def socket(self): return self._socket

    def recvRequest(self):
        return self._socket.recv_multipart()[0]

    def sendResponse(self, dealer, permit):
        self._socket.send(dealer, zmq.SNDMORE)
        self._socket.send('', zmq.SNDMORE)
        self._socket.send_pyobj(permit)
