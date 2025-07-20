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
import java.util.Map;


/**
 * The Class SupvisorsStatus.
 *
 * It gives a structured form to the supervisor state received from a XML-RPC.
 */
public class SupvisorsStatus extends SupvisorsCommonStateModes {

    /** The identifiers of where starting jobs are in progress. */
    private List<String> starting_jobs;

    /** The identifiers of where stopping jobs are in progress. */
    private List<String> stopping_jobs;

    /**
     * The constructor gets the state information from an HashMap.
     *
     * @param HashMap stateInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsStatus(HashMap info)  {
        super(info);
        Object[] startingJobs = (Object[]) info.get("starting_jobs");
        this.starting_jobs = DataConversion.arrayToStringList(startingJobs);
        Object[] stoppingJobs = (Object[]) info.get("stopping_jobs");
        this.stopping_jobs = DataConversion.arrayToStringList(stoppingJobs);
    }

    /**
     * The getStartingJobs method returns the identifiers of the Supvisors instances where starting jobs are in progress.
     *
     * @return List<String>: The list of identifiers where Supvisors has starting jobs.
     */
    public List<String> getStartingJobs() {
        return this.starting_jobs;
    }

    /**
     * The getStoppingJobs method returns the identifiers of the Supvisors instances where stopping jobs are in progress.
     *
     * @return List<String>: The list of identifiers where Supvisors has stopping jobs.
     */
    public List<String> getStoppingJobs() {
        return this.stopping_jobs;
    }

    /**
     * The toString method returns a printable form of the SupvisorsStatus instance.
     *
     * @return String: The contents of the SupvisorsStatus.
     */
    public String toString() {
        return "SupvisorsStatus(" + super.toString()
            + " startingJobs=" + this.starting_jobs
            + " stoppingJobs=" + this.stopping_jobs + ")";
    }

}

