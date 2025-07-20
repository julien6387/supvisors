/*
 * Copyright 2025 Julien LE CLEACH
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

/**
 * The Class SupvisorsStateModes.
 *
 * It gives a structured form to the Supvisors Instance state & modes received from a XML-RPC.
 */

public class SupvisorsStateModes extends SupvisorsCommonStateModes {

    /** True if the Supvisors instance has starting jobs in progress. */
    private Boolean starting_jobs;

    /** True if the Supvisors instance has stopping jobs in progress. */
    private Boolean stopping_jobs;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap instanceInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsStateModes(HashMap info)  {
        super(info);
        this.starting_jobs = (Boolean) info.get("starting_jobs");
        this.stopping_jobs = (Boolean) info.get("stopping_jobs");
    }

    /**
     * The hasStartingJobs method returns True if the Supvisors instance has jobs in progress in its Starter.
     *
     * @return Boolean: The starting jobs progress.
     */
    public Boolean hasStartingJobs() {
        return this.starting_jobs;
    }

    /**
     * The hasStoppingJobs method returns True if the Supvisors instance has jobs in progress in its Stopper.
     *
     * @return Boolean: The stopping jobs progress.
     */
    public Boolean hasStoppingJobs() {
        return this.stopping_jobs;
    }

    /**
     * The toString method returns a printable form of the SupvisorsStateModes instance.
     *
     * @return String: The contents of the SupvisorsStateModes.
     */
    public String toString() {
        return "SupvisorsStateModes(" + super.toString()
            + " startingJobs=" + this.starting_jobs
            + " stoppingJobs=" + this.stopping_jobs + ")";
    }

}
