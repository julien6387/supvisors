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

/**
 * The class SupervisorConfigInfo.
 *
 * It gives a structured form to the process rules received from a XML-RPC.
 */
public class SupervisorConfigInfo implements SupervisorsAnyInfo {

    /** The process namespec. */
    private String namespec;

    /** The name of the process. */
    private String processName;

    /** The name of the process' group. */
    private String groupName;

    /** The inuse status. */
    private Boolean inUse;

    /** The autostart status. */
    private Boolean autoStart;

    /** The priority of the process. */
    private Integer processPriority;

    /** The priority of the process' group. */
    private Integer groupPriority;

    /**
     * The constructor gets all information from an object array.
     *
     * @param HashMap configInfo: The untyped structure got from the XML-RPC.
     */
     public SupervisorConfigInfo(final HashMap configInfo) {
        this.processName = (String) configInfo.get("name");
        this.groupName = (String) configInfo.get("group");
        this.namespec = DataConversion.stringsToNamespec(this.groupName, this.processName);
        this.inUse = (Boolean) configInfo.get("inuse");
        this.autoStart = (Boolean) configInfo.get("autostart");
        this.processPriority = (Integer) configInfo.get("process_prio");
        this.groupPriority = (Integer) configInfo.get("group_prio");
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
     * The isInUse method returns true if the configuration is in use.
     *
     * @return Boolean: The inUse status.
     */
    public Boolean isInUse() {
        return this.inUse;
    }

    /**
     * The isAutoStart method returns true if the autostart is configured.
     *
     * @return Boolean: The autostart status.
     */
    public Boolean isAutoStart() {
        return this.autoStart;
    }

    /**
     * The getProcessPriority method returns the process priority.
     *
     * @return Integer: The process priority.
     */
    public Integer getProcessPriority() {
        return this.processPriority;
    }

    /**
     * The getGroupPriority method returns the group priority.
     *
     * @return Integer: The group priority.
     */
    public Integer getGroupPriority() {
        return this.groupPriority;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorConfigInfo(namespec=" + this.namespec
            + " processName=" + this.processName + " groupName=" + this.groupName
            + " inUse=" + this.inUse + " autoStart=" + this.autoStart
            + " processPriority=" + this.processPriority + " groupPriority=" + this.groupPriority + ")";
    }

}


