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
 * INITIALIZATION is used when Supvisors is synchronizing with all other Supvisors instances.
 * DEPLOYMENT is used when Supvisors is starting applications automatically.
 * OPERATION is used when Supvisors is working normally.
 * CONCILIATION is used when Supvisors is conciliating conflicts due to multiple instance of the same process.
 */
public enum SupvisorsState {
    INITIALIZATION(0),
    DEPLOYMENT(1),
    OPERATION(2),
    CONCILIATION(3),
    RESTARTING(4),
    SHUTTING_DOWN(5),
    FINAL(7);

    /** The state code. */
    private int stateCode;

    /** The constructor links the state code to the state name. */
    private SupvisorsState(final int stateCode) {
        this.stateCode = stateCode;
    }
}
