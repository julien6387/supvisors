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

package org.supvisors.common;

import java.util.HashMap;

import com.google.gson.annotations.SerializedName;

/**
 * The Class SupvisorsAddressInfo.
 *
 * It gives a structured form to the address information received from a XML-RPC.
 */
public class SupvisorsAddressInfo implements SupvisorsAnyInfo {

    /**
     * The State enumeration for an address.
     *
     * UNKNOWN:   used at initialization, before any heartbeat message is
     *            received from this address.
     * CHECKING:  used when the local Supvisors checks the isolation status of
     *            this address.
     * RUNNING:   used when the local Supvisors receives heartbeat messages
     *            from this address.
     * SILENT:    used when the local Supvisors does not receive any heartbeat
     *            message from this address.
     * ISOLATING: used when the local Supvisors is about to disconnect this address.
     * ISOLATED:  used when the local Supvisors has disconnected this address.
     */
    public enum State {
        UNKNOWN(0),
        CHECKING(1),
        RUNNING(2),
        SILENT(3),
        ISOLATING(4),
        ISOLATED(5);

        private final int value;
        public int getValue() {
            return value;
        }

        private State(int value) {
            this.value = value;
        }
    }

    /** The address name. */
    private String address_name;

    /** The address state. */
    private State statename;

    /** The date of the last heartbeat message, as received. */
    private Integer remote_time;

    /** The date of the last heartbeat message, in the local reference time. */
    private Integer local_time;

    /** The TICK counter. */
    private Integer sequence_counter;

    /**
     * The current declared loading of the address.
     * Note: This is not a measurement. It corresponds to the sum of the declared loading of the running processes.
     */
    private Integer loading;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsAddressInfo(HashMap addressInfo)  {
        this.address_name = (String) addressInfo.get("address_name");
        this.statename = State.valueOf((String) addressInfo.get("statename"));
        this.remote_time = (Integer) addressInfo.get("remote_time");
        this.local_time = (Integer) addressInfo.get("local_time");
        this.sequence_counter = (Integer) addressInfo.get("sequence_counter");
        this.loading = (Integer) addressInfo.get("loading");
    }

    /**
     * The getName method returns the name of the address.
     *
     * @return String: The name of the address.
     */
    public String getName() {
        return this.address_name;
    }

    /**
     * The getState method returns the state of the address.
     *
     * @return State: The state of the address.
     */
    public State getState() {
        return this.statename;
    }

    /**
     * The getRemoteTime method returns the date of the last heartbeat message,
     * in the reference time of the address.
     *
     * @return Integer: The number of seconds since Epoch.
     */
    public Integer getRemoteTime() {
        return this.remote_time;
    }

    /**
     * The getLocalTime method returns the date of the last heartbeat message,
     * in the reference time of the local Supvisors.
     *
     * @return Integer: The number of seconds since Epoch.
     */
   public Integer getLocalTime() {
        return this.local_time;
    }

    /**
     * The getSequenceCounter method returns the TICK counter, i.e. the number
     * of TICK events received by Supvisors from Supervisor for this node,
     * since this Supervisor instance has been started.
     *
     * @return Integer: The number of TICK events received.
     */
   public Integer getSequenceCounter() {
        return this.sequence_counter;
    }

    /**
     * The getLoading method returns the loading of the address.
     *
     * @return State: The loading in percent.
     */
    public Integer getLoading() {
        return this.loading;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsAddressInfo(name=" + this.address_name
            + " state=" + this.statename + " remoteTime=" + this.remote_time
            + " localTime=" + this.local_time + " loading=" + this.loading
            + " sequenceCounter=" + this.sequence_counter + ")";
    }

}
