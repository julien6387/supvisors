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

import os

from sys import stderr
from tkinter import *


class ProcessAppTk(Tk):

    cpt = 1

    def __init__(self, namespec, description):
        """ Initialization of the attributes. """
        Tk.__init__(self, None)
        print(f'Starting {namespec} in {os.getenv("SUPERVISOR_SERVER_URL")}')
        self.title('Supvisors')
        self.grid()
        # create main form
        form_window = PanedWindow(self, orient=VERTICAL)
        # display namespec into a PanedWindow
        main_window = PanedWindow(form_window, orient=VERTICAL)
        main_window.add(Label(main_window, text=f'Supvisors namespec: {namespec}'))
        if description:
            main_window.add(Label(main_window, text=f'Supvisors description: {description}'))
        # talk action
        main_window.add(Button(self, text='Talk', command=self.talk))
        # add window to form and pack it
        form_window.add(main_window)
        form_window.pack()
        # close action
        Button(self, text=u"Close", command=self.quit).pack(side=BOTTOM, padx=10, pady=2)
        # window properties
        self.grid_columnconfigure(0, weight=1)
        self.resizable(False, False)

    @staticmethod
    def talk():
        print('Talking seq=%d' % ProcessAppTk.cpt, flush=True)
        print('[ERR] Talking seq=%d' % ProcessAppTk.cpt, file=stderr, flush=True)
        ProcessAppTk.cpt = ProcessAppTk.cpt + 1

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
