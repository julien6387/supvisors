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
import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;


/**
 * The Class SupvisorsProcessInfo.
 *
 * It gives a structured form to the process information received from a XML-RPC.
 */
public class SupvisorsProcessInfo implements SupvisorsAnyInfo {

    /** The process namespec. */
    private String namespec;

    /** The name of the process' application. */
    private String applicationName;

    /** The process name. */
    private String processName;

    /** The process state. */
    private ProcessState state;

    /** A status telling if the process has exited expectantly. */
    private Boolean expectedExitStatus;

    /** The date of the last event received for this process. */
    private Integer lastEventTime;

    /** The addresses where the process is running. */
    private List<String> addresses;
    
    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap processInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsProcessInfo(HashMap processInfo)  {
        this.processName = (String) processInfo.get("process_name");
        this.applicationName = (String) processInfo.get("application_name");
        this.namespec = DataConversion.stringsToNamespec(this.applicationName, this.processName);
        this.state = ProcessState.valueOf((String) processInfo.get("statename"));
        this.expectedExitStatus = (Boolean) processInfo.get("expected_exit");
        this.lastEventTime = (Integer) processInfo.get("last_event_time");
        this.addresses = DataConversion.arrayToStringList((Object[]) processInfo.get("addresses"));
    }

    /**
     * This constructor gets all information from a JSON string.
     *
     * @param String json: The untyped structure got from the event subscriber.
     */
    public SupvisorsProcessInfo(final String json) {
        JSONObject obj = new JSONObject(json);
        this.processName = obj.getString("process_name");
        this.applicationName = obj.getString("application_name");
        this.namespec = DataConversion.stringsToNamespec(this.applicationName, this.processName);
        this.state = ProcessState.valueOf(obj.getString("statename"));
        this.expectedExitStatus = obj.getBoolean("expected_exit");
        this.lastEventTime = obj.getInt("last_event_time");
        // parse addresses
        JSONArray addresses = obj.getJSONArray("addresses");
        this.addresses = new ArrayList<String>(addresses.length());
        for (int i=0 ; i<addresses.length() ; i++) {
            this.addresses.add(addresses.getString(i));
        }
    }

    /**
     * The getApplicationName method returns the name of the process' application.
     *
     * @return String: The name of the application.
     */
    public String getApplicationName() {
        return this.applicationName;
    }

    /**
     * The getProcessName method returns the name of the process.
     *
     * @return String: The name of the process.
     */
    public String getProcessName() {
        return this.processName;
    }

    /**
     * The getName method returns the namespec of the process.
     *
     * @return String: The namespec of the process.
     */
    public String getName() {
        return this.namespec;
    }

    /**
     * The getState method returns the state of the process.
     *
     * @return ProcessState: The state of the process.
     */
    public ProcessState getState() {
        return this.state;
    }

    /**
     * The getExpectedExitStatus method returns the exit status of the process.
     * It only makes sense when the process is in EXITED state.
     *
     * @return Boolean: The exit status.
     */
    public Boolean getExpectedExitStatus() {
        return this.expectedExitStatus;
    }

    /**
     * The getLastEventTime method returns the date of the last event received for the process.
     *
     * @return Integer: The date of the last event received.
     */
    public Integer getLastEventTime() {
        return this.lastEventTime;
    }

    /**
     * The getAddresses method returns the list of addresses where the process is running.
     *
     * @return List: The list of addresses.
     */
    public List getAddresses() {
        return this.addresses;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsProcessInfo(namespec=" + this.namespec
            + " applicationName=" + this.applicationName + " processName=" + this.processName
            + " state=" + this.state + " expectedExitStatus=" + this.expectedExitStatus
            + " lastEventTime=" + this.lastEventTime + " addresses=" + this.addresses + ")";
    }

}
