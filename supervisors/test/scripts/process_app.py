#!/usr/bin/python
#-*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ======================================================================

from Tkinter import *

class ProcessAppTk(Tk):

    def __init__(self, namespec, description):
        """ Initialization of the attributes. """
        Tk.__init__(self, None)
        self.title(u'Supervisors')
        self.grid()
        # create main form
        formWindow = PanedWindow(self, orient=VERTICAL)
        # display namespec into a PanedWindow
        mainWindow = PanedWindow(formWindow, orient=VERTICAL)
        mainWindow.add(Label(mainWindow, text=u'Supervisors namespec: {}'.format(namespec)))
        if description:
            mainWindow.add(Label(mainWindow, text=u'Supervisors description: {}'.format(description)))
        # add window to form and pack it
        formWindow.add(mainWindow)
        formWindow.pack()
        # Actions
        Button(self, text=u"close", command=self.quit).pack(side=BOTTOM, padx=10, pady=2)
        # window properties
        self.grid_columnconfigure(0, weight=1)
        self.resizable(False, False)

    def quit(self):
        print('Quit called')
        Tk.quit(self)


if __name__ == "__main__":
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Start a dummy window named with a namespec.')
    parser.add_argument('-n', '--namespec', required=True, help='the namespec of the program')
    parser.add_argument('-x', '--xkill', type=int, metavar='SEC', help='kill the window after SEC seconds')
    parser.add_argument('-d', '--description', metavar='DESC', help='an additional description')
    args = parser.parse_args()
    # create window
    root = ProcessAppTk(args.namespec, args.description)
    # create auto-kill task
    if args.xkill is not None:
        root.after(args.xkill * 1000, root.quit)
    # start main loop
    root.mainloop()

