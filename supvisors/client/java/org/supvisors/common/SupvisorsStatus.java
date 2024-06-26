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
 * The Class SupvisorsStatus.
 *
 * It gives a structured form to the supervisor state received from a XML-RPC.
 */
public class SupvisorsStatus {

    /** The Supvisors state. */
    private SupvisorsState fsm_statename;

    /** The instance discovery mode. */
    private Boolean discovery_mode;

    /** The identifiers of where starting jobs are in progress. */
    private List starting_jobs;

    /** The identifiers of where stopping jobs are in progress. */
    private List stopping_jobs;

    /**
     * The constructor gets the state information from an HashMap.
     *
     * @param HashMap stateInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsStatus(HashMap stateInfo)  {
        this.fsm_statename = SupvisorsState.valueOf((String) stateInfo.get("fsm_statename"));
        this.discovery_mode = (Boolean) stateInfo.get("discovery_mode");
        Object[] startingJobs = (Object[]) stateInfo.get("starting_jobs");
        this.starting_jobs = Arrays.asList(startingJobs);
        Object[] stoppingJobs = (Object[]) stateInfo.get("stopping_jobs");
        this.stopping_jobs = Arrays.asList(stoppingJobs);
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
     * The inDiscoveryMode method returns True if the Supvisors instance is in discovery mode.
     *
     * @return Boolean: The discovery mode status.
     */
    public Boolean inDiscoveryMode() {
        return this.discovery_mode;
    }

    /**
     * The getStartingJobs method returns the identifiers of the Supvisors instances where starting jobs are in progress.
     *
     * @return List: The list of identifiers where Supvisors has starting jobs.
     */
    public List getStartingJobs() {
        return this.starting_jobs;
    }

    /**
     * The getStoppingJobs method returns the identifiers of the Supvisors instances where stopping jobs are in progress.
     *
     * @return List: The list of identifiers where Supvisors has stopping jobs.
     */
    public List getStoppingJobs() {
        return this.stopping_jobs;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsStatus(state=" + this.fsm_statename
            + " discoveryMode=" + this.discovery_mode
            + " startingJobs=" + this.starting_jobs
            + " stoppingJobs=" + this.stopping_jobs + ")";
    }

}

