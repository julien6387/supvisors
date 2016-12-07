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

    /* TODO: add all Supervisor RPC
supervisor.addProcessGroup, supervisor.clearAllProcessLogs, supervisor.clearLog, supervisor.clearProcessLog, supervisor.clearProcessLogs, supervisor.getAllConfigInfo, supervisor.getAllProcessInfo, supervisor.getPID, supervisor.getProcessInfo, supervisor.getVersion, supervisor.readLog, supervisor.readMainLog, supervisor.readProcessLog, supervisor.readProcessStderrLog, supervisor.readProcessStdoutLog, supervisor.reloadConfig, supervisor.removeProcessGroup, supervisor.restart, supervisor.sendProcessStdin, supervisor.sendRemoteCommEvent, supervisor.shutdown, supervisor.signalAllProcesses, supervisor.signalProcess, supervisor.signalProcessGroup, supervisor.startAllProcesses, supervisor.startProcess, supervisor.startProcessGroup, supervisor.stopAllProcesses, supervisor.stopProcess, supervisor.stopProcessGroup, supervisor.tailProcessLog, supervisor.tailProcessStderrLog, supervisor.tailProcessStdoutLog */

    /**
     * The getAPIVersion method returns the version of the RPC API used by supervisord.
     *
     * @return String: The version.
     */
    private String getAPIVersion() {
        return client.rpcCall(Namespace + "getAPIVersion", null, String.class);
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
     * The xxx method returns xxx.
     *
     * @param String methodName: The name of the method.
     * @return String: The documentation for the method name.
     */
    private String getXXX() {
        return client.rpcCall(Namespace + "xxx", null, String.class);
    }


    /**
     * The main for Supervisors self-tests.
     *
     * @param String[] args: The arguments.
     */
    public static void main(String[] args) {
        SupervisorXmlRpcClient client = null;
        try {
            client = new SupervisorXmlRpcClient(60000);
        } catch(Exception exc) {
            System.err.println("SupervisorsXmlRpc: " + exc);
        }

        if  (client != null) {
            SupervisorXmlRpc supervisor = new SupervisorXmlRpc(client);
            // test supervisor status
            System.out.println(supervisor.getAPIVersion());
            System.out.println(supervisor.getSupervisorVersion());
            System.out.println(supervisor.getIdentification());
            System.out.println(supervisor.getState());
            // to be cont'd'
        }
    }
}
