/*
 * Copyright 2023 Julien LE CLEACH
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
 * The Class SupvisorsStatisticsStatus.
 *
 * It gives a structured form to the statistics status received from a XML-RPC.
 */
public class SupvisorsStatisticsStatus {

    /** The status of host statistics collection. */
    private Boolean hostStatistics;

    /** The status of process statistics collection. */
    private Boolean processStatistics;

    /** The minimum interval between 2 samples of the same statistics type. */
    private Double collectingPeriod;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap info: The untyped structure got from the XML-RPC.
     */
    public SupvisorsStatisticsStatus(HashMap info)  {
        this.hostStatistics = (Boolean) info.get("host_stats");
        this.processStatistics = (Boolean) info.get("process_stats");
        this.collectingPeriod = (Double) info.get("collecting_period");
    }

    /**
     * The areHostStatisticsCollected method returns True host statistics are collected in Supvisors.
     *
     * @return Boolean: The host statistics collection status.
     */
    public Boolean areHostStatisticsCollected() {
        return this.hostStatistics;
    }

    /**
     * The areProcessStatisticsCollected method returns True host statistics are collected in Supvisors.
     *
     * @return Boolean: The process statistics collection status.
     */
    public Boolean areProcessStatisticsCollected() {
        return this.processStatistics;
    }

    /**
     * The getStatisticsCollectionPeriod method returns the minimum interval between 2 statistics samples.
     *
     * @return Float: The statistics collection period.
     */
    public Double getStatisticsCollectingPeriod() {
        return this.collectingPeriod;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsApplicationRules("
            + "hostStatistics=" + this.hostStatistics
            + " processStatistics=" + this.processStatistics
            + " collectingPeriod=" + this.collectingPeriod + ")";
    }

}
