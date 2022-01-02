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
import org.supvisors.common.SupvisorsNodeInfo;
import org.supvisors.common.SupvisorsProcessInfo;
import org.supvisors.common.SupvisorsProcessEvent;
import org.supvisors.common.SupvisorsStatus;

/**
 * The Interface SupvisorsEventListener.
 *
 * It is used to receive Supvisors events.
 */
public interface SupvisorsEventListener {

    /**
     * The method is called when supvisors subscription is set
     * and a SupvisorsStatus message is received.
     *
     * @param Supvisors Status: The last SupvisorsStatus received.
     */
    void onSupvisorsStatus(final SupvisorsStatus status);

    /**
     * The method is called when node subscription is set
     * and a Node Status message is received.
     *
     * @param SupvisorsNodeInfo: The last SupvisorsNodeInfo received.
     */
    void onNodeStatus(final SupvisorsNodeInfo status);

    /**
     * The method is called when application subscription is set
     * and an Application Status message is received.
     *
     * @param SupvisorsApplicationInfo: The last SupvisorsApplicationInfo received.
     */
    void onApplicationStatus(final SupvisorsApplicationInfo status);

    /**
     * The method is called when application subscription is set
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
}

