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

    /** The managed status of the application. */
    private Boolean isManaged;

    /** The distribution status of the application. */
    private Boolean isDistributed;

    /**
     * The identifiers of the applicable Supvisors instances when the application cannot be distributed.
     * If all known Supvisors instances are applicable, '*' is used.
     */
    private List identifiers;

    /** The starting order in the application starting. */
    private Integer startSequence;

    /** The stopping order in the application stopping. */
    private Integer stopSequence;

    /** The strategy applied to choose nodes at application starting time. */
    private StartingStrategy startingStrategy;

    /** The strategy applied when a process crashes at application starting time. */
    private StartingFailureStrategy startingFailureStrategy;

    /** The strategy applied when a process crashes at application running time. */
    private RunningFailureStrategy runningFailureStrategy;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap rulesInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsApplicationRules(HashMap rulesInfo)  {
        this.applicationName = (String) rulesInfo.get("application_name");
        this.isManaged = (Boolean) rulesInfo.get("managed");
        if (this.isManaged) {
            this.isDistributed = (Boolean) rulesInfo.get("distributed");
            if (!this.isDistributed) {
                Object[] identifiers = (Object[]) rulesInfo.get("identifiers");
                this.identifiers = Arrays.asList(identifiers);
            }
            this.startSequence = (Integer) rulesInfo.get("start_sequence");
            this.stopSequence = (Integer) rulesInfo.get("stop_sequence");
            this.startingStrategy = StartingStrategy.valueOf((String) rulesInfo.get("starting_strategy"));
            this.startingFailureStrategy = StartingFailureStrategy.valueOf((String) rulesInfo.get("starting_failure_strategy"));
            this.runningFailureStrategy = RunningFailureStrategy.valueOf((String) rulesInfo.get("running_failure_strategy"));
        }
    }

    /**
     * The getName method uses the getApplicationName method.
     *
     * @return String: The name of the application.
     */
    public String getName() {
        return this.getApplicationName();
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
     * The isManaged method returns the managed status of the application in Supvisors.
     *
     * @return Boolean: The managed status.
     */
    public Boolean isManaged() {
        return this.isManaged;
    }

    /**
     * The isDistributed method returns the distribution status of the application in Supvisors.
     *
     * @return Boolean: The distribution status.
     */
    public Boolean isDistributed() {
        return this.isDistributed;
    }

    /**
     * The getIdentifiers method returns the identifiers of the Supvisors instances
     * where the application processes can be started when the application cannot be distributed.
     *
     * @return List: The list of identifiers.
     */
    public List getIdentifiers() {
        return this.identifiers;
    }

    /**
     * The getStartSequence method returns the starting order of the application when starting all the applications.
     *
     * @return Integer: The starting order.
     */
    public Integer getStartSequence() {
        return this.startSequence;
    }

    /**
     * The getStartSequence method returns the stopping order of the application when stopping all the applications.
     *
     * @return Integer: The stopping order.
     */
    public Integer getStopSequence() {
        return this.stopSequence;
    }

    /**
     * The getStartingStrategy method returns the strategy applied to choose nodes
     *  when the application is starting.
     *
     * @return StartingStrategy: The strategy.
     */
    public StartingStrategy getStartingStrategy() {
        return this.startingStrategy;
    }

    /**
     * The getStartingFailureStrategy method returns the strategy applied if the process crashes
     * when the application is starting.
     *
     * @return StartingFailureStrategy: The strategy.
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
        String rulesString = "SupvisorsApplicationRules(applicationName=" + this.applicationName
            + " managed=" + this.isManaged;
        if (this.isManaged) {
            rulesString += " distributed=" + this.isDistributed;
            if (!this.isDistributed) {
                rulesString += " nodes=" + this.nodes;
            }
            rulesString += " startSequence=" + this.startSequence + " stopSequence=" + this.stopSequence
                + " startingStrategy=" + this.startingStrategy
                + " startingFailureStrategy=" + this.startingFailureStrategy
                + " runningFailureStrategy=" + this.runningFailureStrategy;
        }
        rulesString += ")";
        return rulesString;
    }

}
