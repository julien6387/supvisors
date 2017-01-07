Dashboard
=========

Each Supervisor instance provides a Web Server and the Supvisors extension provides the following web user interface, as a replacement of the Supervisor one.

Pages are not auto-refreshed.
The 'Refresh' button on the top right corner of all pages does the job.

Note about the browser compliance

As the present documentation, the CSS of the web pages has been written for Firefox ESR 45.4.0.
The compatibility with other browsers or other versions of Firefox is unknown.

All pages are divided into 3 parts:

    the Common Menu on the left side,
    a header on the top right,
    the contents itself on the lower right.

Common Menu
-----------
Menu

Clicking on 'Supvisors' brings the Main page back or the Conciliation page if it blinks in red.
The version of Supvisors is displayed.

Below is the Addresses part that lists all the addresses defined in the supvisors section of the Supervisor configuration file.
The color gives the state of the Address, as seen by the Supvisors instance that is displaying this page:

    grey for UNKNOWN,
    grey-to-green gradient for CHECKING,
    yellow for SILENT,
    green for RUNNING,
    red for ISOLATED.

Only the hyperlinks of the RUNNING addresses are active. The browser is redirected to the Address page of the corresponding Web Server.
The Supvisors instance playing the role of "Master" is pointed out with the ✪ sign.

Below is the Application part that lists all the applications defined through the group sections of the Supervisor configuration file.
The color gives the state of the Application, as seen by the Supvisors instance that is displaying this page:

    grey for UNKNOWN,
    yellow for STOPPED,
    yellow-to-green gradient for STARTING,
    green-to-yellow gradient for STOPPING,
    green for RUNNING.

All hyperlinks are active. The browser is redirected to the corresponding Application page on the local Web Server.

The bottom part of the menu contains a contact link and copyright information.

Main page
---------

The Main page shows a synoptic of the Supvisors status.
Main page
Supvisors Main page

Main page Header
~~~~~~~~~~~~~~~~

The state of Supvisors is displayed on the left side of the header:

    INITIALISATION corresponds to the Supvisors starting phase, waiting for all Supvisors instances to connect themselves,
    DEPLOYMENT corresponds to the phase when Supvisors is automatically starting applications (here for more details),
    OPERATION corresponds to the supervising phase in which the Supvisors XML-RPC are available,
    CONCILIATION corresponds to the phase when Supvisors is solving conflicts (here for more details).

On the right side, 3 buttons are available:

    Restart button restarts Supvisors through all Supervisor instances,
    Shutdown button shuts down Supvisors through all Supervisor instances,
    Refresh button refreshes the current page.

Main page Contents
~~~~~~~~~~~~~~~~~~

For every addresses, a box is displayed in the contents of the Supervisor Main page.
Each box contains:

    the address name, which is a hyperlink to the corresponding Address page if the Address state is RUNNING,
    the state of the Address, colord with the same rules used in the Menu,
    the process loading of the Address,
    the list of all processes that are running on this address.

Conciliation page
-----------------

If the page is refreshed when Supvisors is in Conciliation state, the 'Supvisors' label in the top left of the common Menu becomes red and blinks.
This situation is unlikely to happen if the Conciliation Strategy chosen in the Supvisors section of the configuration file is different from USER.

The Conciliation page can be reached by clicking on this blinking red label.
Conciliation page
Supvisors Conciliation page

Conciliation page Header
~~~~~~~~~~~~~~~~~~~~~~~~

The header of the Conciliation page has exactly the same contents as the header of the Main page.

Conciliation page Contents
~~~~~~~~~~~~~~~~~~~~~~~~~~

On the right side of the page, the list of process conflicts is displayed into a table.
A process conflict is raised when the same program is running on several machines.

So the tables lists, for each conflict:

    * the name of the program incriminated,
    * the list of addresses where it is running,
    * the uptime of the corresponding process on each address,
    * for each process, a list of actions helping to the solving of this conflict:

        + Stop the process,
        + Keep this process (and Stop all others),

    * for each process, a list of automatic strategies (details) helping to the solving of this conflict.

The left side of the page contains a simple box that enables the user to perform a global conciliation on all conflicts, using one of the automatic strategies.

Address page
------------

The Address page of Supvisors is a bit less "sparse" than the web page provided by Supervisor.
It shows the status of the address, as seen by the local Supvisors instance, enables the user to command the processes declared on this address and provides statistics that may be useful at software integration time.
Address page
Supvisors Address page

Address page Header
~~~~~~~~~~~~~~~~~~~

The status of the Address is displayed on the left side of the header:

    * the name of the address, marked with the ✪ sign if it corresponds to the "Master",
    * the current loading of the processes running on this address,
    * the state of this address,
    * the date of the last tick received from Supervisor on this address.

In the middle of the header, the 'Statistics Period' box enables the user to choose the period used for the statistics of this page.
The periods can be updated in the Supvisors section of the Supervisor configuration file.

On the right side, 4 buttons are available:

    * Stop button stops all processes handled by Supervisor on this address,
    * Restart button restarts Supervisor on this address,
    * Shutdown button shuts down Supervisor on this address,
    * Refresh button refreshes the current page.

Address page Contents
~~~~~~~~~~~~~~~~~~~~~

The contents of the Address page is divided in two parts.

The upper part looks like the page provided by Supervisor. Indeed, it lists the programs that are configured in Supervisor, it presents their current state with an associated description and enables the user to perform some actions on them: log tail (with a refresh button, click on the name itself), Start, Stop, Restart, Clear log, Tail log (auto-refreshed).

Supvisors shows additional information for each process, such as:

    * the loading declared for the process in the deployment file,
    * the CPU usage of the process during the last period (only if the process is RUNNING),
    * the instant memory (Resident Set Size) occupation of the process at the last period tick (only if the process is RUNNING),

A click on the CPU or RAM measures shows detailed statistics about the process.
More particularly, Supvisors shows a graph built from the series of measures taken from the selected resource:

    * the history of the values with a plain line,
    * the mean value with a dashed line and value in the top right corner,
    * the linear regression with a straight dotted line,
    * the standard deviation with a colored area around the mean value.

Underneath is a table showing for both CPU and Memory:

    * the last measure,
    * the mean value,
    * the value of the slope of the linear regression,
    * the value of the standard deviation.

A color and a sign are associated to the last value, so that:

    * green and ↗ point out a significant increase of the value since the last measure,
    * red and ↘ point out a significant decrease of the value since the last measure,
    * blue and ↝ point out the stability of the value since the last measure,

The lower part of the page contains CPU, Memory and Network statistics for the considered address.
The CPU table shows statistics about the CPU on each core of the processor and about the average CPU of the processor.
The Memory table shows statistics about the amount of used (and not available) memory.
The Network table shows statistics about the receive and sent flows on each network interface.
Clicking on a button associated to the resource displays detailed statistics (graph and table), similarly to the process buttons.

Application page
----------------

The Application page of Supvisors shows the status of the application, as seen by the requested Supvisors instance, enables the user to command the application and its processes, and provides statistics that may be useful at software integration time.
Application page
Supvisors Application page

Application page Header
~~~~~~~~~~~~~~~~~~~~~~~

The status of the Address is displayed on the left side of the header:

    * the name of the application,
    * the state of this address,
    * a led corresponding to the operational status of the application:

        + empty if not RUNNING,
        + red if RUNNING and at least one major failure is detected,
        + orange if RUNNING and at least one minor failure is detected, and no major failure,
        + green if RUNNING and no failure is detected.

The second part of the header is the 'Deployment strategy' box that enables the user to choose the strategy to start the application programs listed below.
Strategies are detailed here.

The third part of the header is the 'Statistics Period' box that enables the user to choose the period used for the statistics of this page.
The periods can be updated in the Supvisors section of the Supervisor configuration file.

On the right side, 4 buttons are available:

    * Start button starts the application,
    * Stop button stops the application,
    * Restart button restarts the application,
    * Refresh button refreshes the current page.

Application page Contents
~~~~~~~~~~~~~~~~~~~~~~~~~

The table lists all the programs belonging to the application, and it shows:

    * the 'synthetic' state of the process (refer to this note for details about the synthesis),
    * the address where it runs, if appropriate,
    * the loading declared for the process in the deployment file,
    * the CPU usage of the process during the last period (only if the process is RUNNING),
    * the instant memory (Resident Set Size) occupation of the process at the last period tick (only if the process is RUNNING),

Like the Address page, the Application page enables the user to perform some actions on programs: Start, Stop, Restart.
The difference is that the process is not started necessarily on the address that displays this page.
Indeed, Supvisors uses the rules of the program (as defined in the deployment file) and the deployment strategy selected in the header part to choose a relevant address.

As previously, a click on the CPU or RAM measures shows detailed statistics about the process.

