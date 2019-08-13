import tkinter as tk
import tkinter.ttk as ttk

from ._base import BaseDialog

from .. import constants as CNST
from ..helper_tk_widgets import TtkText

class FirstRun(BaseDialog):
	'''Will open up when no config file is found on startup, prompts
	user to accept a text.'''
	def __init__(self, parent = None):
		if not parent:
			parent = tk._default_root
		super().__init__(parent, "Welcome!")

	def body(self, master):
		'''UI'''
		master.columnconfigure(0, weight = 1)
		master.columnconfigure(1, weight = 1)
		master.columnconfigure(2, weight = 0)
		master.rowconfigure(0, weight = 1)

		scrlbar = ttk.Scrollbar(master, orient = tk.VERTICAL)
		txtbox = TtkText(master, ttk.Style(), wrap = tk.WORD,
			yscrollcommand = scrlbar.set)
		scrlbar.config(command = txtbox.yview)
		txtbox.insert(tk.END, CNST.WELCOME)
		txtbox.config(state = tk.DISABLED)
		txtbox.grid(column = 0, row = 0, columnspan = 2, sticky = "news")
		scrlbar.grid(column = 2, row = 0, sticky = "sn")

		btconfirm = ttk.Button(master, text = "I am okay with that and I"
			" accept.", command = lambda: self.done(1))
		btcancel = ttk.Button(master, text = "Cancel!",
			command = lambda: self.done(0))
		btconfirm.grid(column = 0, row = 1, padx = (0, 3), sticky = "ew")
		btcancel.grid(column = 1, row = 1, padx = (3, 0), sticky = "ew")

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		self.result = param
		self.destroy()
