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


/**
 * The Class SupervisorExecutionStatus.
 *
 * It gives a structured form to the process information received from a XML-RPC.
 */
public class SupervisorExecutionStatus implements SupervisorsAnyInfo {

    /** The process namespec. */
    private String namespec;

    /** The name of the process. */
    private String processName;

    /** The name of the process' group. */
    private String groupName;

    /**
     * The execution description.
     */
    private String description;

    /** The execution status. */
    private SupervisorFaults status;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupervisorExecutionStatus(HashMap addressInfo)  {
        this.processName = (String) addressInfo.get("name");
        this.groupName = (String) addressInfo.get("group");
        // namespec is a combination of group and process names
        if (this.processName.equals(this.groupName)) {
            this.namespec = this.processName;
        } else {
            this.namespec = this.groupName + ":" + this.processName;
        }
        this.description = (String) addressInfo.get("description");
        this.status = SupervisorFaults.getFault((Integer) addressInfo.get("status"));
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
     * The getDescription method returns the description of the execution of the command.
     *
     * @return String: The description of the command.
     */
    public String getDescription() {
        return this.description;
    }

    /**
     * The getStatus method returns the status of the command.
     *
     * @return SupervisorFaults: The status.
     */
    public SupervisorFaults getStatus() {
        return this.status;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorExecutionStatus(namespec=" + this.namespec
            + " processName=" + this.processName + " groupName=" + this.groupName
            + " description='" + this.description + "'" + " status=" + this.status + ")";
    }

}
