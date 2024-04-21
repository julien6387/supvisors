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

    /** The identifier of the Supervisor instance. */
    private String nick_identifier;

    /** The name of the node where the Supvisors instance is running. */
    private String node_name;

    /** The HTTP port of the Supvisors instance. */
    private Integer port;

    /** The instance state. */
    private SupvisorsInstanceState statename;

    /** The remote TICK counter. */
    private Integer remote_sequence_counter;

    /** The monotonic time of the last heartbeat message, as received. */
    private Double remote_mtime;

    /** The time of the last heartbeat message, as received. */
    private Integer remote_time;

    /** The local TICK counter at the reception time of the remote TICK counter. */
    private Integer local_sequence_counter;

    /** The monotonic time of the last heartbeat message, in the local reference time. */
    private Double local_mtime;

    /** The time of the last heartbeat message, in the local reference time. */
    private Integer local_time;

    /**
     * The current declared loading of the node.
     * Note: This is not a measurement. It corresponds to the sum of the declared loading of the running processes.
     */
    private Integer loading;

    /** True if one of the local processes has crashed or has exited unexpectedly. */
    private Boolean process_failure;

    /** The instance state. */
    private SupvisorsState fsm_statename;

    /** The instance discovery mode. */
    private Boolean discovery_mode;

    /** True if the Supvisors instance has starting jobs in progress. */
    private Boolean starting_jobs;

    /** True if the Supvisors instance has stopping jobs in progress. */
    private Boolean stopping_jobs;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap instanceInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsInstanceInfo(HashMap instanceInfo)  {
        this.identifier = (String) instanceInfo.get("identifier");
        this.nick_identifier = (String) instanceInfo.get("nick_identifier");
        this.node_name = (String) instanceInfo.get("node_name");
        this.port = (Integer) instanceInfo.get("port");
        this.statename = SupvisorsInstanceState.valueOf((String) instanceInfo.get("statename"));
        this.remote_sequence_counter = (Integer) instanceInfo.get("remote_sequence_counter");
        this.remote_mtime = (Double) instanceInfo.get("remote_mtime");
        this.remote_time = (Integer) instanceInfo.get("remote_time");
        this.remote_sequence_counter = (Integer) instanceInfo.get("local_sequence_counter");
        this.local_mtime = (Double) instanceInfo.get("local_mtime");
        this.local_time = (Integer) instanceInfo.get("local_time");
        this.loading = (Integer) instanceInfo.get("loading");
        this.process_failure = (Boolean) instanceInfo.get("process_failure");
        this.fsm_statename = SupvisorsState.valueOf((String) instanceInfo.get("fsm_statename"));
        this.discovery_mode = (Boolean) instanceInfo.get("discovery_mode");
        this.starting_jobs = (Boolean) instanceInfo.get("starting_jobs");
        this.stopping_jobs = (Boolean) instanceInfo.get("stopping_jobs");
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
     * The getNickIdentifier method returns the identifier of the Supervisor instance.
     *
     * @return String: The identifier of the Supervisor instance.
     */
    public String getNickIdentifier() {
        return this.nick_identifier;
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
     * The getRemoteSequenceCounter method returns the TICK counter, i.e. the number
     * of TICK events received by Supvisors from Supervisor for this node,
     * since this Supervisor instance has been started.
     *
     * @return Integer: The number of TICK events received.
     */
    public Integer getRemoteSequenceCounter() {
        return this.remote_sequence_counter;
    }

    /**
     * The getRemoteMonotonicTime method returns the monotonic time of the last heartbeat message,
     * in the reference time of the remote node.
     *
     * @return Double: The number of seconds since the remote node startup.
     */
    public Double getRemoteMonotonicTime() {
        return this.remote_mtime;
    }

    /**
     * The getRemoteTime method returns the time of the last heartbeat message,
     * in the reference time of the remote node.
     *
     * @return Integer: The number of seconds since Epoch.
     */
    public Integer getRemoteTime() {
        return this.remote_time;
    }

    /**
     * The getLocalSequenceCounter method returns the local TICK counter, when the latest remote TICK was received
     * from the remote node.
     *
     * @return Integer: The number of TICK events received.
     */
    public Integer getLocalSequenceCounter() {
        return this.local_sequence_counter;
    }

    /**
     * The getLocalMonotonicTime method returns the monotonic time taken when the latest TICK was received
     * from the remote node.
     *
     * @return Double: The number of seconds since the local node startup.
     */
    public Double getLocalMonotonicTime() {
        return this.local_mtime;
    }

    /**
     * The getLocalTime method returns the time taken when the latest TICK was received from the remote node.
     *
     * @return Integer: The number of seconds since Epoch.
     */
    public Integer getLocalTime() {
        return this.local_time;
    }

    /**
     * The getLoading method returns the loading of the node.
     *
     * @return Integer: The loading in percent.
     */
    public Integer getLoading() {
        return this.loading;
    }

    /**
     * The hasProcessFailure method returns True if any process is in FATAL or unexpected EXITED state.
     *
     * @return Boolean: The process failure status.
     */
    public Boolean hasProcessFailure() {
        return this.process_failure;
    }

    /**
     * The getSupvisorsState method returns the state of Supvisors.
     *
     * @return SupvisorsState: The state of Supvisors.
     */
    public SupvisorsState getSupvisorsState() {
        return this.fsm_statename;
    }

    /**
     * The inDiscoveryMode method returns True if the Supvisors instance is in discovery mode.
     *
     * @return Boolean: The discovery mode status.
     */
    public Boolean inDiscoveryMode() {
        return this.discovery_mode;
    }

    /**
     * The hasStartingJobs method returns True if the Supvisors instance has jobs in progress in its Starter.
     *
     * @return Boolean: The starting jobs progress.
     */
    public Boolean hasStartingJobs() {
        return this.starting_jobs;
    }

    /**
     * The hasStoppingJobs method returns True if the Supvisors instance has jobs in progress in its Stopper.
     *
     * @return Boolean: The stopping jobs progress.
     */
    public Boolean hasStoppingJobs() {
        return this.stopping_jobs;
    }

    /**
     * The toString method returns True if one of the local processes has crashed or has exited unexpectedly.
     *
     * @return Boolean: The process failure status.
     */
    public String toString() {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
        return "SupvisorsInstanceInfo(identifier=" + this.identifier
            + " nickIdentifier=" + this.nick_identifier
            + " nodeName=" + this.node_name
            + " port=" + this.port
            + " state=" + this.statename
            + " remoteSequenceCounter=" + this.remote_sequence_counter
            + " remoteMonotonicTime=" + this.remote_mtime
            + " remoteTime=\"" + sdf.format(new Date(this.remote_time * 1000L)) + "\""
            + " localSequenceCounter=" + this.local_sequence_counter
            + " localMonotonicTime=" + this.local_mtime
            + " localTime=\"" + sdf.format(new Date(this.local_time * 1000L)) + "\""
            + " loading=" + this.loading
            + " processFailure=" + this.process_failure
            + " supvisorsState=" + this.fsm_statename
            + " discoveryMode=" + this.discovery_mode
            + " startingJobs=" + this.starting_jobs
            + " stoppingJobs=" + this.stopping_jobs + ")";
    }

}
