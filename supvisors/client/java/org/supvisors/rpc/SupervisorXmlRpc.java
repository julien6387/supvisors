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

package org.supvisors.rpc;

import java.net.MalformedURLException;
import java.util.ArrayList;
import java.util.List;
import java.util.HashMap;
import org.supvisors.common.*;

/**
 * The Class SupervisorXmlRpc.
 *
 * It uses a SupervisorXmlRpcClient instance to perform XML-RPC requests related to the 'supervisor' namespace.
 * 
 * The Javadoc contains extracts from the Supervisor documentation.
 * http://supervisord.org/api.html
 */
public class SupervisorXmlRpc {

    /** The namespace of Supervisor requests. */
    private static final String Namespace = "supervisor.";

    /** The XML-RPC client. */
    private SupervisorXmlRpcClient client;

    /**
     * The constructor keeps a reference to the XML-RPC client.
     *
     * @param client the XML-RPC client connected to Supervisor
     */
    public SupervisorXmlRpc(SupervisorXmlRpcClient client)  {
        this.client = client;
    }

    /**
     * The getAPIVersion method returns the version of the RPC API used by supervisord.
     *
     * @return String: The version.
     */
    private String getAPIVersion() {
        return client.rpcCall(Namespace + "getAPIVersion", null, String.class);
    }

    /**
     * The getVersion method is an alias of getAPIVersion,
     * kept for backwards compatibility.
     *
     * @deprecated use {@link #getAPIVersion()} instead.
     * @return String: The version.
     */
    @Deprecated
    private String getVersion() {
        return client.rpcCall(Namespace + "getVersion", null, String.class);
    }

    /**
     * The getSupervisorVersion method returns the version of the supervisor package in use by supervisord.
     *
     * @return String: The version.
     */
    private String getSupervisorVersion() {
        return client.rpcCall(Namespace + "getSupervisorVersion", null, String.class);
    }

    /**
     * The getIdentification method returns the identifying string of supervisord.
     *
     * @return String: The id.
     */
    private String getIdentification() {
        return client.rpcCall(Namespace + "getIdentification", null, String.class);
    }

    /**
     * The getState method returns the current state of supervisord.
     *
     * @return SupervisorState: The current state of supervisord.
     */
    private SupervisorState getState() {
        HashMap result = client.rpcCall(Namespace + "getState", null, HashMap.class);
        return new SupervisorState(result);
    }

    /**
     * The getPID method returns the PID of supervisord.
     *
     * @return String: The documentation for the method name.
     */
    private Integer getPID() {
        return client.rpcCall(Namespace + "getPID", null, Integer.class);
    }

    /**
     * The readLog method read bytes from the main log starting at an offset.
     *
     * @param Integer offset: The offeset to start reading from.
     * @param Integer length: The number of bytes to read from the log.
     * @return String: Bytes of log.
     */
    private String readLog(Integer offset, Integer length) {
        Object[] params = new Object[]{offset, length};
        return client.rpcCall(Namespace + "readLog", params, String.class);
    }

    /**
     * The readMainLog method is an alias of the readLog,
     * kept for backwards compatibility.
     *
     * @deprecated use {@link #readLog()} instead.
     * @param Integer offset: The offeset to start reading from.
     * @param Integer length: The number of bytes to read from the log.
     * @return String: Bytes of log.
     */
     @Deprecated
    private String readMainLog(Integer offset, Integer length) {
        Object[] params = new Object[]{offset, length};
        return client.rpcCall(Namespace + "readMainLog", params, String.class);
    }

    /**
     * The clearLog method clears the main log.
     *
     * @return Boolean: Always true unless error.
     */
    private Boolean clearLog() {
        return client.rpcCall(Namespace + "clearLog", null, Boolean.class);
    }

    /**
     * The shutdown method shuts down the supervisor process.
     *
     * @return Boolean: Always true unless error.
     */
    private Boolean shutdown() {
        return client.rpcCall(Namespace + "shutdown", null, Boolean.class);
    }

    /**
     * The restart method restarts the supervisor process.
     *
     * @return Boolean: Always true unless error.
     */
    private Boolean restart() {
        return client.rpcCall(Namespace + "restart", null, Boolean.class);
    }

    /**
     * The getProcessInfo method gets information about a process.
     *
     * @param String namespec: The namespec of the process.
     * @return SupervisorProcessInfo: Information about the process.
     */
    private SupervisorProcessInfo getProcessInfo(final String namespec) {
        Object[] params = new Object[]{namespec};
        HashMap result = client.rpcCall(Namespace + "getProcessInfo", params, HashMap.class);
        return new SupervisorProcessInfo(result);
    }

    /**
     * The getAllProcessInfo method gets information about all processes.
     *
     * @return HashMap<String, SupervisorProcessInfo>: Information about all processes, sorted by namespec.
     */
    private HashMap<String, SupervisorProcessInfo> getAllProcessInfo() {
        Object[] objectsArray = client.rpcCall(Namespace + "getAllProcessInfo", null, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorProcessInfo.class);
    }

    /**
     * The startProcess method starts a process.
     * This method does not support a namespec like 'group:*' because the return type is different
     * (array instead of boolean) and it is not possible in JAVA.
     * To start a group, use {@link #startProcessGroup()}.
     *
     * @param String namespec: The namespec of the process (group:name).
     * @param Boolean wait: If true, wait for process to be fully started.
     * @return Boolean: Always true unless error.
     */
    private Boolean startProcess(final String namespec, final Boolean wait)  throws IllegalArgumentException {
        String[] names = DataConversion.namespecToStrings(namespec);
        if (names[1] == null) {
            throw new IllegalArgumentException("The namespec " + namespec + " is forbidden here, use startProcessGroup.");
        }
        Object[] params = new Object[]{namespec, wait};
        return client.rpcCall(Namespace + "startProcess", params, Boolean.class);
    }

    /**
     * The startAllProcesses method starts all processes listed in the configuration file.
     *
     * @param Boolean wait: If true, wait for processes to be fully started.
     * @return HashMap<String, SupervisorExecutionStatus>: The execution status of the commands, sorted by namespec.
     */
    private HashMap<String, SupervisorExecutionStatus> startAllProcesses(final Boolean wait) {
        Object[] params = new Object[]{wait};
        Object[] objectsArray = client.rpcCall(Namespace + "startAllProcesses", params, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorExecutionStatus.class);
    }

    /**
     * The startProcessGroup method returns starts all processes in the group.
     *
     * @param String groupName: The name of the group.
     * @param Boolean wait: If true, wait for processes to be fully started.
     * @return HashMap<String, SupervisorExecutionStatus>: The execution status of the commands, sorted by namespec.
     */
    private HashMap<String, SupervisorExecutionStatus> startProcessGroup(final String groupName, final Boolean wait) {
        Object[] params = new Object[]{groupName, wait};
        Object[] objectsArray = client.rpcCall(Namespace + "startProcessGroup", params, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorExecutionStatus.class);
    }

    /**
     * The stopProcess method returns stops a Process.
     * This method does not support a namespec like 'group:*' because the return type is different
     * (array instead of boolean) and it is not possible in JAVA.
     * To start a group, use {@link #stopProcessGroup()}.
     *
     * @param String namespec: The namespec of the process (group:name).
     * @param Boolean wait: If true, wait for process to be fully stopped.
     * @return Boolean: Always true unless error.
     */
    private Boolean stopProcess(final String namespec, final Boolean wait) {
        String[] names = DataConversion.namespecToStrings(namespec);
        if (names[1] == null) {
            throw new IllegalArgumentException("The namespec " + namespec + " is forbidden here, use startProcessGroup.");
        }
        Object[] params = new Object[]{namespec, wait};
        return client.rpcCall(Namespace + "stopProcess", params, Boolean.class);
    }

    /**
     * The stopProcessGroup method returns stops all processes in the group.
     *
     * @param String groupName: The name of the group.
     * @param Boolean wait: If true, wait for processes to be fully stopped.
     * @return HashMap<String, SupervisorExecutionStatus>: The execution status of the commands, sorted by namespec.
     */
    private HashMap<String, SupervisorExecutionStatus> stopProcessGroup(final String groupName, final Boolean wait) {
        Object[] params = new Object[]{groupName, wait};
        Object[] objectsArray = client.rpcCall(Namespace + "stopProcessGroup", params, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorExecutionStatus.class);
    }

    /**
     * The stopAllProcesses method stops all processes listed in the configuration file.
     *
     * @param Boolean wait: If true, wait for processes to be fully stopped.
     * @return HashMap<String, SupervisorExecutionStatus>: The execution status of the commands, sorted by namespec.
     */
    private HashMap<String, SupervisorExecutionStatus> stopAllProcesses(final Boolean wait) {
        Object[] params = new Object[]{wait};
        Object[] objectsArray = client.rpcCall(Namespace + "stopAllProcesses", params, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorExecutionStatus.class);
    }

    /**
     * The signalProcess method sends an arbitrary UNIX signal to the process named by name.
     *
     * @param String namespec: The name of the process to signal.
     * @param String signal: The signal to send, as name ('HUP') or number ('1')
     * @return Boolean: Always true unless error.
     */
    private Boolean signalProcess(final String namespec, final String signal) {
        Object[] params = new Object[]{namespec, signal};
        return client.rpcCall(Namespace + "signalProcess", params, Boolean.class);
    }

    /**
     * The signalProcessGroup method sends a signal to all processes in the group.
     *
     * @param String namespec: The name of the process to signal.
     * @param String signal: The signal to send, as name ('HUP') or number ('1')
     * @return HashMap<String, SupervisorExecutionStatus>: The execution status of the commands, sorted by namespec.
     */
    private HashMap<String, SupervisorExecutionStatus> signalProcessGroup(final String groupName, final String signal) {
        Object[] params = new Object[]{groupName, signal};
        Object[] objectsArray = client.rpcCall(Namespace + "signalProcessGroup", params, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorExecutionStatus.class);
    }

    /**
     * The signalAllProcesses method sends a signal to all processes in thr process list.
     *
     * @param String namespec: The name of the process to signal.
     * @param String signal: The signal to send, as name ('HUP') or number ('1')
     * @return HashMap<String, SupervisorExecutionStatus>: The execution status of the commands, sorted by namespec.
     */
    private HashMap<String, SupervisorExecutionStatus> signalAllProcesses(final String signal) {
        Object[] params = new Object[]{signal};
        Object[] objectsArray = client.rpcCall(Namespace + "signalAllProcesses", params, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorExecutionStatus.class);
    }

    /**
     * The sendProcessStdin method sends a string of chars to the stdin of the process.
     *
     * @param String namespec: The namespec of the process.
     * @param String chars: The character data to send to the process.
     * @return Boolean: Always true unless error.
     */
    private Boolean sendProcessStdin(final String namespec, final String chars) {
        Object[] params = new Object[]{namespec, chars};
        return client.rpcCall(Namespace + "sendProcessStdin", params, Boolean.class);
    }

    /**
     * The sendRemoteCommEvent method Send an event that will be received by event listener
     * subprocesses subscribing to the RemoteCommunicationEvent.
     *
     * @param String event_type: The string for the 'type' key in the event header.
     * @param String event_data: The data for the event body.
     * @return Boolean: Always true unless error.
     */
    private Boolean sendRemoteCommEvent(final String event_type, final String event_data) {
        Object[] params = new Object[]{event_type, event_data};
        return client.rpcCall(Namespace + "sendRemoteCommEvent", params, Boolean.class);
    }

    /**
     * The getAllConfigInfo method reloads the Supervisor configuration.
     * This is not documented in Supervisor documentation.
     *
     * @return HashMap<String, SupervisorConfigInfo>: The configurations, sorted by namespec.
     */
    private HashMap<String, SupervisorConfigInfo> getAllConfigInfo() {
        Object[] objectsArray = client.rpcCall(Namespace + "getAllConfigInfo", null, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorConfigInfo.class);
    }

    /**
     * The reloadConfig method reloads the Supervisor configuration.
     *
     * @return SupervisorConfigUpdates: The lists of added, modified, removed configurations.
     */
    private SupervisorConfigUpdates reloadConfig() {
        Object[] objectsArray = client.rpcCall(Namespace + "reloadConfig", null, Object[].class);
        return new SupervisorConfigUpdates(objectsArray);
    }

    /**
     * The addProcessGroup method updates the config for a running process from config file.
     *
     * @param String namespec: The name of the process group to add.
     * @return Boolean: The status indicating whether successful.
     */
    private Boolean addProcessGroup(final String namespec) {
        Object[] params = new Object[]{namespec};
        return client.rpcCall(Namespace + "addProcessGroup", params, Boolean.class);
    }

    /**
     * The removeProcessGroup method removes a stopped process from the active configuration.
     *
     * @param String namespec: The name of the process group to remove.
     * @return Boolean: The status indicating whether the removal was successful.
     */
    private Boolean removeProcessGroup(final String namespec) {
        Object[] params = new Object[]{namespec};
        return client.rpcCall(Namespace + "removeProcessGroup", params, Boolean.class);
    }

    /**
     * The readProcessStdoutLog method reads bytes from process' stdout starting at offset.
     *
     * @param String namespec: The namespec of the process.
     * @param Integer offset: The offeset to start reading from.
     * @param Integer length: The number of bytes to read from the log.
     * @return String: Bytes of log.
     */
    private String readProcessStdoutLog(final String namespec, final Integer offset, final Integer length) {
        Object[] params = new Object[]{namespec, offset, length};
        return client.rpcCall(Namespace + "readProcessStdoutLog", params, String.class);
    }

    /**
     * The readProcessLog method is an alias of readProcessStdoutLog,
     * kept for backwards compatibility.
     *
     * @deprecated use {@link #readProcessStdoutLog()} instead.
     * @param String namespec: The namespec of the process.
     * @param Integer offset: The offset to start reading from.
     * @param Integer length: The number of bytes to read from the log.
     * @return String: Bytes of log.
     */
    @Deprecated
    private String readProcessLog(final String namespec, final Integer offset, final Integer length) {
        Object[] params = new Object[]{namespec, offset, length};
        return client.rpcCall(Namespace + "readProcessLog", params, String.class);
    }

    /**
     * The readProcessStderrLog method reads bytes from process' stderr starting at offset.
     *
     * @param String namespec: The namespec of the process.
     * @param Integer offset: The offset to start reading from.
     * @param Integer length: The number of bytes to read from the log.
     * @return String: Bytes of log.
     */
    private String readProcessStderrLog(final String namespec, final Integer offset, final Integer length) {
        Object[] params = new Object[]{namespec, offset, length};
        return client.rpcCall(Namespace + "readProcessStderrLog", params, String.class);
    }

    /**
     * The tailProcessStdoutLog method provides a more efficient way to tail the stdout log.
     *
     * @param String namespec: The namespec of the process.
     * @param Integer offset: The offset to start reading from.
     * @param Integer length: The maximum number of bytes to return.
     * @return SupervisorLogResult: Structure including the bytes of log.
     */
    private SupervisorLogResult tailProcessStdoutLog(final String namespec, final Integer offset, final Integer length) {
        Object[] params = new Object[]{namespec, offset, length};
        Object[] objectsArray = client.rpcCall(Namespace + "tailProcessStdoutLog", params, Object[].class);
        return new SupervisorLogResult(objectsArray);
    }

    /**
     * The tailProcessLog method is an alias of tailProcessStdoutLog,
     * kept for backwards compatibility.
     *
     * @deprecated use {@link #tailProcessStdoutLog()} instead.
     * @param String namespec: The namespec of the process.
     * @param Integer offset: The offset to start reading from.
     * @param Integer length: The maximum number of bytes to return.
     * @return SupervisorLogResult: Structure including the bytes of log.
     */
    @Deprecated
    private SupervisorLogResult tailProcessLog(final String namespec, final Integer offset, final Integer length) {
        Object[] params = new Object[]{namespec, offset, length};
        Object[] objectsArray = client.rpcCall(Namespace + "tailProcessLog", params, Object[].class);
        return new SupervisorLogResult(objectsArray);
    }

    /**
     * The tailProcessStderrLog method provides a more efficient way to tail the stderr log.
     *
     * @param String namespec: The namespec of the process.
     * @param Integer offset: The offset to start reading from.
     * @param Integer length: The maximum number of bytes to return.
     * @return SupervisorLogResult: Structure including the bytes of log.
     */
    private SupervisorLogResult tailProcessStderrLog(final String namespec, final Integer offset, final Integer length) {
        Object[] params = new Object[]{namespec, offset, length};
        Object[] objectsArray = client.rpcCall(Namespace + "tailProcessStderrLog", params, Object[].class);
        return new SupervisorLogResult(objectsArray);
    }

    /**
     * The clearProcessLogs method clears the stdout and stderr logs
     * for the named process and reopens them.
     *
     * @param String namespec: The namespec of the process.
     * @return Boolean: Always True unless error.
     */
    private Boolean clearProcessLogs(final String namespec) {
        Object[] params = new Object[]{namespec};
        return client.rpcCall(Namespace + "clearProcessLogs", params, Boolean.class);
    }

    /**
     * The clearProcessLog method is an alias of clearProcessLogs,
     * kept for backwards compatibility.
     *
     * @deprecated use {@link #clearProcessLogs()} instead.
     * @param String namespec: The namespec of the process.
     * @return Boolean: Always True unless error.
     */
    @Deprecated
    private Boolean clearProcessLog(final String namespec) {
        Object[] params = new Object[]{namespec};
        return client.rpcCall(Namespace + "clearProcessLog", params, Boolean.class);
    }

    /**
     * The clearAllProcessLogs method clears all process log files.
     *
     * @return HashMap<String, SupervisorExecutionStatus>: The execution status of the commands, sorted by namespec.
     */
    private HashMap<String, SupervisorExecutionStatus> clearAllProcessLogs() {
        Object[] objectsArray = client.rpcCall(Namespace + "clearAllProcessLogs", null, Object[].class);
        return DataConversion.arrayToMap(objectsArray, SupervisorExecutionStatus.class);
    }


    /**
     * The main for Supvisors self-tests.
     *
     * @param String[] args: The arguments.
     */
    public static void main(String[] args) throws InterruptedException, MalformedURLException {
        SupervisorXmlRpcClient client = new SupervisorXmlRpcClient(60000);
        SupervisorXmlRpc supervisor = new SupervisorXmlRpc(client);

        // test supervisor status and control
        System.out.println("### Testing supervisor.getAPIVersion(...) ###");
        System.out.println(supervisor.getAPIVersion());
        System.out.println("### Testing supervisor.getVersion(...) ###");
        System.out.println(supervisor.getVersion());
        System.out.println("### Testing supervisor.getSupervisorVersion(...) ###");
        System.out.println(supervisor.getSupervisorVersion());
        System.out.println("### Testing supervisor.getIdentification(...) ###");
        System.out.println(supervisor.getIdentification());
        System.out.println("### Testing supervisor.getState(...) ###");
        System.out.println(supervisor.getState());
        System.out.println("### Testing supervisor.getPID(...) ###");
        System.out.println(supervisor.getPID());
        System.out.println("### Testing supervisor.readLog(...) ###");
        System.out.println(supervisor.readLog(-100, 0));
        System.out.println("### Testing supervisor.clearLog(...) ###");
        System.out.println(supervisor.clearLog());
        System.out.println("### Testing supervisor.readMainLog(...) ###");
        System.out.println(supervisor.readMainLog(0, 100));

        // first remove test group, so as it does not interfere with this test
        System.out.println("### Testing supervisor.removeProcessGroup(...) ###");
        System.out.println(supervisor.removeProcessGroup("test"));

        // test supervisor process control
        System.out.println("### Testing supervisor.getAllProcessInfo(...) ###");
        HashMap<String, SupervisorProcessInfo> processes = supervisor.getAllProcessInfo();
        System.out.println(processes);
        System.out.println("### Testing supervisor.getProcessInfo(...) ###");
        String namespec = "player:movie_player";
        SupervisorProcessInfo processInfo = supervisor.getProcessInfo(namespec);
        System.out.println(processInfo);
        System.out.println("### Testing supervisor.startAllProcesses(...) ###");
        System.out.println(supervisor.startAllProcesses(true));

        // startAllProcesses is demanding, so let Supervisor breathe
        Thread.sleep(1000);

        System.out.println("### Testing supervisor.stopAllProcesses(...) ###");
        System.out.println(supervisor.stopAllProcesses(true));

        // startAllProcesses is demanding, so let Supervisor breathe
        Thread.sleep(1000);

        System.out.println("### Testing supervisor.startProcessGroup(...) ###");
        System.out.println(supervisor.startProcessGroup(processInfo.getGroupName(), true));
        System.out.println("### Testing supervisor.stopProcessGroup(...) ###");
        System.out.println(supervisor.stopProcessGroup(processInfo.getGroupName(), true));
        System.out.println("### Testing supervisor.startProcess(...) ###");
        System.out.println(supervisor.startProcess(namespec, true));
        System.out.println("### Testing supervisor.stopProcess(...) ###");
        System.out.println(supervisor.stopProcess(namespec, true));
        System.out.println("### Testing supervisor.startProcessGroup(...) ###");
        System.out.println(supervisor.startProcessGroup(processInfo.getGroupName(), true));

        // test UNIX signal
        System.out.println("### Testing supervisor.signalProcessGroup(...) ###");
        System.out.println(supervisor.signalProcessGroup(processInfo.getGroupName(), "STOP"));
        System.out.println("### Testing supervisor.signalProcess(...) ###");
        System.out.println(supervisor.signalProcess(namespec, "CONT"));
        System.out.println("### Testing supervisor.signalAllProcesses(...) ###");
        System.out.println(supervisor.signalAllProcesses("18"));

        // test process stdin
        System.out.println("### Testing supervisor.sendProcessStdin(...) ###");
        System.out.println(supervisor.sendProcessStdin(namespec, "hello"));

        // test comm event
        System.out.println("### Testing supervisor.sendRemoteCommEvent(...) ###");
        System.out.println(supervisor.sendRemoteCommEvent("hello", "world"));

        // test process logging
        System.out.println("### Testing supervisor.readProcessStdoutLog(...) ###");
        System.out.println(supervisor.readProcessStdoutLog(namespec, 0, 100));
        System.out.println("### Testing supervisor.readProcessLog(...) ###");
        System.out.println(supervisor.readProcessLog(namespec, 0, 100));
        System.out.println("### Testing supervisor.readProcessStderrLog(...) ###");
        System.out.println(supervisor.readProcessStderrLog(namespec, 0, 100));
        System.out.println("### Testing supervisor.tailProcessStdoutLog(...) ###");
        System.out.println(supervisor.tailProcessStdoutLog(namespec, 0, 100));
        System.out.println("### Testing supervisor.tailProcessLog(...) ###");
        System.out.println(supervisor.tailProcessLog(namespec, 0, 100));
        System.out.println("### Testing supervisor.tailProcessStderrLog(...) ###");
        System.out.println(supervisor.tailProcessStderrLog(namespec, 0, 100));
        System.out.println("### Testing supervisor.clearProcessLogs(...) ###");
        System.out.println(supervisor.clearProcessLogs(namespec));
        System.out.println("### Testing supervisor.clearProcessLog(...) ###");
        System.out.println(supervisor.clearProcessLog(namespec));
        System.out.println("### Testing supervisor.clearAllProcessLogs(...) ###");
        System.out.println(supervisor.clearAllProcessLogs());

        // test group config
        System.out.println("### Testing supervisor.addProcessGroup(...) ###");
        System.out.println(supervisor.addProcessGroup("test"));
        System.out.println("### Testing supervisor.getAllConfigInfo(...) ###");
        System.out.println(supervisor.getAllConfigInfo());
        System.out.println("### Testing supervisor.reloadConfig(...) ###");
        System.out.println(supervisor.reloadConfig());

        // test supervisor control
        Thread.sleep(2000);

        System.out.println("### Testing supervisor.restart(...) ###");
        System.out.println(supervisor.restart());

        // the following methods are operational but not tested automatically
        System.out.println("### NOT TESTED: supervisor.shutdown(...) ###");
        // System.out.println(supervisor.shutdown());
    }
}
