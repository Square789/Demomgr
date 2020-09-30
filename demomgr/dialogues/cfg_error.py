import tkinter as tk
import tkinter.ttk as ttk

import os
import json

from demomgr.dialogues._base import BaseDialog
from demomgr import constants as CNST 

class CfgError(BaseDialog):
	"""
	Dialog that opens on malformed config and offers three options:
	Retry, Replace, Quit.

	After the dialog is closed:
	`self.result.data` will contain 0: Retry; 1: Replace; 2: Quit
	"""
	def __init__(self, parent, cfgpath, error, mode):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		cfgpath: Path to program configuration. (str)
		error: The error that caused this dialog. (str)
		mode: 0 for read access error, 1 for write error
		"""
		super().__init__(parent, "Configuration error!")

		self.cfgpath = cfgpath
		self.error = error
		self.mode = mode #0: Read; 1: Write

	def body(self, parent):
		"""UI"""

		self.protocol("WM_DELETE_WINDOW", self._quit)

		ifread = abs(self.mode - 1)
		msg = ("The configuration file could not be " +
			("read from" * ifread + "written to" * self.mode) +
			", meaning it was " + ("either corrupted, deleted, " * ifread) +
			"made inaccessible" + (" or has bad values" * ifread) +
			".\nDemomgr can not continue but you can select from the options "
			"below.\n\nRetry: Try performing the action again\nReplace: Write "
			"the default config to the config path, then retry.\nQuit: Quit Demomgr" +
			"\n\n{}: {}".format(self.error.__class__.__name__, str(self.error)) )
		slickframe = ttk.Frame(parent, relief = tk.SUNKEN, border = 5,
			style = "Contained.TFrame")
		msg_label = ttk.Label(slickframe, font = ("TkDefaultFont", 10),
			wrap = 400, text = msg, style = "Contained.TLabel")
		self.inf_updating = ttk.Label(slickframe,
			font = ("TkDefaultFont", 10), wrap = 400, style = "Contained.TLabel",
			text = "Attempting to rewrite default config...")
		self.err_rewrite_fail = ttk.Label(slickframe,
			font = ("TkDefaultFont", 10), wrap = 400, style = "Contained.TLabel")
		retrybtn = ttk.Button(parent, text = "Retry", command = self._retry)
		replbtn = ttk.Button(parent, text = "Replace", command = self._replacecfg)
		quitbtn = ttk.Button(parent, text = "Quit", command = self._quit)

		slickframe.pack(expand = 1, fill = tk.BOTH)
		msg_label.pack(side = tk.TOP, expand = 1, fill = tk.BOTH)
		retrybtn.pack(fill = tk.X, side = tk.LEFT, expand = 1, padx = (0, 3))
		replbtn.pack(fill = tk.X, side = tk.LEFT, expand = 1, padx = 3)
		quitbtn.pack(fill = tk.X, side = tk.LEFT, expand = 1, padx = (3, 0))

	def destroy(self):
		super().destroy()

	def _retry(self):
		self.result.data = 0
		self.destroy()

	def _replacecfg(self):
		cfgtowrite = CNST.DEFAULT_CFG
		try:
			self.err_rewrite_fail.pack_forget()
			self.inf_updating.pack(side = tk.TOP, expand = 1, fill = tk.BOTH)
			os.makedirs(CNST.CFG_FOLDER, exist_ok = True)
			handle = open(self.cfgpath, "w")
			handle.write(json.dumps(cfgtowrite, indent = 4))
			handle.close()
			self.cfg = CNST.DEFAULT_CFG
		except Exception as exception:
			self.inf_updating.pack_forget()
			self.err_rewrite_fail.config(text = "Rewrite failed: {}".format(
				str(exception)
			))
			self.err_rewrite_fail.pack(side = tk.TOP, expand = 1,
				fill = tk.BOTH)
			return
		self.result.data = 1
		self.destroy()

	def _quit(self):
		self.result.data = 2
		self.destroy()
