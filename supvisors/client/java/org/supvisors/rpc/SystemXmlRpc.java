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
import java.util.List;
import java.util.HashMap;
import org.apache.xmlrpc.XmlRpcException;
import org.supvisors.common.DataConversion;

/**
 * The Class SystemXmlRpc.
 *
 * It uses a SupervisorXmlRpcClient instance to perform XML-RPC requests related to the 'system' namespace.
 * This 'namespace' provides the user with methods for help, multi-calls, etc.
 * 
 * The Javadoc contains extracts from the Supervisor documentation.
 * http://supervisord.org/api.html#system-methods
 */
public class SystemXmlRpc {

    /** The namespace of System requests in Supervisor. */
    private static final String Namespace = "system.";

    /** The XML-RPC client. */
    private SupervisorXmlRpcClient client;

    /**
     * The constructor keeps a reference to the XML-RPC client.
     *
     * @param SupervisorXmlRpcClient client: The XML-RPC client connected to Supervisor.
     */
    public SystemXmlRpc(SupervisorXmlRpcClient client)  {
        this.client = client;
    }

    /**
     * The listMethods method returns a listing of the available method names.
     *
     * @return List<String>: the names of the methods available.
     */
    public List<String> listMethods() throws XmlRpcException {
        Object[] objectArray = client.rpcCall(Namespace + "listMethods", null, Object[].class);
        return DataConversion.arrayToStringList(objectArray);
    }

    /**
     * The methodHelp method returns a string showing the method's documentation.
     *
     * @param String methodName: The name of the method.
     * @return String: The documentation for the method name.
     */
    public String methodHelp(final String methodName) throws XmlRpcException {
        Object[] params = new Object[]{methodName};
        return client.rpcCall(Namespace + "methodHelp", params, String.class);
    }

    /**
     * The methodSignature method returns an array describing the method signature
     * in the form [rtype, ptype, ptype...] where rtype is the return data type of the method,
     * and ptypes are the parameter data types that the method accepts in method argument order.
     *
     * @param String methodName: The name of the method.
     * @return List<String>: The signature of the method, as a list of strings.
     */
    public List<String> methodSignature(final String methodName) throws XmlRpcException {
        Object[] params = new Object[]{methodName};
        Object[] objectArray = client.rpcCall(Namespace + "methodSignature", params, Object[].class);
        return DataConversion.arrayToStringList(objectArray);
    }

    /**
     * The multicall method processes an array of calls, and return an array of results.
     *
     * Calls should be structs of the form {'methodName': string, 'params': array}.
     * Each result will either be a single-item array containing the result value,
     * or a struct of the form {'faultCode': int, 'faultString': string}.
     *
     *  This is useful when you need to make lots of small calls without lots of round trips.
     *
     * @param Object[] arrayCalls: An array of call requests.
     * @return Object[]: An array of results.
     */
    public Object[] multicall(final Object[] arrayCalls) throws XmlRpcException {
        Object[] params = new Object[]{arrayCalls};
        return client.rpcCall(Namespace + "multicall", params, Object[].class);
    }

    /**
     * The createCall function creates an entry for a multicall usage.
     *
     * @param String methodName: The name of the method.
     * @param Object[] args: The arguments of the method.
     * @return HashMap: The call request.
     */
    public static HashMap createCall(final String methodName, final Object[] args) {
        HashMap<String, Object> call = new HashMap<String, Object>();
        call.put("methodName", methodName);
        if (args != null) {
            call.put("params", args);
        }
        return call;
    }


    /**
     * The main for Supvisors self-tests.
     *
     * @param String[] args: The arguments.
     */
    public static void main(String[] args) throws MalformedURLException, XmlRpcException {
        SupervisorXmlRpcClient client = new SupervisorXmlRpcClient(60000);
        SystemXmlRpc system = new SystemXmlRpc(client);

        // test help methods
        System.out.println("### Testing system.listMethods() ###");
        System.out.println(system.listMethods());
        System.out.println("### Testing system.methodHelp(...) ###");
        System.out.println(system.methodHelp("system.methodSignature"));
        System.out.println("### Testing system.methodSignature(...) ###");
        System.out.println(system.methodSignature("system.methodSignature"));

        // test multiCall
        System.out.println("### Testing system.multicall(...) ###");
        HashMap call1 = system.createCall("system.listMethods", null);
        HashMap call2 = system.createCall("system.methodHelp", new Object[]{"system.methodSignature"});
        HashMap call3 = system.createCall("system.methodSignature", new Object[]{"system.methodSignature"});
        HashMap call4 = system.createCall("system.methodHelp", new Object[]{"dummy"});
        Object[] results = system.multicall(new Object[]{call1, call2, call3, call4});

        // first result is an Object array made of String objects (see conversion in listMethods)
        List<String> result = DataConversion.arrayToStringList((Object[]) results[0]);
        System.out.println("# Got results for system.listMethods: " + result);

        // second result is a String
        System.out.println("# Got results for system.methodHelp: " + results[1]);

        // third result is an Object array made of String objects (see conversion in methodSignature)
        result = DataConversion.arrayToStringList((Object[]) results[2]);
        System.out.println("# Got results for system.methodSignature: " + result);

        // fourth result should be an error
        System.out.println("# Got error for system.methodSignature: " + (HashMap) results[3]);
    }
}
