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

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The Class SupvisorsNetworkInfo.
 *
 * It gives a structured form to the Supvisors Instance network info received from a XML-RPC.
 * Keep a snake-case format for attributes, as a harmonization principle.
 */

public class SupvisorsNetworkInfo implements SupvisorsAnyInfo {

    /** Identification of a Network Interface Card (NIC). */
    public class NicInformation {

        /** The network interface name. */
        private String nic_name;

        /** The IPv4 address of the host in the network interface context. */
        private String ipv4_address;

        /** The network mask of the host in the network interface context. */
        private String netmask;

        /**
         * This constructor gets all information from an HashMap.
         *
         * @param HashMap info: The untyped structure got from the XML-RPC.
         */
        public NicInformation(HashMap info)  {
            this.nic_name = (String) info.get("nic_name");
            this.ipv4_address = (String) info.get("ipv4_address");
            this.netmask = (String) info.get("netmask");
        }

        /**
         * The getNicName method returns the NIC name.
         *
         * @return String: The NIC name.
         */
        public String getNicName() {
            return this.nic_name;
        }

        /**
         * The getIpv4Address method returns the IPv4 address linked to the host on the NIC.
         *
         * @return String: The IPv4 address.
         */
        public String getIpv4Address() {
            return this.ipv4_address;
        }

        /**
         * The getNetmask method returns the netmask linked to the host on the NIC.
         *
         * @return String: The network interface mask.
         */
        public String getNetmask() {
            return this.netmask;
        }

        /**
         * The toString method returns a printable form of the SupvisorsStatus instance.
         *
         * @return String: The contents of the SupvisorsStatus.
         */
        public String toString() {
            return "NicInformation(nicName=" + this.nic_name
                + " IPv4Address=" + this.ipv4_address
                + " netmask=" + this.netmask + ")";
        }
    }

    /** All address representations for one network interface. */
    public class NetworkAddress {

        /** The host name, as a fully qualified domain name if available, linked to the network interface. */
        private String host_name;

        /** The host aliases. */
        private List<String> aliases;

        /** The IPv4 addresses found. */
        private List<String> ipv4_addresses;

        /** The identifier of the Supvisors instance. */
        private NicInformation nic_info;

        /**
         * This constructor gets all information from an HashMap.
         *
         * @param HashMap info: The untyped structure got from the XML-RPC.
         */
        public NetworkAddress(HashMap info)  {
            this.host_name = (String) info.get("host_name");
            Object[] aliases = (Object[]) info.get("aliases");
            this.aliases = DataConversion.arrayToStringList(aliases);
            Object[] ipv4_addresses = (Object[]) info.get("ipv4_addresses");
            this.ipv4_addresses = DataConversion.arrayToStringList(ipv4_addresses);
            Object nic_info = info.get("nic_info");
            if (nic_info != null) {
                this.nic_info = new NicInformation((HashMap) nic_info);
            }
        }

        /**
         * The getHostName method returns the host name found from the NIC IPv4 address.
         *
         * @return String: The host name.
         */
        public String getHostName() {
            return this.host_name;
        }

        /**
         * The getAliases method returns the host aliases found from the NIC IPv4 address.
         *
         * @return List<String>: The host aliases.
         */
        public List<String> getAliases() {
            return this.aliases;
        }

        /**
         * The getIpv4Addresses method returns the IPv4 addresses found from the NIC IPv4 address.
         *
         * @return List<String>: The host IPv4 addresses.
         */
        public List<String> getIpv4Addresses() {
            return this.ipv4_addresses;
        }

        /**
         * The getNicInfo method returns the NIC information.
         *
         * @return NicInformation: The network interface information.
         */
        public NicInformation getNicInfo() {
            return this.nic_info;
        }

        /**
         * The toString method returns a printable form of the SupvisorsStatus instance.
         *
         * @return String: The contents of the SupvisorsStatus.
         */
        public String toString() {
            return "NetworkAddress(hostName=" + this.host_name
                + " aliases=" + this.aliases
                + " IPv4Addresses=" + this.ipv4_addresses
                + " nicInfo=" + (this.nic_info != null ? this.nic_info.toString() : null) + ")";
        }
    }

    public class LocalNetwork {

        /** The host UUID. */
        private String machine_id;

        /** The fully-qualified domain name of the host. */
        private String fqdn;

        /** The network information per NIC name. */
        private HashMap<String, NetworkAddress> addresses;

        /**
         * This constructor gets all information from an HashMap.
         *
         * @param HashMap info: The untyped structure got from the XML-RPC.
         */
        @SuppressWarnings({"unchecked"})
        public LocalNetwork(HashMap info)  {
            this.machine_id = (String) info.get("machine_id");
            this.fqdn = (String) info.get("fqdn");
            // no safe way to convert an Object to HashMap
            this.addresses = new HashMap<String, NetworkAddress>();
            HashMap<String, Object> addresses = (HashMap<String, Object>) info.get("addresses");
            for (Map.Entry<String, Object> entry : addresses.entrySet()) {
                this.addresses.put(entry.getKey(), new NetworkAddress((HashMap) entry.getValue()));
            }
        }

        /**
         * The getMachineId method returns the host UUID.
         *
         * @return String: The host UUID.
         */
        public String getMachineId() {
            return this.machine_id;
        }

        /**
         * The getMachineId method returns the host fully-qualified domain name.
         *
         * @return String: The host FQDN.
         */
        public String getFqdn() {
            return this.fqdn;
        }

        /**
         * The getAddresses method returns the network information per NIC.
         *
         * @return HashMap<String, NetworkAddress>: All network information.
         */
        public HashMap<String, NetworkAddress> getAddresses() {
            return this.addresses;
        }

        /**
         * The toString method returns a printable form of the SupvisorsStatus instance.
         *
         * @return String: The contents of the SupvisorsStatus.
         */
        public String toString() {
            String networkString = "";
            for (Map.Entry<String, NetworkAddress> entry : this.addresses.entrySet()) {
                networkString += entry.getKey() + "=" + entry.getValue().toString() + " ";
            }
            return "LocalNetwork(machineId=" + this.machine_id
                + " fqdn=" + this.fqdn
                + " network={" + networkString + "})";
        }
    }

    /** The identifier of the Supvisors instance. */
    private SupvisorsIdentifier identifier;

    /** The Supvisors instance host id. */
    private String host_id;

    /** The Supvisors instance HTTP port. */
    private Integer http_port;

    /** The Supervisor instance stereotypes. */
    private List<String> stereotypes;

    /** The Supvisors instance network information. */
    private LocalNetwork network;

    /**
     * This constructor gets all information from an HashMap.
     *
     * @param HashMap info: The untyped structure got from the XML-RPC.
     */
    @SuppressWarnings({"unchecked"})
    public SupvisorsNetworkInfo(HashMap info)  {
        this.identifier = new SupvisorsIdentifier(info);
        this.host_id = (String) info.get("host_id");
        this.http_port = (Integer) info.get("http_port");
        Object[] stereotypes = (Object[]) info.get("stereotypes");
        this.stereotypes = DataConversion.arrayToStringList(stereotypes);
        // no safe way to convert an Object to HashMap
        Object network = info.get("network");
        if (network != null) {
            this.network = new LocalNetwork((HashMap) network);
        }
    }

    /**
     * The getName method uses the getIdentifier method.
     *
     * @return String: The identifier of the Supvisors instance.
     */
    public String getName() {
        return this.identifier.getIdentifier();
    }

    /**
     * The getIdentifier method returns the identification of the Supvisors instance,
     * as a SupvisorsIdentifier instance.
     *
     * @return String: The identifier of the Supvisors instance.
     */
     public SupvisorsIdentifier getIdentifier() {
        return this.identifier;
    }

    /**
     * The getHostId method returns the Supvisors instance host id.
     *
     * @return String: The host id.
     */
    public String getHostId() {
        return this.host_id;
    }

    /**
     * The getHttpPort method returns the Supvisors instance HTTP port.
     *
     * @return Integer: The HTTP port.
     */
    public Integer getHttpPort() {
        return this.http_port;
    }

    /**
     * The getNetwork method returns the network information of the host where the Supvisors instance is running.
     *
     * @return LocalNetwork: The network information.
     */
    public LocalNetwork getNetwork() {
        return this.network;
    }

    /**
     * The toString method returns a printable form of the SupvisorsStatus instance.
     *
     * @return String: The contents of the SupvisorsStatus.
     */
    public String toString() {
        return "SupvisorsNetworkInfo(identifier=" + this.identifier.toString()
            + " hostId=" + this.host_id
            + " httpPort=" + this.http_port
            + " network=" + this.network.toString() + ")";
    }

}
