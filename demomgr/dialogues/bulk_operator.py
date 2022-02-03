from time import time
import tkinter as tk
import tkinter.ttk as ttk

from multiframe_list import MultiframeList, SELECTION_TYPE

from demomgr import constants as CNST, platforming
from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG
from demomgr.helpers import frmd_label
from demomgr.tk_widgets import TtkText
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, ThreadDelete

class BulkOperator(BaseDialog):
	"""
	Dialog that offers operations over multiple demos, while retaining
	their info.
	Able to start deletion, moving and copying threads.

	# TODO change below
	After the dialog is closed:
	`self.result.state` will be SUCCESS if a thread was started, else
		FAILURE.
	`self.result.data` will be a set containing each deleted file.
	"""

	MOVE = 0
	COPY = 1
	DELETE = 2

	def __init__(
		self, parent, demodir, files, cfg, styleobj, operation, arg = None
	):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		demodir: Absolute path to the directory containing the demos.
		files: List of file names of the demos to be operated on.
			This list will likely be modified by the dialog.
		cfg: Program config.
		styleobj: Instance of tkinter.ttk.Style.
		operation: What to do. One of the class variables `MOVE`,
			`COPY` or `DELETE`
		arg: Optional argument describing the target of a `MOVE` or
			`COPY` operation. Ignored when it's `DELETE`.
		"""
		super().__init__(parent, "Delete...")

		self.master = parent
		self.demodir = demodir
		self.files = files
		self.cfg = cfg
		self.styleobj = styleobj
		self._ini_operation = operation
		self.arg = arg

		self.thread_start_time = 0
		self.thread_files_processed = 0
		self._deleted_files = set()

		self.threadgroups = {
			self.DELETE: ThreadGroup(ThreadDelete, self.master),
		}
		self.threadgroups[self.DELETE].build_cb_method(self._after_callback_delete)
		self.active_threadgroup = None

	def body(self, master):
		self.protocol("WM_DELETE_WINDOW", self.destroy)

		master.grid_columnconfigure((0, 1), weight = 1)
		master.grid_rowconfigure((0, 1, 2, 3), weight = 1)

		button_frame = ttk.Frame(master)
		self.okbutton = ttk.Button(button_frame, text = "Start", command = lambda: self.confirm(1))
		self.cancelbutton = ttk.Button(button_frame, text = "Cancel", command = self.destroy)
		self.closebutton = ttk.Button(button_frame, text = "Close", command = self.destroy)
		self.canceloperationbutton = ttk.Button(button_frame, text = "Abort", command = self._stopoperation)

		self.listbox = MultiframeList(
			master,
			(
				{"col_id": "col_file", "name": "Filename"},
				{"col_id": "col_state", "name": "State"},
			),
			rightclickbtn = platforming.get_rightclick_btn(),
			resizable = True,
			selection_type = SELECTION_TYPE.SINGLE,
		)
		self.listbox.set_data({"col_file": self.files, "col_state": [""] * len(self.files)})
		self.listbox.format()

		textframe = ttk.Frame(master, padding = 5)

		self.textbox = TtkText(textframe, self.styleobj, wrap = tk.NONE, width = 20, height = 20)
		self.vbar = ttk.Scrollbar(textframe, orient = tk.VERTICAL, command = self.textbox.yview)
		self.vbar.grid(column = 1, row = 0, sticky = "ns")
		self.hbar = ttk.Scrollbar(textframe, orient = tk.HORIZONTAL, command = self.textbox.xview)
		self.hbar.grid(column = 0, row = 1, sticky = "ew")
		self.textbox.config(xscrollcommand = self.hbar.set, yscrollcommand = self.vbar.set)
		self.textbox.delete("0.0", tk.END)
		self.textbox.config(state = tk.DISABLED)

		self.operation_var = tk.IntVar()
		operation_frame = ttk.Frame(master)
		for i, (op, text) in enumerate((
			(self.DELETE, "Delete"),
			(self.COPY, "Copy"),
			(self.MOVE, "Move"),
		)):
			bt = ttk.Radiobutton(
				operation_frame,
				command = self._on_operation_change,
				variable = self.operation_var,
				value = op,
				text = text,
			)
			bt.grid(row = 0, column = i, sticky = "ne")

		self.operation_var.set(self._ini_operation)
		del self._ini_operation

		target_frame = ttk.Frame(master)
		self.target_entry = ttk.Entry(target_frame)
		self.target_sel_button = ttk.Button(
			target_frame, text = "Select target...", command = self._select_target
		)

		self.listbox.grid(row = 0, column = 0, sticky = "nesw")

		self.textbox.grid(column = 0, row = 0, sticky = "news", padx = (0, 3), pady = (0, 3))
		textframe.grid(row = 0, column = 1, sticky = "nesw")

		operation_frame.grid(row = 1, column = 0)

		self.target_entry.grid(row = 0, column = 0, sticky = "ne")
		self.target_sel_button.grid(row = 0, column = 1, sticky = "ne")
		target_frame.grid(row = 2, column = 0)

		self.okbutton.pack(side = tk.LEFT, anchor = tk.CENTER, fill = tk.X, expand = 1, padx = (0, 3))
		self.cancelbutton.pack(side = tk.LEFT, anchor = tk.CENTER, fill = tk.X, expand = 1, padx = (3, 0))
		button_frame.grid(row = 3, column = 0, columnspan = 2, sticky = "ew")

	def confirm(self, param):
		if param != 1:
			return
		self.okbutton.pack_forget()
		self.cancelbutton.pack_forget()
		self.canceloperationbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		self.thread_files_processed = 0
		self.thread_start_time = time()
		self._locked_operation = self.operation_var.get()

		self.active_threadgroup = self.threadgroups[self._locked_operation]
		self.active_threadgroup.start_thread(
			demodir = self.demodir,
			to_delete = self.files,
			cfg = self.cfg,
		)

	def _stopoperation(self):
		if self.active_threadgroup is not None:
			self.active_threadgroup.join_thread()

	def _on_operation_change(self):
		print("blah blah")

	def _select_target(self):
		print("later")

	def _after_callback_delete(self, sig, *args):
		"""
		Gets stuff from queue that the deleter thread writes to, then
		modifies UI based on queue elements.
		"""
		if sig.is_finish_signal():
			if sig is THREADSIG.SUCCESS:
				self.appendtextbox(
					f"\n\n==[Done]==\nTime taken: {round(time() - self.thread_start_time, 3)} "
					f"seconds\nSuccessfully processed {self.thread_files_processed}/"
					f"{len(self.files)} files.\n=========="
				)
			self.result.state = DIAGSIG.SUCCESS
			self.canceloperationbutton.pack_forget()
			self.closebutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
			return THREADGROUPSIG.FINISHED

		elif sig is THREADSIG.DELETION_SUCCESS:
			self.thread_files_processed += 1
			self._deleted_files.add(args[0])
			self.appendtextbox(f"Deleted {args[0]}\n")
		elif sig is THREADSIG.DELETION_FAILURE:
			self.appendtextbox(f"Failed to delete {args[0]}: {args[1]}\n")

		return THREADGROUPSIG.CONTINUE

	def appendtextbox(self, _inp):
		with self.textbox:
			self.textbox.insert(tk.END, str(_inp))
			self.textbox.yview_moveto(1.0)
			self.textbox.update()

	def destroy(self):
		self._stopoperation()
		self.result.data = self._deleted_files
		super().destroy()
