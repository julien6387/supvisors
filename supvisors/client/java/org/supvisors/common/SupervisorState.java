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

import java.util.HashMap;


/**
 * The Class SupervisorState.
 *
 * It gives a structured form to the supervisor state received from a XML-RPC.
 */
public class SupervisorState {

    /**
     * The State enumeration for Supervisor.
     *
     * FATAL is used when Supervisor has experienced a serious error.
     * RUNNING is used when Supervisor is working normally.
     * RESTARTING is used when Supervisor is in the process of restarting.
     * SHUTDOWN is used when Supervisor is in the process of shutting down.
     */
    public enum State {
        FATAL(2),
        RUNNING(1),
        RESTARTING(0),
        SHUTDOWN(-1);

        /** The state code. */
        private int stateCode;

        /** The constructor links the state code to the state name. */
        private State(final int stateCode) {
            this.stateCode = stateCode;
        }
    }

    /** The supervisor state. */
    private State state;

    /**
     * The constructor gets the state information from an HashMap.
     *
     * @param HashMap stateInfo: The untyped structure got from the XML-RPC.
     */
    public SupervisorState(HashMap stateInfo)  {
        this.state = State.valueOf((String) stateInfo.get("statename"));
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
        return "SupervisorState(state=" + this.state + ")";
    }

}

