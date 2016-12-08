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
 * The SupervisorFaults enumeration.
 *
 * These are the faults defined in the supervisor.xmlprc module
 */
public enum SupervisorFaults {
    UNKNOWN_METHOD(1),
    INCORRECT_PARAMETERS(2),
    BAD_ARGUMENTS(3),
    SIGNATURE_UNSUPPORTED(4),
    SHUTDOWN_STATE(6),
    BAD_NAME(10),
    BAD_SIGNAL(11),
    NO_FILE(20),
    NOT_EXECUTABLE(21),
    FAILED(30),
    ABNORMAL_TERMINATION(40),
    SPAWN_ERROR(50),
    ALREADY_STARTED(60),
    NOT_RUNNING(70),
    SUCCESS(80),
    ALREADY_ADDED(90),
    STILL_RUNNING(91),
    CANT_REREAD(92);

    /** The fault code. */
    private int faultCode;

    /** The mapping between fault codes and enumeration values. */
    private static HashMap<Integer, SupervisorFaults> mapping = new HashMap<Integer, SupervisorFaults>();

    /** Initialization of the static map. */
    static {
        for (SupervisorFaults fault : SupervisorFaults.values()) {
            mapping.put(fault.faultCode, fault);
        }
    }

    /** The constructor links the fault code to the fault name. */
    private SupervisorFaults(final int faultCode) {
        this.faultCode = faultCode;
    }

    /**
     * The getFault function returns the enumeration value associated to the fault code.
     *
     * @param int faultCode: The fault code.
     * @return SupervisorFaults: the corresponding enumeration
     */
    public static SupervisorFaults getFault(final int faultCode) {
        return mapping.get(faultCode);
    }

}

