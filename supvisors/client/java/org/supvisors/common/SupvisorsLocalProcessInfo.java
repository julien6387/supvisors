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

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashMap;

/**
 * The Class SupvisorsLocalProcessInfo.
 *
 * It gives a structured form to the local process info received from a XML-RPC.
 */
public class SupvisorsLocalProcessInfo implements SupvisorsAnyInfo {

    /** The name of the process' application. */
    private String group;

    /** The process name. */
    private String name;

    /** The process state. */
    private ProcessState state;

    /** A status telling if the process has exited expectantly. */
    private Boolean expected;

    /** The date of the last start event received for this process. */
    private Integer start;

    /** The monotonic time of the last start event received for this process. */
    private Double start_monotonic;

    /** The date of the last stop event received for this process. */
    private Integer stop;

    /** The monotonic time of the last stop event received for this process. */
    private Double stop_monotonic;

    /** The date of the last event received for this process. */
    private Integer now;

    /** The monotonic time of the last event received for this process. */
    private Double now_monotonic;

    /** The UNIX process id of the process. */
    private Integer pid;

    /** The process description (as given by Supervisor). */
    private String description;

    /** The description in the case of an erroneous start. */
    private String spawnerr;

    /** The configured number of seconds to go from STARTING to RUNNING. */
    private Integer startsecs;

    /** The configured number of seconds to wait before sending a KILL event to stop the process. */
    private Integer stopwaitsecs;

    /** The extra arguments passed to the command line. */
    private String extra_args;

    /** The program name of the process. */
    private String program_name;

    /** The process index in the case of an homogeneous group. */
    private Integer process_index;

    /** A status telling if the program has been disabled. */
    private Boolean disabled;

    /** A status telling if the program is configured with a stdout log file. */
    private Boolean has_stdout;

    /** A status telling if the program is configured with a stderr log file. */
    private Boolean has_stderr;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap processInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsLocalProcessInfo(HashMap processInfo)  {
        this.name = (String) processInfo.get("name");
        this.group = (String) processInfo.get("group");
        this.state = ProcessState.valueOf((Integer) processInfo.get("state"));
        this.expected = (Boolean) processInfo.get("expected");
        this.start = (Integer) processInfo.get("start");
        this.start_monotonic = (Double) processInfo.get("start_monotonic");
        this.stop = (Integer) processInfo.get("stop");
        this.stop_monotonic = (Double) processInfo.get("stop_monotonic");
        this.now = (Integer) processInfo.get("now");
        this.now_monotonic = (Double) processInfo.get("now_monotonic");
        this.pid = (Integer) processInfo.get("pid");
        this.description = (String) processInfo.get("description");
        this.spawnerr = (String) processInfo.get("spawnerr");
        this.startsecs = (Integer) processInfo.get("startsecs");
        this.stopwaitsecs = (Integer) processInfo.get("stopwaitsecs");
        this.extra_args = (String) processInfo.get("extra_args");
        this.program_name = (String) processInfo.get("program_name");
        this.process_index = (Integer) processInfo.get("process_index");
        this.disabled = (Boolean) processInfo.get("disabled");
        this.has_stdout = (Boolean) processInfo.get("has_stdout");
        this.has_stderr = (Boolean) processInfo.get("has_stderr");
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
     * The getStart method returns the date of the last start event received for this process.
     *
     * @return Integer: The latest start date.
     */
    public Integer getStart() {
        return this.start;
    }

    /**
     * The getStartMonotonic method returns the monotonic time of the last start event received for this process.
     *
     * @return Double: The latest start monotonic time.
     */
    public Double getStartMonotonic() {
        return this.start_monotonic;
    }

    /**
     * The getStop method returns the date of the last stop event received for this process.
     *
     * @return Integer: The latest stop date.
     */
    public Integer getStop() {
        return this.stop;
    }

    /**
     * The getStopMonotonic method returns the monotonic time of the last stop event received for this process.
     *
     * @return Double: The latest stop monotonic time.
     */
    public Double getStopMonotonic() {
        return this.stop_monotonic;
    }

    /**
     * The getNow method returns the date of the last event received for this process.
     *
     * @return Integer: The latest event date.
     */
    public Integer getNow() {
        return this.now;
    }

    /**
     * The getNowMonotonic method returns the monotonic time of the last event received for this process.
     *
     * @return Double: The latest stop monotonic time.
     */
    public Double getNowMonotonic() {
        return this.now_monotonic;
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
     * The getDescription method returns the process description (as given by Supervisor).
     *
     * @return String: The process description.
     */
    public String getDescription() {
        return this.description;
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
     * The getStartSeconds method returns the configured number of seconds to go from STARTING to RUNNING.
     *
     * @return Integer: The configured start seconds.
     */
    public Integer getStartSeconds() {
        return this.startsecs;
    }

    /**
     * The getStopWaitSeconds method returns the configured number of seconds to wait before sending a KILL event
     * to stop the process.
     *
     * @return Integer: The configured stop wait seconds.
     */
    public Integer getStopWaitSeconds() {
        return this.stopwaitsecs;
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
     * The getProgramName method returns the program name of the process.
     *
     * @return String: The arguments.
     */
    public String getProgramName() {
        return this.program_name;
    }

    /**
     * The getProcessIndex method returns the process index in the case of an homogeneous group.
     *
     * @return Integer: The process index.
     */
    public Integer getProcessIndex() {
        return this.process_index;
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
     * The hasStdout method returns true if a stdout log file is configured in the Supervisor program.
     *
     * @return Boolean: The stdout status.
     */
    public Boolean hasStdout() {
        return this.has_stdout;
    }

    /**
     * The hasStderr method returns true if a stderr log file is configured in the Supervisor program.
     *
     * @return Boolean: The stderr status.
     */
    public Boolean hasStderr() {
        return this.has_stderr;
    }

    /**
     * The toString method returns a printable form of the contents
     * of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
        String startDate = "0";
        if (this.start > 0) {
            startDate = "\"" + sdf.format(new Date(this.start * 1000L)) + "\"";
        }
        String stopDate = "0";
        if (this.stop > 0) {
            stopDate = "\"" + sdf.format(new Date(this.stop * 1000L)) + "\"";
        }
        String nowDate = "0";
        if (this.now > 0) {
            nowDate = "\"" + sdf.format(new Date(this.now * 1000L)) + "\"";
        }
        return "SupvisorsLocalProcessInfo(namespec=" + this.getName()
            + " group=" + this.group
            + " name=" + this.name
            + " state=" + this.state
            + " expected=" + this.expected
            + " start=" + startDate
            + " startMonotonic=" + this.start_monotonic
            + " stop=" + stopDate
            + " stopMonotonic=" + this.stop_monotonic
            + " now=" + nowDate
            + " nowMonotonic=" + this.now_monotonic
            + " pid=" + this.pid
            + " description=" + this.description
            + " spawnError=" + this.spawnerr
            + " startSeconds=" + this.startsecs
            + " stopWaitSeconds=" + this.stopwaitsecs
            + " extraArgs=\"" + this.extra_args + "\""
            + " programName=" + this.program_name
            + " processIndex=" + this.process_index
            + " disabled=" + this.disabled
            + " hasStdout=" + this.has_stdout
            + " hasStderr=" + this.has_stderr + ")";
    }

}
