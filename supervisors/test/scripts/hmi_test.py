#!/usr/bin/python
#-*- coding: utf-8 -*-

from Tkinter import *

class ActivityTk(Tk):
	def __init__(self, parent):
		Tk.__init__(self, parent)
		self.parent = parent
		self.initialize()

	def initialize(self):
		self.title(u"Create activity")
		self.grid()

		formWindow = PanedWindow(self, orient=VERTICAL)

		# Domain
		domainWindow = PanedWindow(formWindow, orient=HORIZONTAL)
		formWindow.add(domainWindow)

		domainList = StringVar(value=u'IHM PROC SYSM DEPL GCONF SUPV')
		self.domainListBox = Listbox(domainWindow, listvariable=domainList, height=len(domainList.get().split(" ")), exportselection=False)
		self.domainListBox.selection_set(0)

		domainWindow.add(Label(domainWindow, text=u"DOMAINE: "))
		domainWindow.add(self.domainListBox)

		# pack form
		formWindow.pack()

		# Actions
		Button(self, text=u"close", command=self.quit).pack(side=LEFT, padx=10, pady=2)

		# window properties
		self.grid_columnconfigure(0, weight=1)
		self.resizable(False, False)

if __name__ == "__main__":
	fenetre = ActivityTk(None)
	fenetre.mainloop()



