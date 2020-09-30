import tkinter as tk
import tkinter.ttk as ttk

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr import constants as CNST
from demomgr.tk_widgets import TtkText

class FirstRun(BaseDialog):
	"""
	Will open up when no config file is found on startup, prompts
	user to accept a text.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if user accepted, else FAILURE.
	`self.result.data` will be None.
	"""
	def __init__(self, parent):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		"""
		super().__init__(parent, "Welcome!")

	def body(self, master):
		'''UI'''
		master.columnconfigure((0, 1), weight = 1)
		master.columnconfigure(2, weight = 0)
		master.rowconfigure(0, weight = 1)

		scrlbar_v = ttk.Scrollbar(master, orient = tk.VERTICAL)
		scrlbar_h = ttk.Scrollbar(master, orient = tk.HORIZONTAL)
		txtbox = TtkText(master, ttk.Style(), wrap = tk.WORD,
			yscrollcommand = scrlbar_v.set, xscrollcommand = scrlbar_h.set)
		scrlbar_v.config(command = txtbox.yview)
		scrlbar_h.config(command = txtbox.xview)
		txtbox.insert(tk.END, CNST.WELCOME)
		txtbox.config(state = tk.DISABLED)
		txtbox.grid(column = 0, row = 0, columnspan = 2, sticky = "news")
		scrlbar_v.grid(column = 2, row = 0, sticky = "sn")
		scrlbar_h.grid(column = 0, columnspan = 2, row = 1, sticky = "ew")

		btconfirm = ttk.Button(master, text = "I am okay with that and I"
			" accept.", command = lambda: self.done(DIAGSIG.SUCCESS))
		btcancel = ttk.Button(master, text = "Cancel!",
			command = lambda: self.done(DIAGSIG.FAILURE))
		btconfirm.grid(column = 0, row = 2, padx = (0, 3), sticky = "ew")
		btcancel.grid(column = 1, row = 2, padx = (3, 0), sticky = "ew",
			columnspan = 2)

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		self.result.state = param
		self.destroy()
