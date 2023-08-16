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
    TRACE(5),
    DEBUG(10),
    INFO(20),
    WARN(30),
    ERROR(40),
    CRITICAL(50);

    /** The level code. */
    private int levelCode;

    /** The constructor links the state code to the state name. */
    private LoggerLevels(final int levelCode) {
        this.levelCode = levelCode;
    }

    /**
     * The getLevelCode method returns the value of the logger level.
     *
     * @return String: The value of the logger level.
     */
     public int getLevelCode() {
        return this.levelCode;
    }
}
