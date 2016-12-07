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

import java.util.HashMap;
import java.util.List;


/**
 * The Class SupervisorsProcessInfo.
 *
 * It gives a structured form to the process information received from a XML-RPC.
 */
public class SupervisorsProcessInfo implements SupervisorsAnyInfo {

    /**
     * The State enumeration for a process.
     *
     * See the description in the Supervisor documentation.
     * http://supervisord.org/subprocess.html#process-states
     */
    public enum State {
        STOPPED,
        STARTING,
        RUNNING,
        BACKOFF,
        STOPPING,
        EXITED,
        FATAL,
        UNKNOWN;
    }

    /** The process namepec. */
    private String name;

    /** The process state. */
    private State state;

    /** The addresses where the process is running. */
    private List addresses;
    
    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupervisorsProcessInfo(HashMap addressInfo)  {
        this.name = (String) addressInfo.get("namespec");
        this.state = State.valueOf((String) addressInfo.get("state"));
        this.addresses = (List) addressInfo.get("addresses");
    }

    /**
     * The getName method returns the namespec of the process.
     *
     * @return String: The namespec of the application.
     */
    public String getName() {
        return this.name;
    }

    /**
     * The getState method returns the state of the process.
     *
     * @return State: The state of the process.
     */
    public State getState() {
        return this.state;
    }

    /**
     * The getAddresses method returns the list of addresses where the process is running.
     *
     * @return List: The list of addresses.
     */
    public List getAddresses() {
        return this.addresses;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorsProcessInfo(name=" + this.name
            + " state=" + this.state + " addresses=" + this.addresses + ")";
    }

}
