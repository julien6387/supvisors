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

package org.supervisors.event;

import org.supervisors.common.SupervisorsAddressInfo;
import org.supervisors.common.SupervisorsApplicationInfo;
import org.supervisors.common.SupervisorsProcessInfo;
import org.supervisors.common.SupervisorsStatus;

/**
 * The Interface SupervisorsEventListener.
 *
 * It is used to receive Supervisors events.
 */
public interface SupervisorsEventListener {

    /**
     * The method is called when supervisors subscription is set
     * and a SupervisorsStatus message is received.
     *
     * @param SupervisorsStatus: The last SupervisorsStatus received.
     */
    void onSupervisorsStatus(final SupervisorsStatus status);

    /**
     * The method is called when address subscription is set
     * and an AddressStatus message is received.
     *
     * @param SupervisorsAddressInfo: The last SupervisorsAddressInfo received.
     */
    void onAddressStatus(final SupervisorsAddressInfo status);

    /**
     * The method is called when application subscription is set
     * and an ApplicationStatus message is received.
     *
     * @param SupervisorsApplicationInfo: The last SupervisorsApplicationInfo received.
     */
    void onApplicationStatus(final SupervisorsApplicationInfo status);

    /**
     * The method is called when application subscription is set
     * and a ProcessStatus message is received.
     *
     * @param SupervisorsProcessInfo: The last SupervisorsProcessInfo received.
     */
    void onProcessStatus(final SupervisorsProcessInfo status);

}

