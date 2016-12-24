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
import org.json.JSONObject;


/**
 * The Class SupvisorsAddressInfo.
 *
 * It gives a structured form to the address information received from a XML-RPC.
 */
public class SupvisorsAddressInfo implements SupvisorsAnyInfo {

    /**
     * The State enumeration for an address.
     *
     * UNKNOWN is used at initialization, before any heartbeat message is received from this address.
     * SILENT is used when the local Supvisors does not receive any heartbeat message from this address.
     * RUNNING is used when the local Supvisors receives heartbeat messages from this address.
     * ISOLATED is used when the local Supvisors has disconnected this address.
     */
    public enum State {
        UNKNOWN,
        SILENT,
        RUNNING,
        ISOLATED;
    }

    /** The address name. */
    private String name;

    /** The address state. */
    private State state;

    /** The date of the last heartbeat message, as received. */
    private Integer remoteTime;

    /** The date of the last heartbeat message, in the local reference time. */
    private Integer localTime;

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
        this.name = (String) addressInfo.get("address_name");
        this.state = State.valueOf((String) addressInfo.get("statename"));
        this.remoteTime = (Integer) addressInfo.get("remote_time");
        this.localTime = (Integer) addressInfo.get("local_time");
        this.loading = (Integer) addressInfo.get("loading");
    }

    /**
     * The constructor gets all information from a JSON string.
     *
     * @param String json: The untyped structure got from the event subscriber.
     */
    public SupvisorsAddressInfo(final String json) {
        JSONObject obj = new JSONObject(json);
        this.name = obj.getString("address_name");
        this.state = State.valueOf(obj.getString("statename"));
        this.remoteTime = obj.getInt("remote_time");
        this.localTime = obj.getInt("local_time");
        this.loading = obj.getInt("loading");
    }

    /**
     * The getName method returns the name of the address.
     *
     * @return String: The name of the address.
     */
    public String getName() {
        return this.name;
    }

    /**
     * The getState method returns the state of the address.
     *
     * @return State: The state of the address.
     */
    public State getState() {
        return this.state;
    }

    /**
     * The getRemoteTime method returns the date of the last heartbeat message,
     * in the reference time of the address.
     *
     * @return Integer: The number of seconds since Epoch.
     */
    public Integer getRemoteTime() {
        return this.remoteTime;
    }

     /**
     * The getLocalTime method returns the date of the last heartbeat message,
     * in the reference time of the local Supvisors.
     *
     * @return Integer: The number of seconds since Epoch.
     */
   public Integer getLocalTime() {
        return this.localTime;
    }

    /**
     * The getLoading method returns the loading of the address.
     *
     * @return State: The loadinf in percent.
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
        return "SupvisorsAddressInfo(name=" + this.name
            + " state=" + this.state + " remoteTime=" + this.remoteTime
            + " localTime=" + this.localTime + " loading=" + this.loading + ")";
    }

}
