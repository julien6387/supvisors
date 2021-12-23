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
 * The Class SupvisorsStrategies.
 *
 * It gives a structured form to the strategies received from a XML-RPC.
 */
public class SupvisorsStrategies {

    /** The application status of auto-fencing when a node becomes inactive. */
    private Boolean autoFencing;

    /** The strategy applied when Supvisors is in DEPLOYMENT state. */
    private StartingStrategy startingStrategy;

    /** The strategy applied when Supvisors is in CONCILIATION state. */
    private ConciliationStrategy conciliationStrategy;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap info: The untyped structure got from the XML-RPC.
     */
    public SupvisorsStrategies(HashMap info)  {
        this.autoFencing = (Boolean) info.get("auto-fencing");
        this.startingStrategy = StartingStrategy.valueOf((String) info.get("starting"));
        this.conciliationStrategy = ConciliationStrategy.valueOf((String) info.get("conciliation"));
    }

    /**
     * The isAutoFencing method returns True if auto-fencing is applied in Supvisors.
     *
     * @return Boolean: The auto-fencing status.
     */
    public Boolean isAutoFencing() {
        return this.autoFencing;
    }

    /**
     * The getStartingStrategy method returns the strategy applied by Supvisors in the DEPLOYMENT state.
     *
     * @return StartingStrategy: The strategy.
     */
    public StartingStrategy getStartingStrategy() {
        return this.startingStrategy;
    }

    /**
     * The getConciliationStrategy method returns the strategy applied by Supvisors in the CONCILIATION state.
     *
     * @return ConciliationStrategy: The strategy.
     */
    public ConciliationStrategy getConciliationStrategy() {
        return this.conciliationStrategy;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsApplicationRules(autoFencing=" + this.autoFencing
            + " startingStrategy=" + this.startingStrategy 
            + " conciliationStrategy=" + this.conciliationStrategy + ")";
    }

}
