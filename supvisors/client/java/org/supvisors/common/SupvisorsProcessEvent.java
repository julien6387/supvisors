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

import java.util.HashMap;

/**
 * The Class SupvisorsProcessEvent.
 *
 * It gives a structured form to the process event received from a listener.
 */
public class SupvisorsProcessEvent implements SupvisorsAnyInfo {

    /** The name of the process' application. */
    private String group;

    /** The process name. */
    private String name;

    /** The process state. */
    private ProcessState state;

    /** A status telling if the process has exited expectantly. */
    private Boolean expected;

    /** The date of the last event received for this process. */
    private Integer now;

    /** The UNIX process id of the process. */
    private Integer pid;

    /** The node of the event. */
    private String node;

    /** The extra arguments passed to the command line. */
    private String extra_args;

    /** A status telling if the process has exited expectantly. */
    private Boolean deleted;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap processInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsProcessEvent(HashMap processInfo)  {
        this.name = (String) processInfo.get("name");
        this.group = (String) processInfo.get("group");
        this.state = ProcessState.valueOf((Integer) processInfo.get("state"));
        this.expected = (Boolean) processInfo.get("expected");
        this.now = (Integer) processInfo.get("now");
        this.pid = (Integer) processInfo.get("pid");
        // node is not set in this message
        this.node = null;
        this.extra_args = (String) processInfo.get("extra_args");
   }

    /**
     * The getGroup method returns the name of the process' application'.
     *
     * @return String: The namespec of the application.
     */
    public String getGroup() {
        return this.group;
    }

    /**
     * The getProcessName method returns the name of the process.
     *
     * @return String: The name of the process.
     */
    public String getProcessName() {
        return this.name;
    }

    /**
     * The getName method returns the namespec of the process.
     *
     * @return String: The namespec of the process.
     */
    public String getName() {
        return DataConversion.stringsToNamespec(this.group, this.name);
    }

    /**
     * The getState method returns the state of the process.
     *
     * @return ProcessState: The state of the process.
     */
    public ProcessState getState() {
        return this.state;
    }

    /**
     * The isExpected method returns the exit status of the process.
     * It only makes sense when the process is in EXITED state.
     *
     * @return Boolean: The exit status.
     */
    public Boolean isExpected() {
        return this.expected;
    }

    /**
     * The getNow method returns the date of the event.
     *
     * @return Integer: The date of the event.
     */
    public Integer getNow() {
        return this.now;
    }

    /**
     * The getPID method returns the UNIX process id of the process.
     *
     * @return Integer: The process' PID.
     */
    public Integer getPID() {
        return this.pid;
    }

    /**
     * The getNode method returns the node of the event.
     *
     * @return String: The node of the event.
     */
    public String getNode() {
        return this.node;
    }

    /**
     * The getExtraArgs method returns the extra arguments passed to the
     * command line.
     *
     * @return String: The arguments.
     */
    public String getExtraArgs() {
        return this.extra_args;
    }

    /**
     * The toString method returns a printable form of the contents
     * of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsProcessEvent(namespec=" + this.getName()
            + " group=" + this.group
            + " name=" + this.name
            + " state=" + this.state
            + " expected=" + this.expected
            + " now=" + this.now
            + " pid=" + this.pid
            + " node=" + this.node
            + " extraArgs=\"" + this.extra_args + "\")";
    }

}
