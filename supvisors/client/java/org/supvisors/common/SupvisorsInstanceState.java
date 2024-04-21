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
 * UNKNOWN:   used at initialization, before any heartbeat message is received from this Supvisors instance.
 * CHECKING:  used when the local Supvisors is checking the status of the remote Supvisors instance.
 * CHECKED:   used when the local Supvisors has checked the status of the remote Supvisors instance.
 * RUNNING:   used when the local Supvisors is ready to work with the remote Supvisors instance.
 * SILENT:    used when the local Supvisors does not receive any heartbeat message from this Supvisors instance.
 * ISOLATED:  used when the local Supvisors has actually disconnected this Supvisors instance.
 */
public enum SupvisorsInstanceState {
    UNKNOWN(0),
    CHECKING(1),
    CHECKED(2),
    RUNNING(3),
    SILENT(4),
    ISOLATED(5);

    /** The state code. */
    private final int state;

    /** The constructor links the state code to the state name. */
    private SupvisorsInstanceState(int state) {
        this.state = state;
    }
}
