import tkinter as tk
import tkinter.ttk as ttk

import os
import threading
import queue

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr import constants as CNST
from demomgr.helper_tk_widgets import TtkText
from demomgr.threads import ThreadDelete

THREADSIG = CNST.THREADSIG

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
	def __init__(self, parent, demodir, files, selected,
			deluselessjson, cfg, styleobj, eventfileupdate = "passive"):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		demodir: Absolute path to the directory containing the demos. (str)
		files: List of files that shall be included in the deletion
			evaluation.
		selected: List of boolean values so that
			files[n] will be deleted if selected[n] == True
		deluselessjson: Boolean value that instructs the deletion evaluation
			to include json files with no demos.
		cfg: Program configuration.
		styleobj: Instance of tkinter.ttk.Style.
		eventfileupdate: Has two valid forms: "selectivemove" and "passive"
			(default).
			"selectivemove" only writes Logchunks from the old eventfile to
				the new one if it can be assigned to a file in a previously
				declared list of acceptable files.
				!!!This mode requires every demo of demodir to be present in
				files!!!
			"passive" moves all Logchunks from the old eventfile to the
				new one unless their demo was explicitly deleted.
		"""
		super().__init__(parent, "Delete...")

		self.master = parent
		self.demodir = demodir
		self.files = files
		self.selected = selected
		self.deluselessjson = deluselessjson
		self.cfg = cfg
		self.styleobj = styleobj
		self.eventfileupdate = eventfileupdate

		self.filestodel = [j for i, j in enumerate(self.files) if self.selected[i]]

		self.startmsg = "This operation will delete the following file(s):\n\n" + "\n".join(self.filestodel)

		try: #Try block should only catch from the os.listdir call directly below.
			jsonfiles = [i for i in os.listdir(self.demodir) if os.path.splitext(i)[1] == ".json"]
			choppedfilestodel = [os.path.splitext(i)[0] for i in self.filestodel] #add json files to self.todel if their demo files are in todel
			choppedfiles = None

			for i, j in enumerate(jsonfiles):
				if os.path.splitext(j)[0] in choppedfilestodel:
					self.filestodel.append(jsonfiles[i])
			if self.deluselessjson: #also delete orphaned files
				choppedfilestodel = None
				choppedfiles = [os.path.splitext(i)[0] for i in self.files]
				for i, j in enumerate(jsonfiles):
					if not os.path.splitext(j)[0] in choppedfiles:
						self.filestodel.append(jsonfiles[i])
			del jsonfiles, choppedfilestodel, choppedfiles
			self.startmsg = "This operation will delete the following file(s):\n\n" + "\n".join(self.filestodel)
		except (OSError, PermissionError, FileNotFoundError) as error:
			self.startmsg = "! Error getting JSON files: !\n{}{}\n\n{}".format(error.__class__.__name__, str(error), self.startmsg)

		self.delthread = threading.Thread() #Dummy thread in case self.destroy is called through window manager
		self.after_handler = self.after(0, lambda: None)
		self.queue_out = queue.Queue()

	def body(self, master):
		'''UI'''
		self.okbutton = ttk.Button(master, text = "Delete!", command = lambda: self.confirm(1) )
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
		self.textbox.insert(tk.END, self.startmsg)
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
		self.after_cancel(self.after_handler)
		if self.delthread.isAlive():
			self.delthread.join()
		self._after_callback()

	def _startthread(self):
		self.delthread = ThreadDelete(None, self.queue_out,
			demodir =			self.demodir,
			files =				self.files,
			selected =			self.selected,
			filestodel =		self.filestodel,
			cfg =				self.cfg,
			eventfileupdate =	self.eventfileupdate)
		self.delthread.start()
		self.after_handler = self.after(0, self._after_callback)

	def _after_callback(self, call_once = False):
		"""
		Gets stuff from self.queue_out that the thread writes to, then
		modifies UI based on queue elements.
		"""
		finished = False
		while True:
			try:
				procelem = self.queue_out.get_nowait()
				if procelem[0] == THREADSIG.INFO_CONSOLE:
					self.appendtextbox(procelem[1])
				elif procelem[0] < 0x100: # Finish
					finished = True
					self.result.state = DIAGSIG.SUCCESS
					self.result.data = procelem[0]
					self.canceloperationbutton.pack_forget()
					self.closebutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
			except queue.Empty:
				break
		if (not finished) and (not call_once):
			self.after_handler = self.after(CNST.GUI_UPDATE_WAIT, self._after_callback)

	def appendtextbox(self, _inp):
		self.textbox.config(state = tk.NORMAL)
		self.textbox.insert(tk.END, str(_inp) )
		self.textbox.yview_moveto(1.0)
		self.textbox.update()
		self.textbox.config(state = tk.DISABLED)

	def destroy(self):
		self._stopoperation()
		super().destroy()
