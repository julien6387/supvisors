/*
 * Copyright 2017 Julien LE CLEACH
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
 * The Class SupvisorsApplicationRules.
 *
 * It gives a structured form to the application rules received from a XML-RPC.
 */
public class SupvisorsApplicationRules implements SupvisorsAnyInfo {

    /** The name of the process' application. */
    private String applicationName;

    /** The starting order in the application starting. */
    private Integer startSequence;

    /** The stopping order in the application stopping. */
    private Integer stopSequence;

    /** The strategy applied when a process crashes at application starting time. */
    private StartingFailureStrategy startingFailureStrategy;

    /** The strategy applied when a process crashes at application running time. */
    private RunningFailureStrategy runningFailureStrategy;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsApplicationRules(HashMap rulesInfo)  {
        this.applicationName = (String) rulesInfo.get("application_name");
        this.startSequence = (Integer) rulesInfo.get("start_sequence");
        this.stopSequence = (Integer) rulesInfo.get("stop_sequence");
        this.startingFailureStrategy = StartingFailureStrategy.valueOf((String) rulesInfo.get("starting_failure_strategy"));
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
     * The getName method returns the name of the application.
     *
     * @return String: The name of the application.
     */
    public String getName() {
        return this.applicationName;
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
     * The getStartingFailureStrategy method returns the strategy applied if the process crashes
     * when the application is starting.
     *
     * @return RunningFailureStrategy: The strategy.
     */
    public StartingFailureStrategy getStartingFailureStrategy() {
        return this.startingFailureStrategy;
    }

    /**
     * The getRunningFailureStrategy method returns the strategy applied if the process crashes
     * when the application is running.
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
        return "SupvisorsApplicationRules(applicationName=" + this.applicationName
            + " startSequence=" + this.startSequence + " stopSequence=" + this.stopSequence
            + " startingFailureStrategy=" + this.startingFailureStrategy 
            + " runningFailureStrategy=" + this.runningFailureStrategy + ")";
    }

}
