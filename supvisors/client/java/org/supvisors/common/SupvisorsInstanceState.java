/*
 * Copyright 2023 Julien LE CLEACH
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
 * The SupvisorsInstanceState enumeration.
 *
 * STOPPED:   used when the local Supvisors instance does not receive any heartbeat message from the remote Supvisors instance (default state).
 * CHECKING:  used when the local Supvisors instance is checking the status of the remote Supvisors instance.
 * CHECKED:   used when the local Supvisors instance has checked the status of the remote Supvisors instance.
 * RUNNING:   used when the local Supvisors instance is ready to work with the remote Supvisors instance.
 * FAILED:    used when the local Supvisors instance fails to communicate with the remote Supvisors instance.
 * ISOLATED:  used when the local Supvisors instance has actually disconnected the remote Supvisors instance.
 */
public enum SupvisorsInstanceState {
    STOPPED(0),
    CHECKING(1),
    CHECKED(2),
    RUNNING(3),
    FAILED(4),
    ISOLATED(5);

    /** The state code. */
    private final int state;

    /** The constructor links the state code to the state name. */
    private SupvisorsInstanceState(int state) {
        this.state = state;
    }
}
