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

    /**
     * The State enumeration for Supvisors.
     *
     * INITIALIZATION is used when Supvisors is synchronizing with all other Supvisors instances.
     * DEPLOYMENT is used when Supvisors is starting applications automatically.
     * OPERATION is used when Supvisors is working normally.
     * CONCILIATION is used when Supvisors is conciliating conflicts due to multiple instance of the same process.
     */
    public enum State {
        INITIALIZATION(0),
        DEPLOYMENT(1),
        OPERATION(2),
        CONCILIATION(3),
        RESTARTING(4),
        RESTART(5),
        SHUTTING_DOWN(6),
        SHUTDOWN(7);

        /** The state code. */
        private int stateCode;

        /** The constructor links the state code to the state name. */
        private State(final int stateCode) {
            this.stateCode = stateCode;
        }
    }

    /** The Supvisors state. */
    private State fsm_statename;

    /**
     * The identifiers of where starting jobs are in progress.
     */
    private List starting_jobs;

    /**
     * The identifiers of where stopping jobs are in progress.
     */
    private List stopping_jobs;

    /**
     * The constructor gets the state information from an HashMap.
     *
     * @param HashMap stateInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsStatus(HashMap stateInfo)  {
        this.fsm_statename = State.valueOf((String) stateInfo.get("fsm_statename"));
        Object[] startingJobs = (Object[]) stateInfo.get("starting_jobs");
        this.starting_jobs = Arrays.asList(startingJobs);
        Object[] stoppingJobs = (Object[]) stateInfo.get("stopping_jobs");
        this.stopping_jobs = Arrays.asList(stoppingJobs);
    }

    /**
     * The getState method returns the state of supervisor.
     *
     * @return State: The state of the supervisor.
     */
    public State getState() {
        return this.fsm_statename;
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
            + " startingJobs=" + this.starting_jobs
            + " stoppingJobs=" + this.stopping_jobs + ")";
    }

}

