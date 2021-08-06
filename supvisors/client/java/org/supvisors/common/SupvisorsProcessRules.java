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

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
    
/**
 * The Class SupvisorsProcessRules.
 *
 * It gives a structured form to the process rules received from a XML-RPC.
 */
public class SupvisorsProcessRules implements SupvisorsAnyInfo {

    /** The process namespec. */
    private String namespec;

    /** The name of the process' application. */
    private String applicationName;

    /** The process name. */
    private String processName;

    /**
     * The applicable nodes.
     * If all known nodes are applicable, '*' is used.
     */
    private List nodes;

    /** The starting order in the application starting. */
    private Integer startSequence;

    /** The stopping order in the application stopping. */
    private Integer stopSequence;

    /**
     * A status telling if this process is required in the application.
     * Impact on the majorFailure / minorFailure of the application.
     */
    private Boolean required;

    /**
     * A status telling if the Supvisors starter has to wait for this process to exit
     * before starting the next process.
     */
    private Boolean waitExit;

    /** The loading of the process, as declared in the Supvisors rules file. */
    private Integer expectedLoading;

    /** The strategy applied when the process crashes. */
    private RunningFailureStrategy runningFailureStrategy;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsProcessRules(HashMap rulesInfo)  {
        this.processName = (String) rulesInfo.get("process_name");
        this.applicationName = (String) rulesInfo.get("application_name");
        this.namespec = DataConversion.stringsToNamespec(this.applicationName, this.processName);
        Object[] nodes = (Object[]) rulesInfo.get("addresses");
        this.nodes = Arrays.asList(nodes);
        this.startSequence = (Integer) rulesInfo.get("start_sequence");
        this.stopSequence = (Integer) rulesInfo.get("stop_sequence");
        this.required = (Boolean) rulesInfo.get("required");
        this.waitExit = (Boolean) rulesInfo.get("wait_exit");
        this.expectedLoading = (Integer) rulesInfo.get("expected_loading");
        this.runningFailureStrategy = RunningFailureStrategy.valueOf((String) rulesInfo.get("running_failure_strategy"));
    }

    /**
     * The getApplicationName method returns the name of the process' application'.
     *
     * @return String: The namespec of the application.
     */
    public String getApplicationName() {
        return this.applicationName;
    }

    /**
     * The getProcessName method returns the name of the process.
     *
     * @return String: The namespec of the application.
     */
    public String getProcessName() {
        return this.processName;
    }

    /**
     * The getName method returns the namespec of the process.
     *
     * @return String: The namespec of the application.
     */
    public String getName() {
        return this.namespec;
    }

    /**
     * The getNodes method returns the addresses where the process can be started.
     *
     * @return List: The list of nodes.
     */
    public List getNodes() {
        return this.nodes;
    }

    /**
     * The getStartSequence method returns the starting order of the process in the application starting.
     *
     * @return Integer: The starting order.
     */
    public Integer getStartSequence() {
        return this.startSequence;
    }

    /**
     * The getStartSequence method returns the stopping order of the process in the application stopping.
     *
     * @return Integer: The stopping order.
     */
    public Integer getStopSequence() {
        return this.stopSequence;
    }

    /**
     * The isRequired method returns the required status of the process.
     *
     * @return Boolean: The required status.
     */
    public Boolean isRequired() {
        return this.required;
    }

    /**
     * The hasToWaitExit method returns True if the Supvisors starter has to wait
     * for this process to exit before starting the next processes.
     *
     * @return Boolean: The wait exit status.
     */
    public Boolean hasToWaitExit() {
        return this.waitExit;
    }

    /**
     * The getExpectedLoading method returns the declared loading of the process.
     *
     * @return Integer: The loading.
     */
    public Integer getExpectedLoading() {
        return this.expectedLoading;
    }

    /**
     * The getRunningFailureStrategy method returns the strategy applied when the process crashes.
     *
     * @return RunningFailureStrategy: The strategy.
     */
    public RunningFailureStrategy getRunningFailureStrategy() {
        return this.runningFailureStrategy;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsProcessrules(namespec=" + this.namespec
            + " nodes=" + this.nodes + " startSequence=" + this.startSequence
            + " stopSequence=" + this.stopSequence + " required=" + this.required
            + " waitExit=" + this.waitExit + " expectedLoading=" + this.expectedLoading
            + " runningFailureStrategy=" + this.runningFailureStrategy + ")";
    }

}
