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

import java.util.List;

/**
 * The class SupervisorConfigUpdates.
 *
 * It gives a structured form to the process rules received from a XML-RPC.
 */
public class SupervisorConfigUpdates {

    /** The list of added configurations. */
    private List added;

    /** The list of changed configurations. */
    private List changed;

    /** The list of removed configurations. */
    private List removed;

    /**
     * The constructor gets all information from an object array.
     *
     * @param Object[] objectArray: The untyped structure got from the XML-RPC.
     */
     public SupervisorConfigUpdates(final Object[] objectsArray) {
        // real structure is enclosed in array
        Object[] array = (Object[]) objectsArray[0];
        this.added = DataConversion.arrayToStringList((Object[]) array[0]);
        this.changed = DataConversion.arrayToStringList((Object[]) array[1]);
        this.removed = DataConversion.arrayToStringList((Object[]) array[2]);
    }

    /**
     * The getAdded method returns the list of added configurations.
     *
     * @return List: The list of added configurations.
     */
    public List getAdded() {
        return this.added;
    }

    /**
     * The getChanged method returns the list of changed configurations.
     *
     * @return List: The list of changed configurations.
     */
    public List getChanged() {
        return this.changed;
    }

    /**
     * The getRemoved method returns the list of removed configurations.
     *
     * @return List: The list of removed configurations.
     */
    public List getRemoved() {
        return this.removed;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorConfigUpdates(added=" + this.added
            + " changed=" + this.changed + " removed=" + this.removed + ")";
    }

}

