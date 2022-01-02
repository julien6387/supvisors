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
 * The Class SupvisorsApplicationInfo.
 *
 * It gives a structured form to the application information received from a XML-RPC.
 */
public class SupvisorsApplicationInfo implements SupvisorsAnyInfo {

    /**
     * The State enumeration for an application.
     *
     * STOPPED is used when all the processes of the application are STOPPED, EXITED, FATAL or UNKNOWN.
     * STARTING is used when one of the processes of the application is STARTING.
     * RUNNING is used when at least one process of the application is RUNNING and none is STARTING or STOPPING.
     * STOPPING is used when one of the processes of the application is STOPPING and none is STARTING.
     */
    public enum State {
        STOPPED(0),
        STARTING(1),
        RUNNING(2),
        STOPPING(3);

        private final int value;
        public int getValue() {
            return value;
        }

        private State(int value) {
            this.value = value;
        }
    }

    /** The application name. */
    private String application_name;

    /** The application state. */
    private State statename;

    /**
     * A status telling if the application is managed in Supvisors,
     * i.e. it is declared in the rules file.
     */
    private Boolean managed;

    /**
     * A status telling if the running application has a major failure,
     * i.e. at least one of its required processes is stopped.
     */
    private Boolean major_failure;

    /**
     * A status telling if the running application has a minor failure,
     * i.e. at least one of its optional processes has stopped unexpectedly.
     */
    private Boolean minor_failure;
    
    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap applicationInfo: The untyped structure got from the XML-RPC.
     */
    public SupvisorsApplicationInfo(HashMap applicationInfo) {
        this.application_name = (String) applicationInfo.get("application_name");
        this.statename = State.valueOf((String) applicationInfo.get("statename"));
        this.managed = (Boolean) applicationInfo.get("managed");
        this.major_failure = (Boolean) applicationInfo.get("major_failure");
        this.minor_failure = (Boolean) applicationInfo.get("minor_failure");
    }

    /**
     * The getName method uses the getApplicationName method.
     *
     * @return String: The name of the application.
     */
    public String getName() {
        return this.getApplicationName();
    }

    /**
     * The getApplicationName method returns the name of the process' application.
     *
     * @return String: The name of the application.
     */
    public String getApplicationName() {
        return this.applicationName;
    }

    /**
     * The getState method returns the state of the application.
     *
     * @return State: The state of the application.
     */
    public State getState() {
        return this.statename;
    }

    /**
     * The isManaged method returns the managed status of the application in Supvisors.
     *
     * @return Boolean: True if the application is managed.
     */
    public Boolean isManaged() {
        return this.managed;
    }

    /**
     * The hasMajorFailure method returns the status of the major failure for the application.
     *
     * @return Boolean: True if a major failure is raised.
     */
    public Boolean hasMajorFailure() {
        return this.major_failure;
    }

    /**
     * The hasMinorFailure method returns the status of the minor failure for the application.
     *
     * @return Boolean: True if a minor failure is raised.
     */
    public Boolean hasMinorFailure() {
        return this.minor_failure;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupvisorsApplicationInfo("
            + "name=" + this.application_name
            + " state=" + this.statename
            + " managed=" + this.managed
            + " majorFailure=" + this.major_failure
            + " minorFailure=" + this.minor_failure + ")";
    }

}

