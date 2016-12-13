/*
 * Copyright 2016 Julien LE CLEACH
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *     http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.supervisors.event;

import org.supervisors.common.*;
import org.zeromq.ZMQ;
import org.zeromq.ZMQ.Context;
import org.zeromq.ZMQ.Poller;
import org.zeromq.ZMQ.Socket;


/**
 * The SupervisorsEventSubscriber wraps the ZeroMQ socket that connects to Supervisors.
 *
 * The TCP socket is configured with a ZeroMQ SUBSCRIBE pattern.
 * It is connected to the Supervisors instance running on the localhost and bound on the event port.
 */
public class SupervisorsEventSubscriber implements Runnable {

    /** The constant header in SupervisorStatus messages. */
    private static final String SUPERVISORS_STATUS_HEADER = "supervisors";

    /** The constant header in AddressStatus messages. */
    private static final String ADDRESS_STATUS_HEADER = "address";

    /** The constant header in ApplicationStatus messages. */
    private static final String APPLICATION_STATUS_HEADER = "application";

    /** The constant header in ProcessStatus messages. */
    private static final String PROCESS_STATUS_HEADER = "process";

    /** The ZeroMQ context. */
    private Context context;

    /** The ZeroMQ Socket. */
    private Socket subscriber;

    /** The end-of-loop flag. */
    private volatile boolean done;

    /** The event listener. */
    private SupervisorsEventListener listener;

    /**
     * The constructor creates the subscriber socket.
     *
     * @param Integer port: The port number of the Supervisor's server.
     * @param Context context: The ZeroMQ context.
     */
    public SupervisorsEventSubscriber(final Integer port, final Context context)  {
        // store the context
        this.context = context;
        //  connect the subscriber socket
        this.subscriber = context.socket(ZMQ.SUB);
        this.subscriber.connect("tcp://localhost:" + port);
    }

    /**
     * Close the ZeroMQ socket.
     */
    private void close() {
        this.subscriber.close();
        this.subscriber = null;
    }

    /**
     * Subscription to all events.
     */
    public void subscribeToAll() {
        this.subscriber.subscribe(ZMQ.SUBSCRIPTION_ALL);
    }

    /**
     * Subscription to Supervisors status events.
     */
    public void subscribeToSupervisorsStatus() {
        subscribeTo(SUPERVISORS_STATUS_HEADER);
    }

    /**
     * Subscription to Address status events.
     */
    public void subscribeToAddressStatus() {
        subscribeTo(ADDRESS_STATUS_HEADER);
    }

    /**
     * Subscription to Application status events.
     */
    public void subscribeToApplicationStatus() {
        subscribeTo(APPLICATION_STATUS_HEADER);
    }

    /**
     * Subscription to Process status events.
     */
    public void subscribeToProcessStatus() {
        subscribeTo(PROCESS_STATUS_HEADER);
    }

    /**
     * Subscription to event.
     *
     * @param String header: the header of the message to subscribe to.
     */
    private void subscribeTo(final String header) {
        this.subscriber.subscribe(header.getBytes(ZMQ.CHARSET));
    }

    /**
     * Unubscription from all events.
     */
    public void unsubscribeFromAll() {
        this.subscriber.unsubscribe(ZMQ.SUBSCRIPTION_ALL);
    }

    /**
     * Unubscription from Supervisors status events.
     */
    public void unsubscribeFromSupervisorsStatus() {
        unsubscribeFrom(SUPERVISORS_STATUS_HEADER);
    }

    /**
     * Unubscription from Address status events.
     */
    public void unsubscribeFromAddressStatus() {
        unsubscribeFrom(ADDRESS_STATUS_HEADER);
    }

    /**
     * Unubscription from Application status events.
     */
    public void unsubscribeFromApplicationStatus() {
        unsubscribeFrom(APPLICATION_STATUS_HEADER);
    }

    /**
     * Unubscription from Process status events.
     */
    public void unsubscribeFromProcessStatus() {
        unsubscribeFrom(PROCESS_STATUS_HEADER);
    }

    /**
     * Unsubscription from event.
     *
     * @param String header: the header of the message to unsubscribe from.
     */
    private void unsubscribeFrom(final String header) {
        this.subscriber.unsubscribe(header.getBytes(ZMQ.CHARSET));
    }

    /**
     * Set the flag to stop the main loop.
     */
    public void stop() {
        this.done = true;
    }

    /**
     * The main loop of the Supervisors' event reception.
     */
    public void run() {
        this.done = false;

        // create poller so as to benefit from a non-blocking reception
        Poller poller = new Poller(1);
        poller.register(this.subscriber, Poller.POLLIN);

        // main loop until stop called or thread interrupted
        while (!this.done && !Thread.currentThread().isInterrupted()) {
            poller.poll(1000);
            // check if something happened
            if (poller.pollin(0)) {
                String header = this.subscriber.recvStr();
                String body = this.subscriber.recvStr();
                if (SUPERVISORS_STATUS_HEADER.equals(header)) {
                    onSupervisorsStatus(new SupervisorsState(body));
                } else if (ADDRESS_STATUS_HEADER.equals(header)) {
                    onAddressStatus(new SupervisorsAddressInfo(body));
                } else if (APPLICATION_STATUS_HEADER.equals(header)) {
                    onApplicationStatus(new SupervisorsApplicationInfo(body));
                } else if (PROCESS_STATUS_HEADER.equals(header)) {
                    onProcessStatus(new SupervisorsProcessInfo(body));
                }
            }
        }

        // close the socket
        this.subscriber.close();
    }

    // FIXME: implement interface
    public void onSupervisorsStatus(final SupervisorsState status) {
        System.out.println(status);
    }

    public void onAddressStatus(final SupervisorsAddressInfo status) {
        System.out.println(status);
    }

    public void onApplicationStatus(final SupervisorsApplicationInfo status) {
        System.out.println(status);
    }

    public void onProcessStatus(final SupervisorsProcessInfo status) {
        System.out.println(status);
    }

    /**
     * The main for SupervisorsEventSubscriber self-tests.
     *
     * @param String[] args: The arguments.
     */
    public static void main(String[] args) {
        Context context = ZMQ.context(1);
        SupervisorsEventSubscriber subscriber = new SupervisorsEventSubscriber(60002, context);
        subscriber.subscribeToAll();
        new Thread(subscriber).start();
        try {
            Thread.sleep(20000);
        } catch (Exception e) {
            
        }
        subscriber.stop();
    }

}

