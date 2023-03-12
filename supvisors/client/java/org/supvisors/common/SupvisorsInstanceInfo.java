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

    /** The identifier of the Supvisors instance. */
    private String identifier;

    /** The name of the node where the Supvisors instance is running. */
    private String node_name;

    /** The HTTP port of the Supvisors instance. */
    private Integer port;

    /** The instance state. */
    private SupvisorsInstanceState statename;

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

    /** True if one of the local processes has crashed or has exited unexpectedly. */
    private Boolean process_failure;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap instanceInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsInstanceInfo(HashMap instanceInfo)  {
        this.identifier = (String) instanceInfo.get("identifier");
        this.node_name = (String) instanceInfo.get("node_name");
        this.port = (Integer) instanceInfo.get("port");
        this.statename = SupvisorsInstanceState.valueOf((String) instanceInfo.get("statename"));
        this.remote_time = (Integer) instanceInfo.get("remote_time");
        this.local_time = (Integer) instanceInfo.get("local_time");
        this.sequence_counter = (Integer) instanceInfo.get("sequence_counter");
        this.loading = (Integer) instanceInfo.get("loading");
        this.process_failure = (Boolean) instanceInfo.get("process_failure");
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
     * The getNodeName method returns the name of the node where the Supvisors instance is running.
     *
     * @return String: The node name of the Supvisors instance.
     */
    public String getNodeName() {
        return this.node_name;
    }

    /**
     * The getPort method returns the HTTP port of the Supvisors instance.
     *
     * @return Integer: The HTTP port.
     */
    public Integer getPort() {
        return this.port;
    }

    /**
     * The getState method returns the state of the node.
     *
     * @return SupvisorsInstanceState: The state of the node.
     */
    public SupvisorsInstanceState getState() {
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
     * The hasProcessFailure method returns True .
     *
     * @return State: The loading in percent.
     */
    public Boolean hasProcessFailure() {
        return this.process_failure;
    }

    /**
     * The toString method returns True if one of the local processes has crashed or has exited unexpectedly.
     *
     * @return Boolean: The process failure status.
     */
    public String toString() {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
        return "SupvisorsInstanceInfo(identifier=" + this.identifier
            + " node_name=" + this.node_name
            + " port=" + this.port
            + " state=" + this.statename
            + " sequenceCounter=" + this.sequence_counter
            + " remoteTime=\"" + sdf.format(new Date(this.remote_time * 1000L)) + "\""
            + " localTime=\"" + sdf.format(new Date(this.local_time * 1000L)) + "\""
            + " loading=" + this.loading
            + " processFailure=" + this.process_failure + ")";
    }

}
