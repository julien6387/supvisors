# ======================================================================
# Copyright 2023 Julien LE CLEACH
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

from typing import Optional, Tuple

from supervisor.loggers import Logger

from supvisors.ttypes import RequestHeaders, PublicationHeaders, Payload
from .supervisorproxy import SupervisorProxyServer


class RpcHandler:
    """ Class for pushing deferred XML-RPC.

    Attributes:
        - supvisors: a reference to the Supvisors global structure ;
        - proxy_server: the Supervisor proxy server.
    """

    def __init__(self, supvisors) -> None:
        """ Initialization of the attributes.

        :param supvisors: the Supvisors global structure.
        """
        self.supvisors = supvisors
        self.proxy_server = SupervisorProxyServer(supvisors)

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    def stop(self):
        """ Stop the Supvisors proxy server threads. """
        self.proxy_server.stop()

    # Discovery events
    def push_notification(self, discovery_event) -> None:
        """ Post the discovery event to the Supervisor proxy server.

        :param discovery_event: the Supvisors discovery event received on the Multicast Group.
        :return: None.
        """
        self.proxy_server.push_notification(discovery_event)

    # Deferred XML-RPC requests
    def push_request(self, identifier: str, request_type: RequestHeaders, request_body: Optional[Tuple] = None) -> None:
        """ Push the request to the Supervisor proxy server.

        :param identifier: the target identifier of the request.
        :param request_type: the type of the request to send.
        :param request_body: the request_body.
        :return: None.
        """
        self.proxy_server.push_request(identifier, (request_type.value, request_body))

    def send_check_instance(self, identifier: str) -> None:
        """ Send request to check authorization to deal with the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance to check.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.CHECK_INSTANCE)

    def send_start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Send request to start process.

        :param identifier: the identifier of the Supvisors instance where the process has to be started.
        :param namespec: the process namespec.
        :param extra_args: the additional arguments to be passed to the command line.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.START_PROCESS, (namespec, extra_args))

    def send_stop_process(self, identifier: str, namespec: str) -> None:
        """ Send request to stop process.

        :param identifier: the identifier of the Supvisors instance where the process has to be stopped.
        :param namespec: the process namespec.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.STOP_PROCESS, (namespec,))

    def send_restart(self, identifier: str):
        """ Send request to restart a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be restarted.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.RESTART)

    def send_shutdown(self, identifier: str):
        """ Send request to shut down a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be shut down.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.SHUTDOWN)

    def send_restart_sequence(self, identifier: str):
        """ Send request to trigger the DEPLOYMENT phase.

        :param identifier: the Master Supvisors instance.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.RESTART_SEQUENCE)

    def send_restart_all(self, identifier: str):
        """ Send request to restart Supvisors.

        :param identifier: the Master Supvisors instance.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.RESTART_ALL)

    def send_shutdown_all(self, identifier: str):
        """ Send request to shut down Supvisors.

        :param identifier: the Master Supvisors instance.
        :return: None.
        """
        self.push_request(identifier, RequestHeaders.SHUTDOWN_ALL)

    # Publications
    def push_publication(self, publication_type: PublicationHeaders, publication_body: Payload) -> None:
        """ Push the publication to the Supervisor proxy server.

        :param publication_type: the type of the publication to send.
        :param publication_body: the data to publish.
        :return: None.
        """
        self.proxy_server.push_publication((publication_type.value, publication_body))

    def send_tick_event(self, payload: Payload) -> None:
        """ Send the tick event.

        :param payload: the tick to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.TICK, payload)

    def send_process_state_event(self, payload: Payload) -> None:
        """ Send the process state event.

        :param payload: the process state to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS, payload)

    def send_process_added_event(self, payload: Payload) -> None:
        """ Send the process added event.

        :param payload: the added process to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_ADDED, payload)

    def send_process_removed_event(self, payload: Payload) -> None:
        """ Send the process removed event.

        :param payload: the removed process to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_REMOVED, payload)

    def send_process_disability_event(self, payload: Payload) -> None:
        """ Send the process disability event.

        :param payload: the enabled/disabled process to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_DISABILITY, payload)

    def send_host_statistics(self, payload: Payload) -> None:
        """ Send the host statistics.

        :param payload: the statistics to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.HOST_STATISTICS, payload)

    def send_process_statistics(self, payload: Payload) -> None:
        """ Send the process statistics.

        :param payload: the statistics to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_STATISTICS, payload)

    def send_state_event(self, payload: Payload) -> None:
        """ Send the Master state event.

        :param payload: the Supvisors state to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.STATE, payload)
