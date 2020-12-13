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


/**
 * The Class SupvisorsProcessInfo.
 *
 * It gives a structured form to the process information received from a XML-RPC.
 */
public class SupvisorsProcessInfo implements SupvisorsAnyInfo {

    /** The name of the process' application. */
    private String application_name;

    /** The process name. */
    private String process_name;

    /** The process state. */
    private ProcessState statecode;

    /** A status telling if the process has exited expectantly. */
    private Boolean expected_exit;

    /** The date of the last event received for this process. */
    private Integer last_event_time;

    /** The addresses where the process is running. */
    private List<String> addresses;
    
    /** The extra arguments passed to the command line. */
    private String extra_args;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap processInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsProcessInfo(HashMap processInfo)  {
        this.process_name = (String) processInfo.get("process_name");
        this.application_name = (String) processInfo.get("application_name");
        this.statecode = ProcessState.valueOf((String) processInfo.get("statename"));
        this.expected_exit = (Boolean) processInfo.get("expected_exit");
        this.last_event_time = (Integer) processInfo.get("last_event_time");
        this.addresses = DataConversion.arrayToStringList((Object[]) processInfo.get("addresses"));
        this.extra_args = (String) processInfo.get("extra_args");
   }

    /**
     * The getApplicationName method returns the name of the process' application.
     *
     * @return String: The name of the application.
     */
    public String getApplicationName() {
        return this.application_name;
    }

    /**
     * The getProcessName method returns the name of the process.
     *
     * @return String: The name of the process.
     */
    public String getProcessName() {
        return this.process_name;
    }

    /**
     * The getName method returns the namespec of the process.
     *
     * @return String: The namespec of the process.
     */
    public String getName() {
        return DataConversion.stringsToNamespec(this.application_name, this.process_name);
    }

    /**
     * The getState method returns the state of the process.
     *
     * @return ProcessState: The state of the process.
     */
    public ProcessState getState() {
        return this.statecode;
    }

    /**
     * The getExpectedExitStatus method returns the exit status of the process.
     * It only makes sense when the process is in EXITED state.
     *
     * @return Boolean: The exit status.
     */
    public Boolean getExpectedExitStatus() {
        return this.expected_exit;
    }

    /**
     * The getLastEventTime method returns the date of the last event received for the process.
     *
     * @return Integer: The date of the last event received.
     */
    public Integer getLastEventTime() {
        return this.last_event_time;
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
     * The getExtraArgs method returns the exta arguments passed to the
     * command line.
     *
     * @return String: The arguments.
     */
    public String getExtraArgs() {
        return this.extra_args;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsProcessInfo(namespec=" + this.getName()
            + " applicationName=" + this.application_name
            + " processName=" + this.process_name
            + " state=" + this.statecode
            + " expectedExitStatus=" + this.expected_exit
            + " lastEventTime=" + this.last_event_time
            + " addresses=" + this.addresses
            + " extraArgs=" + this.extra_args + ")";
    }

}
