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

class ActivityTk(Tk):

    def __init__(self, namespec):
        """ Initialization of the attributes. """
        Tk.__init__(self, None)
        self.namespec = namespec
        self.initialize()

    def initialize(self):
        self.title(u'Supervisors')
        self.grid()
        # create main form
        formWindow = PanedWindow(self, orient=VERTICAL)
        # display namespec into a PanedWindow
        mainWindow = PanedWindow(formWindow, orient=HORIZONTAL)
        mainWindow.add(Label(mainWindow, text=u'Supervisors namespec: {}'.format(self.namespec)))
        # add window to form and pack it
        formWindow.add(mainWindow)
        formWindow.pack()
        # Actions
        Button(self, text=u"close", command=self.quit).pack(side=BOTTOM, padx=10, pady=2)
        # window properties
        self.grid_columnconfigure(0, weight=1)
        #self.resizable(False, False)


if __name__ == "__main__":
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Start a dummy window named with a namespec.')
    parser.add_argument('-n', '--namespec', required=True, help="the namespec of the program")
    args = parser.parse_args()
    # create window
    fenetre = ActivityTk(args.namespec)
    fenetre.mainloop()



