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

from typing import Any

from .supvisorsmapper import SupvisorsInstanceId
from .ttypes import EventLinks, Payload


class EventPublisherInterface:
    """ Interface for the publication of Supvisors events. """

    def close(self) -> None:
        """ Close the publisher.

        :return: None
        """
        raise NotImplementedError

    def send_supvisors_status(self, status: Payload) -> None:
        """ Send a JSON-serialized supvisors status through the socket.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError

    def send_instance_status(self, status: Payload) -> None:
        """ Send a Supvisors instance status.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError

    def send_application_status(self, status: Payload) -> None:
        """ Send an application status.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError

    def send_process_event(self, identifier: str, event: Payload) -> None:
        """ Send a process event.

        :param identifier: the identifier used to identify the origin of the event
        :param event: the event to publish
        :return: None
        """
        raise NotImplementedError

    def send_process_status(self, status: Payload) -> None:
        """ Send a process status.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError


def create_external_publisher(supvisors: Any) -> EventPublisherInterface:
    """ Create the relevant event publisher in accordance with the option selected.

    :param supvisors: the global Supvisors instance
    :return: the event publisher instance
    """
    publisher_instance = None
    if supvisors.options.event_link == EventLinks.ZMQ:
        # Create a PyZMQ publisher
        local_instance: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
        try:
            import zmq
            from supvisors.supvisorszmq import EventPublisher
            publisher_instance = EventPublisher(local_instance, supvisors.logger)
        except (ImportError, ModuleNotFoundError):
            supvisors.logger.error('create_external_publisher: failed to import PyZmq')
    return publisher_instance
