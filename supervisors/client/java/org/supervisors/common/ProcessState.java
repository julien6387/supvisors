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


/**
 * The ProcessState enumeration.
 *
 * See the description in the Supervisor documentation.
 * http://supervisord.org/subprocess.html#process-states
 */
public enum ProcessState {
    STOPPED(0),
    STARTING(10),
    RUNNING(20),
    BACKOFF(30),
    STOPPING(40),
    EXITED(100),
    FATAL(200),
    UNKNOWN(1000);

    /** The state code. */
    private int stateCode;

    /** The constructor links the state code to the state name. */
    private ProcessState(final int stateCode) {
        this.stateCode = stateCode;
    }
}

