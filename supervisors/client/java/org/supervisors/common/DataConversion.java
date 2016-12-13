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

package org.supervisors.common;

import java.util.Arrays;
import java.util.ArrayList;
import java.util.List;
import java.util.HashMap;

/**
 * The Class DataConversion.
 *
 * It is used to convert raw results Object or Object[] into typed structures.
 */
public final class DataConversion {

    /**
     * The arrayToMap function creates a HashMap of typed results
     * from an array of Object instances.
     *
     * The type of the result must implement the SupervisorsAnyInfo interface
     * and provide a getName method.
     *
     * @param Object[] objectsArray: The array of Object instances.
     * @param Class<T> klass: The class that will hold the Object instances.
     * @return HashMap<String, T>: The HashMap of typed results.
     */
    public static <T extends SupervisorsAnyInfo> HashMap<String, T> arrayToMap(
            final Object[] objectsArray, final Class<T> klass) {
        HashMap<String, T> infoMap = new HashMap<String, T>();
        for (int i=0 ; i<objectsArray.length ; i++) {
            try {
                final HashMap map = (HashMap) objectsArray[i];
                final T info = klass.getDeclaredConstructor(map.getClass()).newInstance(map);
                infoMap.put(info.getName(), info);
            } catch (Exception exc) {
                System.err.println("DataConversion: " + exc);
            }
        }
        return infoMap;
    }

    /**
     * The arrayToStringList function creates a list of String from an array of Object instances.
     *
     * @param Object[] objectsArray: The array of Object instances.
     * @return List<String>: The list of String results.
     */
    public static List<String> arrayToStringList(final Object[] objectArray) {
        return new ArrayList(Arrays.asList(objectArray));
    }

    /**
     * The namespecToStrings function splits a namespec into group and process names.
     * The function accepts 3 patterns:
     *     "processName" returns ["processName", "processName"],
     *     "groupName:processName" returns ["groupName", "processName"],
     *     "groupName:*" returns ["groupName", null]
     *
     * @param String namespec: The namespec.
     * @return String[]: The split names.
     */
    public static String[] namespecToStrings(final String namespec) {
        String[] split =  namespec.split(":");
        if (split.length > 2) {
            throw new IllegalArgumentException("Separator used more than once in namespec.");
        }
        if (split.length == 1) {
            // no separator
            return new String[]{namespec, namespec};
        }
        if ("*".equals(split[1])) {
            // use of wildcard
            return new String[]{split[0], null};
        }
        return split;
    }

    /**
     * The stringsToNamespec function joins group and process names into a namspec.
     * The function accepts 3 patterns:
     *     "processName" + "processName" returns "processName",
     *     "groupName" + "processName" returns "groupName:processName",
     *     "groupName" + null returns "groupName:*".
     *
     * @param String groupName: The name of the process' group.
     * @param String processName: The name of the process.
     * @return String: The corresponding namespec.
     */
    public static String stringsToNamespec(final String groupName, final String processName) {
        if ((groupName == null) || (groupName.equals(processName))) {
            return processName;
        }
        if (processName == null) {
            return groupName + ":*";
        }
        return groupName + ":" + processName;
    }

    /**
     * The main for Supervisors self-tests.
     *
     * @param String[] args: The arguments.
     */
    public static void main (String[] args) {
        // test the namespecToStrings function
        System.out.println(Arrays.asList(namespecToStrings("processName")));
        System.out.println(Arrays.asList(namespecToStrings("groupName:processName")));
        System.out.println(Arrays.asList(namespecToStrings("groupName:*")));
        // test the stringsToNamespec function
        System.out.println(stringsToNamespec("processName", "processName"));
        System.out.println(stringsToNamespec("groupName", "processName"));
        System.out.println(stringsToNamespec("groupName", null));
    }

}

