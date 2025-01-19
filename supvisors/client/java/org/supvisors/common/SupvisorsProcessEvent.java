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

    /** The identifier of the Supvisors instance that published the event. */
    private String identifier;

    /** The nickname of the Supervisor instance that published the event. */
    private String nick_identifier;

    /** The name of the process' application. */
    private String group;

    /** The process name. */
    private String name;

    /** The process state. */
    private ProcessState state;

    /** A status telling if the process has exited expectantly. */
    private Boolean expected;

    /** The POSIX date (remote reference time) of the last event received for this process. */
    private Double now;

    /** The monotonic time (remote reference time) of the last event received for this process. */
    private Double now_monotonic;

    /** The monotonic time (local reference time) of the last event received for this process. */
    private Double event_mtime;

    /** The UNIX process id of the process. */
    private Integer pid;

    /** The description in the case of an erroneous start. */
    private String spawnerr;

    /** The extra arguments passed to the command line. */
    private String extra_args;

    /** A status telling if the program has been disabled. */
    private Boolean disabled;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap processInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsProcessEvent(HashMap processInfo)  {
        this.identifier = (String) processInfo.get("identifier");
        this.nick_identifier = (String) processInfo.get("nick_identifier");
        this.name = (String) processInfo.get("name");
        this.group = (String) processInfo.get("group");
        this.state = ProcessState.valueOf((Integer) processInfo.get("state"));
        this.expected = (Boolean) processInfo.get("expected");
        this.now = (Double) processInfo.get("now");
        this.now_monotonic = (Double) processInfo.get("now_monotonic");
        this.event_mtime = (Double) processInfo.get("event_mtime");
        this.pid = (Integer) processInfo.get("pid");
        this.spawnerr = (String) processInfo.get("spawnerr");
        this.extra_args = (String) processInfo.get("extra_args");
        this.disabled = (Boolean) processInfo.get("disabled");
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
     * The getNickIdentifier method returns the nickname of the Supervisor instance.
     *
     * @return String: The nickname of the Supervisor instance.
     */
    public String getNickIdentifier() {
        return this.nick_identifier;
    }

    /**
     * The getSupvisorsIdentifier method returns the identification of the Supvisors instance,
     * as a SupvisorsIdentifier instance.
     *
     * @return SupvisorsIdentifier: a SupvisorsIdentifier instance.
     */
    public SupvisorsIdentifier getSupvisorsIdentifier() {
        return new SupvisorsIdentifier(this.identifier, this.nick_identifier);
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
     * The getNow method returns the POSIX date (remote reference time) of the last event received for this process.
     *
     * @return Double: The latest stop date.
     */
    public Double getNow() {
        return this.now;
    }

    /**
     * The getNowMonotonic method returns the monotonic time (remote reference time) of the last event received
     * for this process.
     *
     * @return Double: The event monotonic time.
     */
    public Double getNowMonotonic() {
        return this.now_monotonic;
    }

    /**
     * The getEventMonotonicTime method returns the monotonic time (local reference time) of the last event received
     * for this process.
     *
     * @return Double: The event monotonic time.
     */
    public Double getEventMonotonicTime() {
        return this.event_mtime;
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
     * The getSpawnError method returns the description in the case of an erroneous start.
     *
     * @return String: The spawn error description.
     */
    public String getSpawnError() {
        return this.spawnerr;
    }

    /**
     * The getExtraArgs method returns the extra arguments passed to the command line.
     *
     * @return String: The arguments.
     */
    public String getExtraArgs() {
        return this.extra_args;
    }

    /**
     * The isExpected method returns the disabled status of the program.
     * The processes of a disabled program cannot be started.
     *
     * @return Boolean: The exit status.
     */
    public Boolean isDisabled() {
        return this.disabled;
    }

    /**
     * The toString method returns a printable form of the contents
     * of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsProcessEvent(identifier=" + this.identifier
            + " nickIdentifier=" + this.nick_identifier
            + " namespec=" + this.getName()
            + " group=" + this.group
            + " name=" + this.name
            + " state=" + this.state
            + " expected=" + this.expected
            + " now=" + DataConversion.timestampToDate(this.now)
            + " nowMonotonic=" + this.now_monotonic
            + " eventMonotonicTime=" + this.event_mtime
            + " pid=" + this.pid
            + " identifier=" + this.identifier
            + " spawnError=" + this.spawnerr
            + " extraArgs=\"" + this.extra_args + "\""
            + " disabled=" + this.disabled + ")";
    }

}
