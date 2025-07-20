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
 * The State enumeration for Supvisors.
 *
 * OFF is the Supvisors entry state, used until the local Supvisors instance is operational.
 * SYNCHRONIZATION is used when Supvisors is synchronizing all Supvisors instances.
 * ELECTION is used when Supvisors is electing the Supvisors Master instance (must be unanimous).
 * DISTRIBUTION is used when Supvisors is starting applications automatically.
 * OPERATION is used when Supvisors is working normally.
 * CONCILIATION is used when Supvisors is conciliating conflicts due to multiple instance of the same process.
 * RESTARTING is used when Supvisors is stopping all processes before restarting all Supvisors instances.
 * SHUTTING_DOWN is used when Supvisors is stopping all processes before shutting down all Supvisors instances.
 * FINAL is used just before Supvisors is shut down.
 */
public enum SupvisorsState {
    OFF(0),
    SYNCHRONIZATION(1),
    ELECTION(2),
    DISTRIBUTION(3),
    OPERATION(4),
    CONCILIATION(5),
    RESTARTING(6),
    SHUTTING_DOWN(7),
    FINAL(8);

    /** The state code. */
    private int stateCode;

    /** The constructor links the state code to the state name. */
    private SupvisorsState(final int stateCode) {
        this.stateCode = stateCode;
    }
}
