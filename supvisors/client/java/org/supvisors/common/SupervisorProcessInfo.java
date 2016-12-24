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
 * The Class SupervisorProcessInfo.
 *
 * It gives a structured form to the process information received from a XML-RPC.
 */
public class SupervisorProcessInfo implements SupvisorsAnyInfo {

    /** The process namespec. */
    private String namespec;

    /** The name of the process. */
    private String processName;

    /** The name of the process' group. */
    private String groupName;

    /**
     * If process state is running, description's value is process_id and uptime.
     * If process state is stopped, description's value is stop time.
     */
    private String description;

    /** The UNIX timestamp of when the process was started. */
    private Integer startTime;

    /**
     * The UNIX timestamp of when the process last ended,
     * or 0 if the process has never been stopped.
     */
    private Integer stopTime;

    /**
     * The UNIX timestamp of the current time,
     * which can be used to calculate process up-time.
     */
    private Integer currentTime;

    /** The process state. */
    private ProcessState state;

    /**
     * The description of error that occurred during spawn,
     * or empty string if none.
     */
    private String spawnError;

    /**
     * The Exit status (errorlevel) of process,
     * or 0 if the process is still running.
     */
    private Integer exitStatus;

    /** Deprecated alias for stdoutLogFile. */
    private String logFile;

    /** Absolute path and filename to the stdout logfile. */
    private String stdoutLogFile;

    /** Absolute path and filename to the stderr logfile. */
    private String stderrLogFile;

    /**
     * The UNIX process ID (PID) of the process,
     * or 0 if the process is not running.
     */
    private Integer pid;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupervisorProcessInfo(HashMap addressInfo)  {
        this.processName = (String) addressInfo.get("name");
        this.groupName = (String) addressInfo.get("group");
        this.namespec = DataConversion.stringsToNamespec(this.groupName, this.processName);
        this.description = (String) addressInfo.get("description");
        this.startTime = (Integer) addressInfo.get("start");
        this.stopTime = (Integer) addressInfo.get("stop");
        this.currentTime = (Integer) addressInfo.get("now");
        this.state = ProcessState.valueOf((String) addressInfo.get("statename"));
        this.spawnError = (String) addressInfo.get("spawnerr");
        this.exitStatus = (Integer) addressInfo.get("exitstatus");
        this.logFile = (String) addressInfo.get("logfile");
        this.stdoutLogFile = (String) addressInfo.get("stdout_logfile");
        this.stderrLogFile = (String) addressInfo.get("stderr_logfile");
        this.pid = (Integer) addressInfo.get("pid");
    }

    /**
     * The getName method returns the namespec of the process.
     *
     * @return String: The namespec of the process.
     */
    public String getName() {
        return this.namespec;
    }

    /**
     * The getProcessName method returns the name of the process.
     *
     * @return String: The name of the process.
     */
    public String getProcessName() {
        return this.processName;
    }

    /**
     * The getGroupName method returns the name of the process' group.
     *
     * @return String: The name of the process' group.
     */
    public String getGroupName() {
        return this.groupName;
    }

    /**
     * The getDescription method returns the description of the process,
     * depending on its state.
     *
     * @return String: The description of the process.
     */
    public String getDescription() {
        return this.description;
    }

    /**
     * The getStartTime method returns the starting time of the process.
     *
     * @return Integer: The UNIX start time.
     */
    public Integer getStartTime() {
        return this.startTime;
    }

    /**
     * The getStopTime method returns the stopping time of the process.
     *
     * @return Integer: The UNIX stop time.
     */
    public Integer getStopTime() {
        return this.stopTime;
    }

    /**
     * The getCurrentTime method returns the current time of the process.
     *
     * @return Integer: The UNIX current time.
     */
    public Integer getCurrentTime() {
        return this.currentTime;
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
     * The getSpawnError method returns the description of
     * the eventual error that occurred during spawn.
     *
     * @return String: The description of the spawn error.
     */
    public String getSpawnError() {
        return this.spawnError;
    }

    /**
     * The getExitStatus method returns the exit code of the process.
     *
     * @return Integer: The exit status.
     */
    public Integer getExitStatus() {
        return this.exitStatus;
    }

    /**
     * Deprecated alias for getStdoutLogFile.
     *
     * @deprecated use {@link #getStdoutLogFile()} instead.
     * @return String: The absolute path of the log file.
     */
    @Deprecated
    public String getLogFile() {
        return this.logFile;
    }

    /**
     * The getStdoutLogFile method returns the absolute path
     * and filename to the stdout logfile.
     *
     * @return String: The absolute path of the stdout log file.
     */
    public String getStdoutLogFile() {
        return this.stdoutLogFile;
    }

    /**
     * The getStderrLogFile method returns the absolute path
     * and filename to the stderr logfile.
     *
     * @return String: The absolute path of the stderr log file.
     */
    public String getStderrLogFile() {
        return this.stderrLogFile;
    }

    /**
     * The getPID method returns the pid of the process.
     *
     * @return Integer: The UNIX pid.
     */
    public Integer getPID() {
        return this.pid;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorProcessInfo(namespec=" + this.namespec
            + " processName=" + this.processName + " groupName=" + this.groupName
            + " description='" + this.description + "'" + " startTime=" + this.startTime
            + " stopTime=" + this.stopTime + " currentTime=" + this.currentTime
            + " state=" + this.state + " spawnError='" + this.spawnError + "'"
            + " exitStatus=" + this.exitStatus + " logFile=" + this.logFile
            + " stdoutLogFile=" + this.stdoutLogFile + " stderrLogFile=" + this.stderrLogFile
            + " pid=" + this.pid + ")";
    }

}
