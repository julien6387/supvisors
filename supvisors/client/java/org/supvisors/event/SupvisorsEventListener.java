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

package org.supvisors.event;

import org.supvisors.common.SupvisorsApplicationInfo;
import org.supvisors.common.SupvisorsInstanceInfo;
import org.supvisors.common.SupvisorsHostStatistics;
import org.supvisors.common.SupvisorsProcessInfo;
import org.supvisors.common.SupvisorsProcessEvent;
import org.supvisors.common.SupvisorsProcessStatistics;
import org.supvisors.common.SupvisorsStatus;

/**
 * The Interface SupvisorsEventListener.
 *
 * It is used to receive Supvisors events.
 */
public interface SupvisorsEventListener {

    /**
     * The method is called when supvisors status subscription is set
     * and a SupvisorsStatus message is received.
     *
     * @param Supvisors Status: The last SupvisorsStatus received.
     */
    void onSupvisorsStatus(final SupvisorsStatus status);

    /**
     * The method is called when instance status subscription is set
     * and an Instance Status message is received.
     *
     * @param SupvisorsInstanceInfo: The last SupvisorsInstanceInfo received.
     */
    void onInstanceStatus(final SupvisorsInstanceInfo status);

    /**
     * The method is called when application status subscription is set
     * and an Application Status message is received.
     *
     * @param SupvisorsApplicationInfo: The last SupvisorsApplicationInfo received.
     */
    void onApplicationStatus(final SupvisorsApplicationInfo status);

    /**
     * The method is called when process status subscription is set
     * and a Process Status message is received.
     *
     * @param SupvisorsProcessInfo: The last SupvisorsProcessInfo received.
     */
    void onProcessStatus(final SupvisorsProcessInfo status);

    /**
     * The method is called when application subscription is set
     * and a Process Event message is received.
     *
     * @param SupvisorsProcessEvent: The last SupvisorsProcessEvent received.
     */
    void onProcessEvent(final SupvisorsProcessEvent status);

    /**
     * The method is called when host statistics subscription is set
     * and a Host Statistics message is received.
     *
     * @param SupvisorsHostStatistics: The last SupvisorsHostStatistics received.
     */
    void onHostStatistics(final SupvisorsHostStatistics statistics);

    /**
     * The method is called when host process subscription is set
     * and a Process Statistics message is received.
     *
     * @param SupvisorsProcessStatistics: The last SupvisorsProcessStatistics received.
     */
    void onProcessStatistics(final SupvisorsProcessStatistics statistics);
}
