/*
 * Copyright 2024 Julien LE CLEACH
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
import java.util.List;


/**
 * The Class SupvisorsDistributionInfo.
 *
 * It gives a structured form to the process information received from a XML-RPC.
 */
public class SupvisorsDistributionInfo implements SupvisorsAnyInfo {

    /** The name of the process' application. */
    private String application_name;

    /** The process name. */
    private String process_name;

    /** The predicted process state. */
    private ProcessState state;

    /** The reason of the starting failure if state is FATAL. */
    private String forced_reason;

    /** The identifiers of the Supvisors instances where the process is expected to run. */
    private List<String> running_identifiers;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap processInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsDistributionInfo(HashMap processInfo)  {
        this.process_name = (String) processInfo.get("process_name");
        this.application_name = (String) processInfo.get("application_name");
        this.state = ProcessState.valueOf((String) processInfo.get("state"));
        this.forced_reason = (String) processInfo.get("forced_reason");
        this.running_identifiers = DataConversion.arrayToStringList((Object[]) processInfo.get("running_identifiers"));
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
     * The getState method returns the predicted state of the process.
     *
     * @return ProcessState: The predicted state of the process.
     */
    public ProcessState getState() {
        return this.state;
    }

    /**
     * The getForcedReason method returns the reason of the expected starting failure in the event where the process
     * cannot be started (state is expected to be FATAL).
     *
     * @return String: The reason of the failure.
     */
    public String getForcedReason() {
        return this.forced_reason;
    }

    /**
     * The getRunningIdentifiers method returns the list of identifiers of the Supvisors instances
     * where the process is expected to run (one identifier only expected, unless the process is already conflicting).
     *
     * @return List: The identifiers list of Supvisors instances.
     */
    public List getRunningIdentifiers() {
        return this.running_identifiers;
    }

    /**
     * The toString method returns a printable form of the contents of the SupvisorsDistributionInfo instance.
     *
     * @return String: The contents of the SupvisorsDistributionInfo instance.
     */
    public String toString() {
        return "SupvisorsDistributionInfo(namespec=" + this.getName()
            + " applicationName=" + this.application_name
            + " processName=" + this.process_name
            + " state=" + this.state
            + " forcedReason=\"" + this.forced_reason + "\""
            + " runningIdentifiers=" + this.running_identifiers + ")";
    }

}
