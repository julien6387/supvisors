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

package org.supervisors;

import java.util.List;
import java.util.HashMap;
    
/**
 * The Class SupervisorsXmlRpc.
 *
 * It uses a SupervisorXmlRpcClient instance to perform XML-RPC requests related to the 'supervisors' namespace.
 * The Javadoc contains extracts from the Supervisors documentation.
 */
public class SupervisorsXmlRpc {

    /**
     * The DeploymentStrategy enumeration.
     *
     * CONFIG strategy takes the first address that can handle the new process,
     *     keeping the ordering set in the deployment file.
     * LESS_LOADED takes among all the addresses that can handle the new process,
     *     the one having the lower expected loading.
     * MOST_LOADED takes among all the addresses that can handle the new process,
     *     the one having the highest expected loading.
     */
    public enum DeploymentStrategy {
        CONFIG,
        LESS_LOADED,
        MOST_LOADED;
    }

    /** The namespace of System requests in Supervisor. */
    private static final String Namespace = "supervisors.";

    /** The XML-RPC client. */
    private SupervisorXmlRpcClient client;

    /**
     * The constructor keeps a reference to the XML-RPC client.
     *
     * @param SupervisorXmlRpcClient client: The XML-RPC client connected to Supervisor.
     */
    public SupervisorsXmlRpc(final SupervisorXmlRpcClient client)  {
        this.client = client;
    }

    /**
     * The getAPIVersion methods returns the version of the RPC API used by Supervisors.
     *
     * @return String: The version.
     */
    private String getAPIVersion() {
        return client.rpcCall(Namespace + "get_api_version", null, String.class);
    }

    /**
     * The getSupervisorsState methods returns the state of Supervisors.
     *
     * @return SupervisorsState: The state of Supervisors.
     */
    public SupervisorsState getSupervisorsState() {
        HashMap result = client.rpcCall(Namespace + "get_supervisors_state", null, HashMap.class);
        return new SupervisorsState(result);
    }

    /**
     * The getMasterAddress methods returns the address of the Supervisors Master.
     *
     * @return String: An IPv4 address or a host name.
     */
    public String getMasterAddress() {
        return client.rpcCall(Namespace + "get_master_address", null, String.class);
    }

    /**
     * The getAllAddressesInfo methods returns information about the addresses known in Supervisors.
     *
     * @return HashMap<String, SupervisorsAddressInfo>: Information for all address, sorted by name.
     */
    public HashMap<String, SupervisorsAddressInfo> getAllAddressesInfo() {
        Object[] objectsArray = client.rpcCall(Namespace + "get_all_addresses_info", null, Object[].class);
        return XmlRpcConversion.arrayToMap(objectsArray, SupervisorsAddressInfo.class);
    }

    /**
     * The getAddressInfo methods returns information about an address known in Supervisors.
     *
     * @param String addressName: The name of the address.
     * @return SupervisorsAddressInfo: Information about the address.
     */
    public SupervisorsAddressInfo getAddressInfo(final String addressName) {
        Object[] params = new Object[]{addressName};
        HashMap result = client.rpcCall(Namespace + "get_address_info", params, HashMap.class);
        return new SupervisorsAddressInfo(result);
    }

    /**
     * The getAllApplicationInfo methods returns information about the applications known in Supervisors.
     *
     * @return HashMap<String, SupervisorsApplicationInfo>: Information for all applications, sorted by name.
     */
    public HashMap<String, SupervisorsApplicationInfo> getAllApplicationInfo() {
        Object[] objectsArray = client.rpcCall(Namespace + "get_all_applications_info", null, Object[].class);
        return XmlRpcConversion.arrayToMap(objectsArray, SupervisorsApplicationInfo.class);
    }

    /**
     * The getApplicationInfo methods returns information about an application known in Supervisors.
     *
     * @param String applicationName: The name of the application.
     * @return SupervisorsApplicationInfo: Information about the application.
     */
    public SupervisorsApplicationInfo getApplicationInfo(final String applicationName) {
        Object[] params = new Object[]{applicationName};
        HashMap result = client.rpcCall(Namespace + "get_application_info", params, HashMap.class);
        return new SupervisorsApplicationInfo(result);
    }

    /**
     * The getProcessInfo methods returns information about processes known in Supervisors.
     * It just complements the supervisor.getProcessInfo by telling where the process is running.
     *
     * @param String namespec: The name of the process (or "applicationName:processName", or "applicationName:*").
     * @return HashMap<String, SupervisorsProcessInfo>: Information about the process, sorted by namespec.
     */
    public HashMap<String, SupervisorsProcessInfo> getProcessInfo(final String namespec) {
        Object[] params = new Object[]{namespec};
        Object[] objectsArray = client.rpcCall(Namespace + "get_process_info", params, Object[].class);
        return XmlRpcConversion.arrayToMap(objectsArray, SupervisorsProcessInfo.class);
    }

    /**
     * The getProcessRules methods returns rules used to start/stop processes known in Supervisors.
     *
     * @param String namespec: The name of the process (or "applicationName:processName", or "applicationName:*").
     * @return HashMap<String, SupervisorsProcessRules>: The rules of the processes, sorted by namespec.
     */
    public HashMap<String, SupervisorsProcessRules> getProcessRules(final String namespec) {
        Object[] params = new Object[]{namespec};
        Object[] objectsArray = client.rpcCall(Namespace + "get_process_rules", params, Object[].class);
        return XmlRpcConversion.arrayToMap(objectsArray, SupervisorsProcessRules.class);
    }

    /**
     * The getConflicts methods returns the conflicting processes.
     *
     * @return HashMap<String, SupervisorsProcessInfo>: The list of conflicting processes, sorted by namespec.
     */
    public HashMap<String, SupervisorsProcessInfo> getConflicts() {
        Object[] objectsArray = client.rpcCall(Namespace + "get_conflicts", null, Object[].class);
        return XmlRpcConversion.arrayToMap(objectsArray, SupervisorsProcessInfo.class);
    }

    /**
     * The startApplication methods starts the processes of the application, in accordance with the rules configured
     * in the deployment file for the application and its processes.
     *
     * @param DeploymentStrategy strategy: The strategy used for choosing addresses.
     * @param String applicationName: The name of the application to start.
     * @param Boolean wait: If true, the RPC returns only when the application is fully started.
     * @return Boolean: Always True unless error or nothing to start.
     */
    public Boolean startApplication(final DeploymentStrategy strategy, final String applicationName, final Boolean wait) {
        Object[] params = new Object[]{strategy.ordinal(), applicationName, wait};
        return client.rpcCall(Namespace + "start_application", params, Boolean.class);
    }

    /**
     * The stopApplication methods stops the processes of the application, in accordance with the rules configured
     * in the deployment file for the application and its processes.
     *
     * @param String applicationName: The name of the application to stop.
     * @param Boolean wait: If true, the RPC returns only when the application is fully started.
     * @return Boolean: Always True unless error or nothing to stop.
     */
    public Boolean stopApplication(final String applicationName, final Boolean wait) {
        Object[] params = new Object[]{applicationName, wait};
        return client.rpcCall(Namespace + "stop_application", params, Boolean.class);
    }

    /**
     * The restartApplication methods restarts the processes of the application, in accordance with the rules configured
     * in the deployment file for the application and its processes.
     *
     * @param DeploymentStrategy strategy: The strategy used for choosing addresses.
     * @param String applicationName: The name of the application to restart.
     * @param Boolean wait: If true, the RPC returns only when the application is fully restarted.
     * @return Boolean: Always True unless error or nothing to start.
     */
    public Boolean restartApplication(final DeploymentStrategy strategy, final String applicationName, final Boolean wait) {
        Object[] params = new Object[]{strategy.ordinal(), applicationName, wait};
        return client.rpcCall(Namespace + "restart_application", params, Boolean.class);
    }

    /**
     * The startArgs methods starts a process on the local address.
     * The behaviour is different from 'supervisor.startProcess' as it sets the process state to FATAL
     * instead of throwing an exception to the RPC client.
     * This method makes it also possible to pass extra arguments to the program command line.
     *
     * @param String namespec: The name of the process to start.
     * @param String extraArgs: The extra arguments to be passed to the command line of the program.
     * @param Boolean wait: If true, the RPC returns only when the process is fully started.
     * @return Boolean: Always True unless error or nothing to start.
     */
    public Boolean startArgs(final String namespec, final String extraArgs, final Boolean wait) {
        Object[] params = new Object[]{namespec, extraArgs, wait};
        return client.rpcCall(Namespace + "start_args", params, Boolean.class);
    }

    /**
     * The startProcess methods starts a process, in accordance with the rules ('wait_exit' excepted)
     * configured in the deployment file for the application and its processes.
     * This method makes it also possible to pass extra arguments to the program command line.
     *
     * @param DeploymentStrategy strategy: The strategy used for choosing addresses.
     * @param String namespec: The name of the process to start.
     * @param String extraArgs: The extra arguments to be passed to the command line of the program.
     * @param Boolean wait: If true, the RPC returns only when the process is fully started.
     * @return Boolean: Always True unless error or nothing to start.
     */
    public Boolean startProcess(final DeploymentStrategy strategy, final String namespec,
            final String extraArgs, final Boolean wait) {
        Object[] params = new Object[]{strategy.ordinal(), namespec, extraArgs, wait};
        return client.rpcCall(Namespace + "start_process", params, Boolean.class);
    }

    /**
     * The stopProcess methods stops a process where it is running.
     *
     * @param String namespec: The name of the process to start.
     * @param Boolean wait: If true, the RPC returns only when the process is fully stopped.
     * @return Boolean: Always True unless error or nothing to stop.
     */
    public Boolean stopProcess(final String namespec, final Boolean wait) {
        Object[] params = new Object[]{namespec, wait};
        return client.rpcCall(Namespace + "stop_process", params, Boolean.class);
    }

    /**
     * The restartProcess methods restarts a process, in accordance with the rules ('wait_exit' excepted)
     * configured in the deployment file for the application and its processes.
     *
     * @param DeploymentStrategy strategy: The strategy used for choosing addresses.
     * @param String namespec: The name of the process to restart.
     * @param String extraArgs: The extra arguments to be passed to the command line of the program.
     * @param Boolean wait: If true, the RPC returns only when the process is fully restarted.
     * @return Boolean: Always True unless error or nothing to start.
     */
    public Boolean restartProcess(final DeploymentStrategy strategy, final String namespec,
            final String extraArgs, final Boolean wait) {
        Object[] params = new Object[]{strategy.ordinal(), namespec, extraArgs, wait};
        return client.rpcCall(Namespace + "restart_process", params, Boolean.class);
    }

    /**
     * The restart methods restarts Supervisors through all the Supervisor instances.
     *
     * @return Boolean: Always True unless error.
     */
    public Boolean restart() {
        return client.rpcCall(Namespace + "restart", null, Boolean.class);
    }

    /**
     * The shutdown methods shuts down Supervisors through all the Supervisor instances.
     *
     * @return Boolean: Always True unless error.
     */
    public Boolean shutdown() {
        return client.rpcCall(Namespace + "shutdown", null, Boolean.class);
    }


    /**
     * The main for Supervisors self-tests.
     *
     * @param String[] args: The arguments.
     */
    public static void main (String[] args) {
        // TODO: add port in parameter
        // how to do with ant ?
        SupervisorXmlRpcClient client = null;
        try {
            client = new SupervisorXmlRpcClient(60000);
        } catch(Exception exc) {
            System.err.println("SupervisorsXmlRpc: " + exc);
        }

        if  (client != null) {
            SupervisorsXmlRpc supervisors = new SupervisorsXmlRpc(client);
            // test supervisors status
            System.out.println(supervisors.getAPIVersion());
            System.out.println(supervisors.getSupervisorsState());
            System.out.println(supervisors.getMasterAddress());
            // test address status rpc
            HashMap<String, SupervisorsAddressInfo> addresses = supervisors.getAllAddressesInfo();
            System.out.println(addresses);
            String addressName = addresses.entrySet().iterator().next().getValue().getName();
            SupervisorsAddressInfo addressInfo = supervisors.getAddressInfo(addressName);
            System.out.println(addressInfo);
            // test application status rpc
            HashMap<String, SupervisorsApplicationInfo> applications = supervisors.getAllApplicationInfo();
            System.out.println(applications);
            String applicationName = applications.entrySet().iterator().next().getValue().getName();
            SupervisorsApplicationInfo applicationInfo = supervisors.getApplicationInfo(applicationName);
            System.out.println(applicationInfo);
            // test process status rpc
            HashMap<String, SupervisorsProcessInfo> processes = supervisors.getProcessInfo(applicationName + ":*");
            System.out.println(processes);
            String processName = processes.entrySet().iterator().next().getValue().getName();
            processes = supervisors.getProcessInfo(processName);
            System.out.println(processes);
            // test process rules rpc
            HashMap<String, SupervisorsProcessRules> rules = supervisors.getProcessRules(applicationName + ":*");
            System.out.println(rules);
            processName = rules.entrySet().iterator().next().getValue().getName();
            rules = supervisors.getProcessRules(processName);
            System.out.println(rules);
            // test process conflicts rpc
            HashMap<String, SupervisorsProcessInfo> conflicts = supervisors.getConflicts();
            System.out.println(conflicts);
            // test application request rpc
            supervisors.restartApplication(DeploymentStrategy.LESS_LOADED, "my_movies", true);
            supervisors.stopApplication("my_movies", true);
            supervisors.startApplication(DeploymentStrategy.CONFIG, "my_movies", false);
            // test process request rpc
            supervisors.startArgs("my_movies:converter_01", "-x 3", false);
            supervisors.startProcess(DeploymentStrategy.MOST_LOADED, "my_movies:converter_02", "", false);
            supervisors.restartProcess(DeploymentStrategy.CONFIG, "my_movies:converter_02", "", true);
            supervisors.stopProcess("my_movies:converter_02", false);
            supervisors.startProcess(DeploymentStrategy.MOST_LOADED, "my_movies:converter_03", "-x 8", true);
            supervisors.restartProcess(DeploymentStrategy.LESS_LOADED, "my_movies:converter_03", "-x 4", true);
            // restart and shutdown are working but not tested automatically
            // supervisors.restart();
            // supervisors.shutdown();
        }
    }

}
