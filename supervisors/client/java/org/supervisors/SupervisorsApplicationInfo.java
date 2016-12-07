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
 * The Class SupervisorsApplicationInfo.
 *
 * It gives a structured form to the application information received from a XML-RPC.
 */
public class SupervisorsApplicationInfo implements SupervisorsAnyInfo {

    /**
     * The State enumeration for an application.
     *
     * STOPPED is used when all the processes of the application are STOPPED, EXITED, FATAL or UNKNOWN.
     * STARTING is used when one of the processes of the application is STARTING.
     * RUNNING is used when at least one process of the application is RUNNING and none is STARTING or STOPPING.
     * STOPPING is used when one of the processes of the application is STOPPING and none is STARTING.
     */
    public enum State {
        STOPPED,
        STARTING,
        RUNNING,
        STOPPING;
    }

    /** The application name. */
    private String name;

    /** The application state. */
    private State state;

    /** A status telling if the running application has a major failure,
    i.e. at least one of its required processes is stopped. */
    private Boolean majorFailure;

    /** A status telling if the running application has a minor failure,
    i.e. at least one of its optional processes has stopped unexpectantly. */
    private Boolean minorFailure;
    
    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupervisorsApplicationInfo(HashMap addressInfo)  {
        this.name = (String) addressInfo.get("application_name");
        this.state = State.valueOf((String) addressInfo.get("state"));
        this.majorFailure = (Boolean) addressInfo.get("major_failure");
        this.minorFailure = (Boolean) addressInfo.get("minor_failure");
    }

    /**
     * The getName method returns the name of the application.
     *
     * @return String: The name of the application.
     */
    public String getName() {
        return this.name;
    }

    /**
     * The getState method returns the state of the application.
     *
     * @return State: The state of the application.
     */
    public State getState() {
        return this.state;
    }

    /**
     * The hasMajorFailure method the status of the major failure for the application.
     *
     * @return Boolean: True if a major failure is raised.
     */
    public Boolean hasMajorFailure() {
        return this.majorFailure;
    }

    /**
     * The hasMinorFailure method the status of the minor failure for the application.
     *
     * @return Boolean: True if a minor failure is raised.
     */
    public Boolean hasMinorFailure() {
        return this.minorFailure;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorsApplicationInfo(name=" + this.name
            + " state=" + this.state + " majorFailure=" + this.majorFailure
            + " minorFailure=" + this.minorFailure + ")";
    }

}

