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

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashMap;
import com.google.gson.annotations.SerializedName;

/**
 * The Class SupvisorsInstanceInfo.
 *
 * It gives a structured form to the Supvisors Instance information received from a XML-RPC.
 */
public class SupvisorsInstanceInfo implements SupvisorsAnyInfo {

    /**
     * The State enumeration for a node.
     *
     * UNKNOWN:   used at initialization, before any heartbeat message is received from this Supvisors instance.
     * CHECKING:  used when the local Supvisors checks the isolation status of this Supvisors instance.
     * RUNNING:   used when the local Supvisors receives heartbeat messages from this Supvisors instance.
     * SILENT:    used when the local Supvisors does not receive any heartbeat message from this Supvisors instance.
     * ISOLATING: used when the local Supvisors is about to disconnect this Supvisors instance.
     * ISOLATED:  used when the local Supvisors has actually disconnected this Supvisors instance.
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

    /** The identifier of the Supvisors instance. */
    private String identifier;

    /** The node state. */
    private State statename;

    /** The date of the last heartbeat message, as received. */
    private Integer remote_time;

    /** The date of the last heartbeat message, in the local reference time. */
    private Integer local_time;

    /** The TICK counter. */
    private Integer sequence_counter;

    /**
     * The current declared loading of the node.
     * Note: This is not a measurement. It corresponds to the sum of the declared loading of the running processes.
     */
    private Integer loading;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap instanceInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsInstanceInfo(HashMap instanceInfo)  {
        this.identifier = (String) instanceInfo.get("identifier");
        this.statename = State.valueOf((String) instanceInfo.get("statename"));
        this.remote_time = (Integer) instanceInfo.get("remote_time");
        this.local_time = (Integer) instanceInfo.get("local_time");
        this.sequence_counter = (Integer) instanceInfo.get("sequence_counter");
        this.loading = (Integer) instanceInfo.get("loading");
    }

    /**
     * The getName method uses the getIdentifier method.
     *
     * @return String: The identifier of the Supvisors instance.
     */
    public String getName() {
        return this.getIdentifier();
    }

    /**
     * The getIdentifier method returns the identifier of the Supvisors instance.
     *
     * @return String: The identifier of the Supvisors instance.
     */
    public String getIdentifier() {
        return this.identifier;
    }

    /**
     * The getState method returns the state of the node.
     *
     * @return State: The state of the node.
     */
    public State getState() {
        return this.statename;
    }

    /**
     * The getRemoteTime method returns the date of the last heartbeat message,
     * in the reference time of the remote node.
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
     * The getLoading method returns the loading of the node.
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
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
        return "SupvisorsInstanceInfo(identifier=" + this.identifier
            + " state=" + this.statename + " remoteTime=\"" + sdf.format(new Date(this.remote_time * 1000L)) + "\""
            + " localTime=\"" + sdf.format(new Date(this.local_time * 1000L)) + "\""
            + " loading=" + this.loading + " sequenceCounter=" + this.sequence_counter + ")";
    }

}
