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

import java.net.URL;
import java.net.MalformedURLException;
import org.apache.xmlrpc.client.XmlRpcClient;
import org.apache.xmlrpc.client.XmlRpcClientConfigImpl;
    
/**
 * The Class SupervisorXmlRpcClient.
 *
 * It connects to the XML-RPC server of Supervisor.
 * It contains methods to perform XML-RPC and to return the results in a more user-friendly way.
 */
public class SupervisorXmlRpcClient {

    /** The Apache XML-RPC client. */
    private XmlRpcClient client = new XmlRpcClient();

    /**
     * The constructor performs the connection with the XML-RPC server of the local Supervisor,
     * without HTTP authentification.
     *
     * @param int port: The port used to connect the server.
     */
    public SupervisorXmlRpcClient(final int port) throws MalformedURLException {
        this("localhost", port, "", "");
    }

    /**
     * The constructor performs the connection with the XML-RPC server of the Supervisor running on address,
     * without HTTP authentification.
     *
     * @param String address: The host name or IP address.
     * @param int port: The port used to connect the server.
     */
    public SupervisorXmlRpcClient(final String address, final int port) throws MalformedURLException {
        this(address, port, "", "");
    }

    /**
     * The constructor performs the connection with the XML-RPC server of the Supervisor running on address,
     * with basic HTTP authentification.
     *
     * @param String address: The host name or IP address.
     * @param int port: The port used to connect the server.
     * @param String userName: The user name.
     * @param String password: The password of the user.
     */
    public SupervisorXmlRpcClient(final String address, final int port,
            final String userName, final String password) throws MalformedURLException {
        XmlRpcClientConfigImpl config = new XmlRpcClientConfigImpl();
        config.setServerURL(new URL("http://" + address + ":" + port + "/RPC2"));
        config.setBasicUserName(userName);
        config.setBasicPassword(password);
        client.setConfig(config);
    }

    /**
     * The rpcCall method performs a generic XML-RPC.
     *
     * @param String rpcName: The name of the XML-RPC.
     * @param Object[] args: The additional arguments passed to the XML-RPC.
     * @param Class<T> type: The class T used to type the result.
     * @return T result: The result of the XML-RPC.
     */
    @SuppressWarnings({"unchecked"})
    public <T> T rpcCall(final String rpcName, final Object[] args, final Class<T> type) {
        T result = null;
        try {
            result = (T) client.execute(rpcName, args);
        } catch (Exception exception) {
            System.err.println("SupervisorXmlRpcClient: " + exception);
        }
        return result;
    }

}
