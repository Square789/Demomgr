import tkinter as tk
import tkinter.ttk as ttk

import os
import threading
import queue

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr import constants as CNST
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

	def __init__(
		self, parent, demodir, files, selected, evtblocksz, deluselessjson,
		styleobj, eventfileupdate = "passive"
	):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		demodir: Absolute path to the directory containing the demos. (str)
		files: List of files that shall be included in the deletion
			evaluation.
		selected: List of boolean values so that
			files[n] will be deleted if selected[n] == True
		evtblocksz: Size of blocks (in bytes) to read _events.txt in.
		deluselessjson: Boolean value that instructs the deletion evaluation
			to include json files with no demos.
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
		self.evtblocksz = evtblocksz
		self.deluselessjson = deluselessjson
		self.styleobj = styleobj
		self.eventfileupdate = eventfileupdate

		self.filestodel = [j for i, j in enumerate(self.files) if self.selected[i]]

		self.threadgroup = ThreadGroup(ThreadDelete, self.master)
		self.threadgroup.decorate_and_patch(self, self._after_callback)

	def body(self, master):
		self.protocol("WM_DELETE_WINDOW", self.destroy)

		try: # Try block should only catch from the os.listdir call directly below.
			jsonfiles = [i for i in os.listdir(self.demodir) if os.path.splitext(i)[1] == ".json"]
			# Add json files to self.todel if their demo files are in todel
			choppedfilestodel = [os.path.splitext(i)[0] for i in self.filestodel]
			choppedfiles = None

			for i, j in enumerate(jsonfiles):
				if os.path.splitext(j)[0] in choppedfilestodel:
					self.filestodel.append(jsonfiles[i])
			if self.deluselessjson: # also delete orphaned files
				choppedfilestodel = None
				choppedfiles = {os.path.splitext(i)[0] for i in self.files}
				for i, j in enumerate(jsonfiles):
					if not os.path.splitext(j)[0] in choppedfiles:
						self.filestodel.append(jsonfiles[i])
			self.startmsg = "This operation will delete the following file(s):\n\n" + \
				"\n".join(self.filestodel)
		except (OSError, PermissionError, FileNotFoundError) as error:
			self.startmsg = f"Error getting JSON files: !\n{type(error).__name__}: {error}\n\n" \
				f"This operation will delete the following file(s):\n\n" + "\n".join(self.filestodel)

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
		self.threadgroup.join_thread()

	def _startthread(self):
		self.threadgroup.start_thread(
			demodir =         self.demodir,
			files =           self.files,
			selected =        self.selected,
			filestodel =      self.filestodel,
			evtblocksz =      self.evtblocksz,
			eventfileupdate = self.eventfileupdate,
		)

	def _after_callback(self, queue_elem):
		"""
		Gets stuff from self.queue_out that the thread writes to, then
		modifies UI based on queue elements.
		(Additional decoration in __init__)
		"""
		if queue_elem[0] == THREADSIG.INFO_CONSOLE:
			self.appendtextbox(queue_elem[1])
			return THREADGROUPSIG.CONTINUE
		elif queue_elem[0] < 0x100: # Finish
			self.result.state = DIAGSIG.SUCCESS
			self.result.data = queue_elem[0]
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
