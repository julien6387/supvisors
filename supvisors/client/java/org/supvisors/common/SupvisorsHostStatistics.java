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

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The Class SupvisorsHostStatistics.
 *
 * It gives a structured form to the Supvisors Host Statistics information received from the event interface.
 */
public class SupvisorsHostStatistics {

    /**
     * The Class IOBytes.
     *
     * It stores the number of received and sent bytes on a given interface.
     */
     public class IOBytes {

        /** The number of bytes received/read on the interface. */
        private float recvBytes;

        /** The number of bytes sent/written on the interface. */
        private float sentBytes;

    /**
     * The IOBytes constructor.
     *
     * @param float recvBytes: The number of received/read bytes.
     * @param float sentBytes: The number of sent/written bytes.
     */
     public IOBytes(float recvBytes, float sentBytes) {
            this.recvBytes = recvBytes;
            this.sentBytes = sentBytes;
        }
    }

    /** The identifier of the Supvisors instance. */
    private String identifier;

    /** The configured integration period. */
    private Float target_period;

    /** The actual integration dates. */
    private List<Float> period;

    /** The CPU on the host during the period. */
    private List<Float> cpu;

    /** The current Memory occupation on the host. */
    private Float mem;

    /** The Network IO statistics. */
    private HashMap<String, List<Float>> net_io;

    /** The Disk IO statistics. */
    private HashMap<String, List<Float>> disk_io;

    /** The Disk usage statistics. */
    private HashMap<String, Float> disk_usage;

    /**
     * This constructor gets all information from a HashMap.
     * NOT USED but kept for future growth.
     *
     * @param HashMap statsInfo: The untyped structure got from the XML-RPC.
     */
    @SuppressWarnings({"unchecked"})
    public SupvisorsHostStatistics(HashMap statsInfo)  {
        this.identifier = (String) statsInfo.get("identifier");
        this.target_period = (Float) statsInfo.get("target_period");
        this.period = DataConversion.arrayToFloatList((Object[]) statsInfo.get("period"));
        this.cpu = DataConversion.arrayToFloatList((Object[]) statsInfo.get("cpu"));
        this.mem = (Float) statsInfo.get("memory");
        this.net_io = (HashMap<String, List<Float>>) statsInfo.get("net_io");
        this.disk_io = (HashMap<String, List<Float>>) statsInfo.get("disk_io");
        this.disk_usage = (HashMap<String, Float>) statsInfo.get("disk_usage");
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
     * The getTargetPeriod method returns the configured integration period.
     *
     * @return Float: The configured integration period.
     */
    public Float getTargetPeriod() {
        return this.target_period;
    }

    /**
     * The getStartPeriod method returns the start date of the integrated host statistics.
     * (end - start) is expected to be greater than the configured integration period.
     *
     * @return Float: The start date of the integrated host statistics.
     */
    public Float getStartPeriod() {
        return this.period.get(0);
    }

    /**
     * The getEndPeriod method returns the end date of the integrated host statistics.
     * (end - start) is expected to be greater than the configured integration period.
     *
     * @return Float: The node name of the Supvisors instance.
     */
    public Float getEndPeriod() {
        return this.period.get(1);
    }

    /**
     * The getAverageCPU method returns the average CPU (IRIX mode) on the host during the integration period.
     *
     * @return Float: The average CPU.
     */
    public Float getAverageCPU() {
        return this.cpu.get(0);
    }

    /**
     * The getDetailedCPU method returns the CPU (IRIX mode) on all host processor cores during the integration period.
     *
     * @return List<Float>: The CPU on every processor cores.
     */
    public List<Float> getDetailedCPU() {
        return this.cpu.subList(1, this.cpu.size() - 1);
    }

    /**
     * The getMemory method returns the memory occupation on the host during the integration period.
     *
     * @return Float: The memory occupation.
     */
    public Float getMemory() {
        return this.mem;
    }

    /**
     * The getNetworkIO method returns the number of received and sent bytes on every network interfaces.
     *
     * @return HashMap<String, List<Float>: The number of received and sent bytes per network interface.
     */
    public HashMap<String, List<Float>> getNetworkIO() {
        return this.net_io;
    }

    /**
     * The getDiskIO method returns the number of received and sent bytes on every physical devices.
     *
     * @return HashMap<String, List<Float>: The number of read and written bytes per physical device.
     */
    public HashMap<String, List<Float>> getDiskIO() {
        return this.disk_io;
    }

    /**
     * The getDiskUsage method returns the occupation percentage on every physical partitions.
     *
     * @return HashMap<String, Float: The occupation percentage per physical partition.
     */
    public HashMap<String, Float> getDiskUsage() {
        return this.disk_usage;
    }

    /**
     * The getNetworkInterfaces method returns the network interfaces names.
     *
     * @return Set<String>: The network interfaces names.
     */
    Set<String> getNetworkInterfaces() {
        return this.net_io.keySet();
    }

    /**
     * The getInterfaceBytes method returns the number of received and sent bytes on the given network interface.
     *
     * @param String: The network interface name among the elements provided by the getInterfaces method.
     * @return IOBytes: The number of received and sent bytes on the network interface.
     */
    IOBytes getInterfaceBytes(final String interfaceName) {
        List<Float> bytesList = this.net_io.get(interfaceName);
        return new IOBytes(bytesList.get(0).floatValue(), bytesList.get(1).floatValue());
    }

    /**
     * The toString method returns a printable form of the contents of the SupvisorsHostStatistics instance.
     *
     * @return String: The contents of the SupvisorsHostStatistics instance.
     */
    public String toString() {
        return "SupvisorsHostStatistics("
            + "identifier=" + this.identifier
            + " target_period=" + this.target_period
            + " startPeriod=" + this.getStartPeriod()
            + " endPeriod=" + this.getEndPeriod()
            + " cpu=" + this.getAverageCPU()
            + " memory=" + this.mem
            + " netIO=" + this.net_io
            + " diskIO=" + this.disk_io
            + " diskUsage=" + this.disk_usage
             + ")";
    }

}
