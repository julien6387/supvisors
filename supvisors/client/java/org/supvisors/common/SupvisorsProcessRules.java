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

    /**
     * The applicable addresses.
     * If all known addresses are applicable, '*' is used.
     */
    private List addresses;

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

    /** The loading of the process, as declared in the Supvisors deployment file. */
    private Integer expectedLoading;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsProcessRules(HashMap addressInfo)  {
        this.namespec = (String) addressInfo.get("namespec");
        Object[] addresses = (Object[]) addressInfo.get("addresses");
        this.addresses = Arrays.asList(addresses);
        this.startSequence = (Integer) addressInfo.get("start_sequence");
        this.stopSequence = (Integer) addressInfo.get("stop_sequence");
        this.required = (Boolean) addressInfo.get("required");
        this.waitExit = (Boolean) addressInfo.get("wait_exit");
        this.expectedLoading = (Integer) addressInfo.get("expected_loading");
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
     * The getAddresses method returns the addresses where the process can be started.
     *
     * @return List: The list of addresses.
     */
    public List getAddresses() {
        return this.addresses;
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
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsProcessrules(namespec=" + this.namespec
            + " addresses=" + this.addresses + " startSequence=" + this.startSequence
            + " stopSequence=" + this.stopSequence + " required=" + this.required
            + " waitExit=" + this.waitExit + " expectedLoading=" + this.expectedLoading + ")";
    }

}
