/*
 * Copyright 2017 Julien LE CLEACH
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
 * The RunningFailureStrategy enumeration.
 */
public enum RunningFailureStrategy {
    CONTINUE(0),
    RESTART_PROCESS(1),
    STOP_APPLICATION(2),
    RESTART_APPLICATION(3);

    /** The strategy code. */
    private int strategyCode;

    /** The constructor links the state code to the state name. */
    private RunningFailureStrategy(final int strategyCode) {
        this.strategyCode = strategyCode;
    }
}

