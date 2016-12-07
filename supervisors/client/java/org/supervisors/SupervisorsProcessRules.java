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

package org.supervisors;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
    
/**
 * The Class SupervisorsProcessRules.
 *
 * It gives a structured form to the process rules received from a XML-RPC.
 */
public class SupervisorsProcessRules implements SupervisorsAnyInfo {

    private String name;
    private List addresses;
    private Integer startSequence;
    private Integer stopSequence;
    private Boolean required;
    private Boolean waitExit;
    private Integer expectedLoading;

    public SupervisorsProcessRules(HashMap addressInfo)  {
        this.name = (String) addressInfo.get("namespec");
        Object[] addresses = (Object[]) addressInfo.get("addresses");
        this.addresses = Arrays.asList(addresses);
        this.startSequence = (Integer) addressInfo.get("start_sequence");
        this.stopSequence = (Integer) addressInfo.get("stop_sequence");
        this.required = (Boolean) addressInfo.get("required");
        this.waitExit = (Boolean) addressInfo.get("wait_exit");
        this.expectedLoading = (Integer) addressInfo.get("expected_loading");
    }

   public String getName() {
        return this.name;
    }

   public List getAddresses() {
        return this.addresses;
    }

   public Integer getStartSequence() {
        return this.startSequence;
    }

   public Integer getStopSequence() {
        return this.stopSequence;
    }

   public Boolean isRequired() {
        return this.required;
    }

   public Boolean hasToWaitExit() {
        return this.waitExit;
    }

   public Integer getExpectedLoading() {
        return this.expectedLoading;
    }

}
