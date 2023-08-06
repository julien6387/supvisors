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
 * The LoggerLevels enumeration.
 */
public enum LoggerLevels {
    BLATHER(3),
    TRACE(1),
    DEBUG(2),
    INFO(3),
    WARN(4),
    ERROR(5),
    CRITICAL(5);

    /** The level code. */
    private int levelCode;

    /** The constructor links the state code to the state name. */
    private LoggerLevels(final int levelCode) {
        this.levelCode = levelCode;
    }
}
