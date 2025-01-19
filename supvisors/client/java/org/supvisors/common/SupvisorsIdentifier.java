/*
 * Copyright 2025 Julien LE CLEACH
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

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;


/**
 * The Class SupvisorsIdentifier.
 *
 * It groups the identifier and nickname of the Supvisors instance received from XML-RPC or the event interface.
 * To benefit from the automatic JSON unmarshalling, the attributes must be written exactly as in the payload.
 */
public class SupvisorsIdentifier {

    /** The identifier of the Supvisors instance. */
    private String identifier;

    /** The nickname of the Supervisor instance. */
    private String nick_identifier;

    /**
     * The constructor gets the identifier information from an HashMap.
     *
     * @param HashMap info: The untyped structure got from the XML-RPC.
     */
    public SupvisorsIdentifier(HashMap info)  {
        this.identifier = (String) info.get("identifier");
        this.nick_identifier = (String) info.get("nick_identifier");
    }

    /**
     * The constructor gets the identifier information from two Stings.
     *
     * @param String identifier: The identifier of the Supvisors instance.
     * @param String nickIdentifier: The nickname of the Supvisors instance.
     */
    public SupvisorsIdentifier(String identifier, String nickIdentifier)  {
        this.identifier = identifier;
        this.nick_identifier = nickIdentifier;
    }

    /**
     * The getName method returns the usage identifier of the Supvisors instance.
     *
     * @return String: The usage identifier of the Supvisors instance.
     */
    public String getName() {
        if (this.identifier == this.nick_identifier)
            return this.identifier;
        return "<" + this.nick_identifier + ">" + this.identifier;
    }

    /**
     * The getIdentifier method returns the identifier of the Supvisors instance.
     *
     * @return String: The identifier of the Supvisors instance.
     */
    public String getIdentifier() {
        return this.identifier;
    }

    /**
     * The getNickIdentifier method returns the nickname of the Supervisor instance.
     *
     * @return String: The nickname of the Supervisor instance.
     */
    public String getNickIdentifier() {
        return this.nick_identifier;
    }

    /**
     * The toString method returns a printable form of the SupvisorsIdentifier instance.
     *
     * @return String: The contents of the SupvisorsIdentifier.
     */
    public String toString() {
        return "SupvisorsStatus(identifier=" + this.identifier
            + " nickIdentifier=" + this.nick_identifier
            + " usageIdentifier=" + this.getName() + ")";
    }

}
