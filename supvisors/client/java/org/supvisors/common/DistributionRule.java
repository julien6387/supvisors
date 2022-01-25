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
 * The DistributionRule enumeration.
 */
public enum DistributionRule {
    ALL_INSTANCES(0),
    SINGLE_INSTANCE(1),
    SINGLE_NODE(2);

    /** The distribution code. */
    private int distributionCode;

    /** The constructor links the state code to the state name. */
    private DistributionRule(final int distributionCode) {
        this.distributionCode = distributionCode;
    }
}
