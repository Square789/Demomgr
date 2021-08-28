import tkinter as tk
import tkinter.ttk as ttk

import os

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr.tk_widgets import TtkText
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, ThreadDelete

class Deleter(BaseDialog):
	"""
	A dialog that constructs deletion requests for demos and prompts the
	user whether they are sure of the deletion. If yes was selected, starts
	a stoppable thread and waits for its completion.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if the thread was started, else
		FAILURE.
	`self.result.data` will be None if the thread was not started, else the
		thread's termination signal.
	"""

	REMEMBER_DEFAULT = [True, True, True]

	def __init__(
		self, parent, demodir, to_delete, cfg, styleobj
	):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		demodir: Absolute path to the directory containing the demos.
		to_delete: List of file names of the Demos to be deleted.
			This list will likely be modified by the dialog.
		cfg: Program config.
		styleobj: Instance of tkinter.ttk.Style.
		"""
		super().__init__(parent, "Delete...")

		self.master = parent
		self.demodir = demodir
		self.to_delete = to_delete
		self.cfg = cfg
		self.styleobj = styleobj

		self.files = []

		self.threadgroup = ThreadGroup(ThreadDelete, self.master)
		self.threadgroup.decorate_and_patch(self, self._after_callback)

	def body(self, master):
		self.protocol("WM_DELETE_WINDOW", self.destroy)

		startmsg = ""
		try:
			self.files = os.listdir(self.demodir)
		except (OSError, PermissionError, FileNotFoundError) as e:
			self.to_delete = []
			startmsg += f"Failed to get files: {e.__class__.__name__}: {e}!"

		# delete json files if: no corresponding demo file exists or a corresponding demo
		# file exists but is scheduled for deletion
		_to_delete = set(self.to_delete)
		untouched_demos = set(
			file for file in self.files
			if os.path.splitext(file)[1] == ".dem" and file not in _to_delete
		)
		for file in self.files:
			name, ext = os.path.splitext(file)
			if ext != ".json":
				continue
			if name + ".dem" not in untouched_demos:
				self.to_delete.append(file)

		startmsg += \
			"This operation will delete the following file(s):\n\n" + "\n".join(self.to_delete)

		self.okbutton = ttk.Button(master, text = "Delete!", command = lambda: self.confirm(1))
		self.cancelbutton = ttk.Button(master, text = "Cancel", command = self.destroy )
		self.closebutton = ttk.Button(master, text = "Close", command = self.destroy )
		self.canceloperationbutton = ttk.Button(master, text = "Abort", command = self._stopoperation)
		textframe = ttk.Frame(master, padding = (5, 5, 5, 5))
		textframe.grid_columnconfigure(0, weight = 1)
		textframe.grid_rowconfigure(0, weight = 1)

		self.textbox = TtkText(textframe, self.styleobj, wrap = tk.NONE, width = 40, height = 20)
		self.vbar = ttk.Scrollbar(textframe, orient = tk.VERTICAL, command = self.textbox.yview)
		self.vbar.grid(column = 1, row = 0, sticky = "ns")
		self.hbar = ttk.Scrollbar(textframe, orient = tk.HORIZONTAL, command = self.textbox.xview)
		self.hbar.grid(column = 0, row = 1, sticky = "ew")
		self.textbox.config(xscrollcommand = self.hbar.set, yscrollcommand = self.vbar.set)
		self.textbox.grid(column = 0, row = 0, sticky = "news", padx = (0, 3), pady = (0, 3))

		self.textbox.delete("0.0", tk.END)
		self.textbox.insert(tk.END, startmsg)
		self.textbox.config(state = tk.DISABLED)

		textframe.pack(fill = tk.BOTH, expand = 1)

		self.okbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		self.cancelbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (3, 0))

	def confirm(self, param):
		if param == 1:
			self.okbutton.pack_forget()
			self.cancelbutton.pack_forget()
			self.canceloperationbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
			self._startthread()

	def _stopoperation(self):
		self.threadgroup.join_thread()

	def _startthread(self):
		self.threadgroup.start_thread(
			demodir =   self.demodir,
			files =     self.files,
			to_delete = self.to_delete,
			cfg =       self.cfg,
		)

	def _after_callback(self, sig, *args):
		"""
		Gets stuff from self.queue_out that the thread writes to, then
		modifies UI based on queue elements.
		(Additional decoration in __init__)
		"""
		if sig is THREADSIG.INFO_CONSOLE:
			self.appendtextbox(args[0])
			return THREADGROUPSIG.CONTINUE
		elif sig.is_finish_signal(): # Finish
			self.result.state = DIAGSIG.SUCCESS
			self.result.data = sig
			self.canceloperationbutton.pack_forget()
			self.closebutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
			return THREADGROUPSIG.FINISHED

	def appendtextbox(self, _inp):
		with self.textbox:
			self.textbox.insert(tk.END, str(_inp))
			self.textbox.yview_moveto(1.0)
			self.textbox.update()

	def destroy(self):
		self._stopoperation()
		super().destroy()
