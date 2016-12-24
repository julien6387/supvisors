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


/**
 * The Class SupervisorLogResult.
 *
 * It gives a structured form to the process information received from a XML-RPC.
 */
public class SupervisorLogResult {

    /** The log bytes. */
    private String bytes;

    /** The log offset. */
    private Integer offset;

    /** The log overflow. */
    private Boolean overflow;

    /**
     * The constructor gets all information from an HashMap.
     *
     * @param HashMap addressInfo: The untyped structure got from the XML-RPC.
     */
    public SupervisorLogResult(final Object[] objectsArray)  {
        this.bytes = (String) objectsArray[0];
        this.offset = (Integer) objectsArray[1];
        this.overflow = (Boolean) objectsArray[2];
    }

    /**
     * The getBytes method returns the log bytes.
     *
     * @return String: The log bytes.
     */
    public String getBytes() {
        return this.bytes;
    }

    /**
     * The getOffset method returns the offset.
     *
     * @return Integer: The log offset.
     */
    public Integer getOffset() {
        return this.offset;
    }

    /**
     * The getGroupName method returns the log overflow.
     *
     * @return Boolean: The log overflow.
     */
    public Boolean getOverflow() {
        return this.overflow;
    }

    /**
     * The toString method returns a printable form of the contents of the instance.
     *
     * @return String: The contents of the instance.
     */
    public String toString() {
        return "SupervisorLogResult(offset=" + this.offset
            + " overflow=" + this.overflow + " bytes=" + this.bytes + ")";
    }

}

