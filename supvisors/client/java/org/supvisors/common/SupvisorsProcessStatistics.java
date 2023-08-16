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

import java.util.HashMap;
import java.util.List;

/**
 * The Class SupvisorsProcessStatistics.
 *
 * It gives a structured form to the Supvisors Process Statistics information received from the event interface.
 */
public class SupvisorsProcessStatistics {

    /** The namespec of the process. */
    private String namespec;

    /** The identifier of the Supvisors instance. */
    private String identifier;

    /** The configured integration period. */
    private Float target_period;

    /** The actual integration dates. */
    private List<Float> period;

    /** The CPU of the process during the period. */
    private Float cpu;

    /** The current Memory occupation of the process on the host. */
    private Float mem;

    /**
     * This constructor gets all information from a HashMap.
     * NOT USED but kept for future growth.
     *
     * @param HashMap statsInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsProcessStatistics(HashMap statsInfo)  {
        this.namespec = (String) statsInfo.get("namespec");
        this.identifier = (String) statsInfo.get("identifier");
        this.target_period = (Float) statsInfo.get("target_period");
        this.period = DataConversion.arrayToFloatList((Object[]) statsInfo.get("period"));
        this.cpu = (Float) statsInfo.get("cpu");
        this.mem = (Float) statsInfo.get("mem");
    }

    /**
     * The getNamespec method returns the namespec of the process.
     *
     * @return String: The namespec of the process.
     */
    public String getNamespec() {
        return this.namespec;
    }

    /**
     * The getIdentifier method returns the identifier of the Supvisors instance.
     *
     * @return String: The identifier of the Supvisors instance.
     */
    public String getIdentifier() {
        return this.identifier;
    }

    /**
     * The getTargetPeriod method returns the configured integration period.
     *
     * @return Float: The configured integration period.
     */
    public Float getTargetPeriod() {
        return this.target_period;
    }

    /**
     * The getStartPeriod method returns the start date of the integrated host statistics.
     * (end - start) is expected to be greater than the configured integration period.
     *
     * @return Float: The start date of the integrated host statistics.
     */
    public Float getStartPeriod() {
        return this.period.get(0);
    }

    /**
     * The getEndPeriod method returns the end date of the integrated host statistics.
     * (end - start) is expected to be greater than the configured integration period.
     *
     * @return Float: The node name of the Supvisors instance.
     */
    public Float getEndPeriod() {
        return this.period.get(1);
    }

    /**
     * The getCPU method returns the CPU (IRIX mode) of the process on the host during the integration period.
     *
     * @return Float: The average CPU.
     */
    public Float getCPU() {
        return this.cpu;
    }

    /**
     * The getMemory method returns the memory occupation of the process on the host during the integration period.
     *
     * @return Float: The memory occupation.
     */
    public Float getMemory() {
        return this.mem;
    }

    /**
     * The toString method returns a printable form of the contents of the SupvisorsProcessStatistics instance.
     *
     * @return String: The contents of the SupvisorsProcessStatistics instance.
     */
    public String toString() {
        return "SupvisorsProcessStatistics("
            + "namespec=" + this.namespec
            + " identifier=" + this.identifier
            + " target_period=" + this.target_period
            + " startPeriod=" + this.getStartPeriod()
            + " endPeriod=" + this.getEndPeriod()
            + " cpu=" + this.getCPU()
            + " memory=" + this.getMemory()
            + ")";
    }

}
