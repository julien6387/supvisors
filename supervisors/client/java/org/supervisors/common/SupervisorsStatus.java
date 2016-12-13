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

package org.supervisors.common;

import java.util.HashMap;
import org.json.JSONObject;


/**
 * The Class SupervisorsStatus.
 *
 * It gives a structured form to the supervisor state received from a XML-RPC.
 */
public class SupervisorsStatus {

    /**
     * The State enumeration for Supervisors.
     *
     * INITIALIZATION is used when Supervisors is synchronizing with all orther Supervisors instances.
     * DEPLOYMENT is used when Supervisors is starting applications automatically.
     * OPERATION is used when Supervisors is working normally.
     * CONCILIATION is used when Supervisors is conciliating conflicts due to multiple instance of the same process.
     */
    public enum State {
        INITIALIZATION(0),
        DEPLOYMENT(1),
        OPERATION(2),
        CONCILIATION(3);

        /** The state code. */
        private int stateCode;

        /** The constructor links the state code to the state name. */
        private State(final int stateCode) {
            this.stateCode = stateCode;
        }
    }

    /** The Supervisors state. */
    private State state;

    /**
     * The constructor gets the state information from an HashMap.
     *
     * @param HashMap stateInfo: The untyped structure got from the XML-RPC.
     */
    public SupervisorsStatus(HashMap stateInfo)  {
        this.state = State.valueOf((String) stateInfo.get("statename"));
    }

    /**
     * The constructor gets the state information from a JSON string.
     *
     * @param String json: The untyped structure got from the event subscriber.
     */
    public SupervisorsStatus(final String json) {
        JSONObject obj = new JSONObject(json);
        this.state = State.valueOf(obj.getString("statename"));
    }

    /**
     * The getState method returns the state of supervisor.
     *
     * @return State: The state of the supervisor.
     */
    public State getState() {
        return this.state;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorsState(state=" + this.state + ")";
    }

}

