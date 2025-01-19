/*
 * Copyright 2025 Julien LE CLEACH
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

/**
 * The Class SupvisorsCommonStateModes.
 *
 * Common part for SupvisorsStatus and SupvisorsStateModes.
 */

public class SupvisorsCommonStateModes implements SupvisorsAnyInfo {

    /** The identifier of the Supvisors instance. */
    protected String identifier;

    /** The nickname of the Supervisor instance. */
    protected String nick_identifier;

    /** The monotonic time of the message, in the local reference time. */
    protected Double now_monotonic;

    /** The Supvisors state, as seen by the Supvisors instance. */
    protected SupvisorsState fsm_statename;

    /** The identifier of the Supervisor Master instance. */
    protected String master_identifier;

    /** The Supvisors degraded status. */
    protected Boolean degraded_mode;

    /** The Supvisors discovery mode. */
    protected Boolean discovery_mode;

    /** All Supvisors instance states per identifier. */
    protected HashMap<String, SupvisorsInstanceState> instance_states;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap instanceInfo: The untyped structure got from the XML-RPC.
     */
    @SuppressWarnings({"unchecked"})
    public SupvisorsCommonStateModes(HashMap info)  {
        this.identifier = (String) info.get("identifier");
        this.nick_identifier = (String) info.get("nick_identifier");
        this.now_monotonic = (Double) info.get("now_monotonic");
        this.fsm_statename = SupvisorsState.valueOf((String) info.get("fsm_statename"));
        this.master_identifier = (String) info.get("master_identifier");
        this.degraded_mode = (Boolean) info.get("degraded_mode");
        this.discovery_mode = (Boolean) info.get("discovery_mode");
        // no safe way to convert an Object to HashMap
        this.instance_states = (HashMap<String, SupvisorsInstanceState>) info.get("instance_states");
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
     * The getNickIdentifier method returns the nickname of the Supervisor instance.
     *
     * @return String: The nickname of the Supervisor instance.
     */
    public String getNickIdentifier() {
        return this.nick_identifier;
    }

    /**
     * The getSupvisorsIdentifier method returns the identification of the Supvisors instance,
     * as a SupvisorsIdentifier instance.
     *
     * @return SupvisorsIdentifier: a SupvisorsIdentifier instance.
     */
    public SupvisorsIdentifier getSupvisorsIdentifier() {
        return new SupvisorsIdentifier(this.identifier, this.nick_identifier);
    }

    /**
     * The getNowMonotonic method returns the monotonic time of the event.
     *
     * @return Double: The number of seconds since the local node startup.
     */
    public Double getNowMonotonic() {
        return this.now_monotonic;
    }

    /**
     * The getState method returns the state of Supvisors.
     *
     * @return SupvisorsState: The state of Supvisors.
     */
    public SupvisorsState getState() {
        return this.fsm_statename;
    }

    /**
     * The inDegradedMode method returns True if the Supvisors instance is in degraded mode.
     *
     * @return Boolean: The degraded mode status.
     */
    public Boolean inDegradedMode() {
        return this.degraded_mode;
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
     * The getInstanceStates method returns all Supvisors instance states per identifier.
     *
     * @return HashMap<String, SupvisorsInstanceState>: The Supvisors instances states.
     */
    public HashMap<String, SupvisorsInstanceState> getInstanceStates() {
        return this.instance_states;
    }

    /**
     * The toString method returns a printable form of the SupvisorsStatus instance.
     *
     * @return String: The contents of the SupvisorsStatus.
     */
    public String toString() {
        return "identifier=" + this.identifier
            + " nickIdentifier=" + this.nick_identifier
            + " nowMonotonic=" + this.now_monotonic
            + " state=" + this.fsm_statename
            + " degradedMode=" + this.degraded_mode
            + " discoveryMode=" + this.discovery_mode
            + " instance_states=" + this.instance_states;
    }

}
