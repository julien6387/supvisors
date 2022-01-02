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

package org.supvisors.event;

import com.google.gson.Gson;

import java.util.Timer;
import java.util.TimerTask;

import org.supvisors.common.*;

import org.zeromq.ZMQ;
import org.zeromq.ZMQ.Poller;
import org.zeromq.ZMQ.Socket;
import org.zeromq.SocketType;
import org.zeromq.ZContext;


/**
 * The SupvisorsEventSubscriber wraps the ZeroMQ socket that connects to Supvisors.
 *
 * The TCP socket is configured with a ZeroMQ SUBSCRIBE pattern.
 * It is connected to the Supvisors instance running on the localhost and bound on the event port.
 */
public class SupvisorsEventSubscriber implements Runnable {

    /** The constant header in SupvisorsStatus messages. */
    private static final String SUPVISORS_STATUS_HEADER = "supvisors";

    /** The constant header in SupvisorsInstanceStatus messages. */
    private static final String INSTANCE_STATUS_HEADER = "instance";

    /** The constant header in ApplicationStatus messages. */
    private static final String APPLICATION_STATUS_HEADER = "application";

    /** The constant header in ProcessStatus messages. */
    private static final String PROCESS_STATUS_HEADER = "process";

    /** The constant header in ProcessStatus messages. */
    private static final String PROCESS_EVENT_HEADER = "event";

    /** The ZeroMQ context. */
    private ZContext context;

    /** The ZeroMQ Socket. */
    private Socket subscriber;

    /** The end-of-loop flag. */
    private volatile boolean done;

    /** The event listener. */
    private SupvisorsEventListener listener;

    /**
     * The constructor creates the subscriber socket.
     *
     * @param Integer port: The port number of the Supervisor's server.
     * @param Context context: The ZeroMQ context.
     */
    public SupvisorsEventSubscriber(final Integer port, final ZContext context)  {
        // store the context
        this.context = context;
        //  connect the subscriber socket
        this.subscriber = context.createSocket(SocketType.SUB);
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
     * Set the event listener.
     *
     * @param String listener: the instance that will receive notifications.
     */
    public void setListener(final SupvisorsEventListener listener) {
        this.listener = listener;
    }

    /**
     * Subscription to all events.
     */
    public void subscribeToAll() {
        this.subscriber.subscribe(ZMQ.SUBSCRIPTION_ALL);
    }

    /**
     * Subscription to Supvisors status events.
     */
    public void subscribeToSupvisorsStatus() {
        subscribeTo(SUPVISORS_STATUS_HEADER);
    }

    /**
     * Subscription to Instance status events.
     */
    public void subscribeToInstanceStatus() {
        subscribeTo(INSTANCE_STATUS_HEADER);
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
     * Subscription to Process events.
     */
    public void subscribeToProcessEvent() {
        subscribeTo(PROCESS_EVENT_HEADER);
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
     * Unubscription from Supvisors status events.
     */
    public void unsubscribeFromSupvisorsStatus() {
        unsubscribeFrom(SUPVISORS_STATUS_HEADER);
    }

    /**
     * Unubscription from Instance status events.
     */
    public void unsubscribeFromInstanceStatus() {
        unsubscribeFrom(INSTANCE_STATUS_HEADER);
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
     * Unubscription from Process events.
     */
    public void unsubscribeFromProcessEvent() {
        unsubscribeFrom(PROCESS_EVENT_HEADER);
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
     * The main loop of the Supvisors' event reception.
     */
    public void run() {
        this.done = false;

        // create poller so as to benefit from a non-blocking reception
        Poller poller = this.context.createPoller(1);
        poller.register(this.subscriber, Poller.POLLIN);

        // main loop until stop called or thread interrupted
        while (!this.done && !Thread.currentThread().isInterrupted()) {
            poller.poll(1000);
            // check if something happened on socket
            if (poller.pollin(0)) {
                // get the data
                String header = this.subscriber.recvStr();
                String body = this.subscriber.recvStr();

                // notify subscribers if any
                if (listener != null) {
                    Gson gson = new Gson();
                    if (SUPVISORS_STATUS_HEADER.equals(header)) {
                        SupvisorsStatus status = gson.fromJson(body, SupvisorsStatus.class);
                        listener.onSupvisorsStatus(status);
                    } else if (INSTANCE_STATUS_HEADER.equals(header)) {
                        SupvisorsInstanceInfo info = gson.fromJson(body, SupvisorsInstanceInfo.class);
                        listener.onInstanceStatus(info);
                    } else if (APPLICATION_STATUS_HEADER.equals(header)) {
                        SupvisorsApplicationInfo info = gson.fromJson(body, SupvisorsApplicationInfo.class);
                        listener.onApplicationStatus(info);
                    } else if (PROCESS_STATUS_HEADER.equals(header)) {
                        SupvisorsProcessInfo info = gson.fromJson(body, SupvisorsProcessInfo.class);
                        listener.onProcessStatus(info);
                    } else if (PROCESS_EVENT_HEADER.equals(header)) {
                        SupvisorsProcessEvent evt = gson.fromJson(body, SupvisorsProcessEvent.class);
                        listener.onProcessEvent(evt);
                    }
                }
            }
        }

        // close the socket
        this.subscriber.close();
    }


    /**
     * The main for SupvisorsEventSubscriber self-tests.
     *
     * @param String[] args: The arguments.
     */
    public static void main(String[] args) throws InterruptedException {
        // create ZeroMQ context
        try (ZContext context = new ZContext()) {
            // create and configure the subscriber
            final SupvisorsEventSubscriber subscriber =
                new SupvisorsEventSubscriber(60002, context);
            subscriber.subscribeToAll();
            subscriber.setListener(new SupvisorsEventListener() {

                @Override
                public void onSupvisorsStatus(final SupvisorsStatus status) {
                    System.out.println(status);
                }

                @Override
                public void onInstanceStatus(final SupvisorsInstanceInfo status) {
                    System.out.println(status);
                }

                @Override
                public void onApplicationStatus(final SupvisorsApplicationInfo status) {
                    System.out.println(status);
                }

                @Override
                public void onProcessStatus(final SupvisorsProcessInfo status) {
                    System.out.println(status);
                }

                @Override
                public void onProcessEvent(final SupvisorsProcessEvent status) {
                    System.out.println(status);
                }
            });

            // start subscriber in thread
            Thread t = new Thread(subscriber);
            t.start();

            // schedule task to stop the thread
            new Timer().schedule(new TimerTask() {

                @Override
                public void run() {
                    subscriber.stop();
                }

            }, 60000);

            // wait for the thread to end
            t.join();
        }
    }
}

