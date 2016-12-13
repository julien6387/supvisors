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

import java.util.Arrays;
import java.util.ArrayList;
import java.util.List;
import java.util.HashMap;

/**
 * The Class XmlRpcConversion.
 *
 * It is used to convert raw results Object or Object[] into typed structures.
 */
public final class XmlRpcConversion {

    /**
     * The arrayToMap function creates a HashMap of typed results
     * from an array of Object instances.
     *
     * The type of the result must implement the SupervisorsAnyInfo interface
     * and provide a getName method.
     *
     * @param Object[] objectsArray: The array of Object instances.
     * @param Class<T> klass: The class that will hold the Object instances.
     * @return HashMap<String, T> result: The HashMap of typed results.
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
                System.err.println("XmlRpcConversion: " + exc);
            }
        }
        return infoMap;
    }

    /**
     * The arrayToStringList function creates a list of String from an array of Object instances.
     *
     * @param Object[] objectsArray: The array of Object instances.
     * @return List<String> result: The list of String results.
     */
    public static List<String> arrayToStringList(final Object[] objectArray) {
        return new ArrayList(Arrays.asList(objectArray));
    }

}

