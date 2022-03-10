from itertools import chain, cycle, repeat
import random
from time import time
import tkinter as tk
from tkinter import filedialog as tk_fid
from tkinter import messagebox as tk_msg
import tkinter.ttk as ttk

from multiframe_list import MultiframeList, SELECTION_TYPE

from demomgr import constants as CNST, platforming
from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG
from demomgr.helpers import frmd_label
from demomgr.platforming import is_same_path
from demomgr.tk_widgets import TtkText
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, CMDDemosThread


_DGM_TXT = {CNST.DATA_GRAB_MODE.JSON: "JSON file", CNST.DATA_GRAB_MODE.EVENTS: "_events logchunk"}

class BulkOperator(BaseDialog):
	"""
	Dialog that offers operations over multiple demos, while retaining
	their info.
	Able to start and restart the Move/Copy/Delete thread.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if a thread was run at least once
		and the filesystem was likely modified in some way.
		Otherwise, it will be FAILURE.
	`self.result.data` will be a 2-element tuple.
	The first element contains all deleted files as a list.
	The second element is a dict mapp
	"""

	def __init__(
		self, parent, demodir, files, cfg, styleobj, operation, target = None
	):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		demodir: Absolute path to the directory containing the demos.
		files: List of file names of the demos to be operated on.
			This list will likely be modified by the dialog.
		cfg: Program config.
		styleobj: Instance of tkinter.ttk.Style.
		operation: What to do. One of the BULK_OPERATION enum members.
		target: Optional argument describing the target of a `MOVE` or
			`COPY` operation. Ignored when it's `DELETE`.
		"""
		super().__init__(parent, "Bulk Operator")

		self.master = parent
		self.demodir = demodir
		self.files = files
		self.cfg = cfg
		self.styleobj = styleobj
		self._ini_operation = operation
		self.target = target

		self.spinner = cycle(
			chain(*(
				repeat(sign, max(100 // CNST.GUI_UPDATE_WAIT, 1))
				for sign in ("|", "/", "-", "\\")
			))
		)

		self._locked_operation = None
		self._locked_operation_success_str = ""
		self._locked_operation_failure_str = ""
		self._listbox_idx_map = {}
		self.thread_last_start_time = 0
		self.thread_last_start_pending_files = 0
		self.thread_last_processed_files = 0
		self.pending_files = set() # Files that still need to be processed
		self.pending_demo_info = {} # Demo info that still needs to be processed
		self.thread_alive = False

		self._FULL_DGM = {m for m in CNST.DATA_GRAB_MODE if m is not CNST.DATA_GRAB_MODE.NONE}

		self.threadgroup = ThreadGroup(CMDDemosThread, self.master)
		self.threadgroup.build_cb_method(self._demo_after_callback)

	def _listbox_fmt_state(self, demo_name):
		# Usually gets called just after pending_files or pending_demo_info has been
		# modified as well as once after thread termination.
		# Updates the values all accordingly and stuff
		if self._locked_operation is None:
			return ""

		if self.thread_alive:
			return (
				self._locked_operation_failure_str if demo_name in self.pending_files else
				self._locked_operation_success_str
			)

		if demo_name in self.pending_files:
			return self._locked_operation_failure_str
		elif demo_name in self.pending_demo_info:
			return (
				self._locked_operation_success_str + "Failed transferring demo info for " +
				" ".join(_DGM_TXT[mode] for mode in self.pending_demo_info[demo_name])
			)
		else:
			return self._locked_operation_success_str

	def body(self, master):
		self.protocol("WM_DELETE_WINDOW", self.destroy)

		master.grid_columnconfigure(0, weight = 1)
		master.grid_rowconfigure(0, weight = 1)

		button_frame = ttk.Frame(master)
		self.okbutton = ttk.Button(button_frame, text = "Start", command = self._start_demo_processing)
		self.closebutton = ttk.Button(button_frame, text = "Close", command = self.destroy)
		self.canceloperationbutton = ttk.Button(button_frame, text = "Abort", command = self._stopoperation)

		self.listbox = MultiframeList(
			master,
			(
				{"col_id": "col_file", "name": "Filename"},
				{"col_id": "col_state", "name": "State", "formatter": self._listbox_fmt_state},
			),
			rightclickbtn = platforming.get_rightclick_btn(),
			resizable = True,
			selection_type = SELECTION_TYPE.SINGLE,
		)
		self.listbox.set_data({
			"col_file": self.files,
			"col_state": self.files,
		})
		self.listbox.format()
		self._refresh_demo_to_index_map()

		textframe = ttk.Frame(master, padding = 5)
		textframe.grid_columnconfigure(0, weight = 1)

		self.textbox = TtkText(textframe, self.styleobj, wrap = tk.NONE, width = 60, height = 3)
		self.textbox.insert(tk.END, "Status: Ready [.]\n")
		self.textbox.mark_set("status_start", "1.8")
		self.textbox.mark_set("status_end", "1.13")
		self.textbox.mark_set("spinner", "1.15")
		self.textbox.mark_gravity("status_start", tk.LEFT)
		self.textbox.mark_gravity("status_end", tk.RIGHT)
		self.textbox.mark_gravity("spinner", tk.LEFT)
		self.vbar = ttk.Scrollbar(textframe, orient = tk.VERTICAL, command = self.textbox.yview)
		self.vbar.grid(column = 1, row = 0, sticky = "ns")
		self.hbar = ttk.Scrollbar(textframe, orient = tk.HORIZONTAL, command = self.textbox.xview)
		self.hbar.grid(column = 0, row = 1, sticky = "ew")
		self.textbox.config(xscrollcommand = self.hbar.set, yscrollcommand = self.vbar.set)
		self.textbox.config(state = tk.DISABLED)

		self.operation_var = tk.IntVar()
		self.target_directory_var = tk.StringVar()
		self.operation_radiobuttons = []
		option_frame = ttk.LabelFrame(
			master,
			padding = 5,
			labelwidget = frmd_label(master, "Options"),
		)
		option_frame.grid_columnconfigure(0, weight = 1)
		radiobutton_frame = ttk.Frame(option_frame, style = "Contained.TFrame")
		for i, (text, op) in enumerate((
			("Delete", CNST.BULK_OPERATION.DELETE),
			("Copy", CNST.BULK_OPERATION.COPY),
			("Move", CNST.BULK_OPERATION.MOVE),
		)):
			bt = ttk.Radiobutton(
				radiobutton_frame,
				command = self._on_operation_change,
				variable = self.operation_var,
				value = op.value,
				text = text,
				style = "Contained.TRadiobutton"
			)
			bt.grid(row = 0, column = i, padx = (0, 10 * (i < 2)), ipadx = 1, sticky = "ew")
			self.operation_radiobuttons.append(bt)

		self.operation_var.set(self._ini_operation.value)
		del self._ini_operation

		self.target_path_frame = ttk.Frame(option_frame, style = "Contained.TFrame")
		self.target_path_frame.grid_columnconfigure(0, weight = 1)
		self.target_entry = ttk.Entry(
			self.target_path_frame, textvariable = self.target_directory_var, state = "readonly"
		)
		self.target_sel_button = ttk.Button(
			self.target_path_frame, text = "Select target...", command = self._select_target
		)
		self.warning_label = ttk.Label(
			self.target_path_frame,
			text = (
				"Note: Since I don't feel like writing more code that checks for "
				"duplicate files, any file naming conflicts in the destination directory "
				"will be ignored and existing files overwritten."
			),
			style = "Info.Contained.TLabel",
			wraplength = 400,
		)
		self.bind(
			"<Configure>",
			lambda _: self.warning_label.configure(
				wraplength = max(300, self.target_path_frame.winfo_width())
			)
		)

		self.listbox.grid(row = 0, column = 0, sticky = "nesw")

		self.textbox.grid(column = 0, row = 0, sticky = "ew", padx = (0, 3), pady = (0, 3))
		textframe.grid(row = 1, column = 0, sticky = "ew")

		radiobutton_frame.grid(row = 0, column = 0, pady = (0, 5))
		self.target_entry.grid(row = 1, column = 0, sticky = "ew")
		self.target_sel_button.grid(row = 1, column = 1, padx = (3, 0))
		self.target_path_frame.grid(row = 1, column = 0, sticky = "ew")
		self.warning_label.grid(row = 2, column = 0, columnspan = 2, sticky = "ew")
		option_frame.grid(row = 2, column = 0, sticky = "ew", pady = (0, 5))

		self.okbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		self.closebutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (3, 0))
		button_frame.grid(row = 3, column = 0, columnspan = 2, sticky = "ew")

		# Pokes all widgets that may need to be modified depending to the operation the dialog was
		# initialized with
		self._on_operation_change()

	def _lock_operation(self, op):
		for b in self.operation_radiobuttons:
			b.configure(state = tk.DISABLED)
		self.target_sel_button.configure(state = tk.DISABLED)
		self._locked_operation = op
		self._locked_operation_success_str, self._locked_operation_failure_str = {
			CNST.BULK_OPERATION.COPY: ("Copied.", "Failed copying."),
			CNST.BULK_OPERATION.MOVE: ("Moved.", "Failed moving."),
			CNST.BULK_OPERATION.DELETE: ("Deleted.", "Failed deleting."),
		}[op]

	def _refresh_demo_to_index_map(self):
		self._listbox_idx_map = {f: i for i, f in enumerate(self.listbox.get_column("col_file"))}

	def _stopoperation(self):
		self.threadgroup.join_thread()

	def _on_operation_change(self):
		if self._locked_operation is not None:
			return

		new_op = CNST.BULK_OPERATION(self.operation_var.get())
		if new_op is CNST.BULK_OPERATION.COPY or new_op is CNST.BULK_OPERATION.MOVE:
			self.target_sel_button.configure(state = tk.NORMAL)
			self.target_path_frame.grid()
		else:
			self.target_sel_button.configure(state = tk.DISABLED)
			self.target_path_frame.grid_remove()

	def _select_target(self):
		if self._locked_operation is not None:
			return

		res = tk_fid.askdirectory(parent = self)
		if not res:
			return
		self.target_directory_var.set(res)

	def _thread_run_always(self):
		with self.textbox:
			self.textbox.delete("spinner", "spinner + 1 chars")
			self.textbox.insert("spinner", next(self.spinner))

	def _start_demo_processing(self):
		selected_op = CNST.BULK_OPERATION(self.operation_var.get())

		target_dir = None
		if (
			selected_op is CNST.BULK_OPERATION.COPY or
			selected_op is CNST.BULK_OPERATION.MOVE
		):
			target_dir = self.target_directory_var.get()
			if target_dir == "":
				tk_msg.showinfo("Demomgr", "You must select a target directory.")
				return

			try:
				if is_same_path(self.demodir, target_dir):
					tk_msg.showerror("Demomgr", "The directories must be distinct!")
					return
			except (FileNotFoundError, OSError) as e:
				tk_msg.showerror(
					"Demomgr",
					f"Error while checking directories for distinctness: {e}",
				)
				return

		# We're in business once this point is reached

		self._lock_operation(selected_op)
		self.textbox.replace("status_start", "status_end", "Running")
		self.okbutton.pack_forget()
		self.okbutton.configure(text = "Retry")
		self.closebutton.pack_forget()
		self.canceloperationbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		self.pending_files = set(self.files)

		self.thread_last_start_time = time()
		self.thread_last_start_pending_files = len(self.pending_files) + len(self.pending_demo_info)
		self.thread_last_processed_files = 0
		self.thread_alive = True
		self.threadgroup.start_thread(
			source_dir = self.demodir,
			target_dir = target_dir,
			mode = selected_op,
			files_to_process = self.pending_files.copy(),
			# Copy, the thread modifies this object
			info_to_process = {d: m.copy() for d, m in self.pending_demo_info.items()},
			cfg = self.cfg,
		)

	def _demo_after_callback(self, sig, *args):
		if sig.is_finish_signal():
			self.thread_alive = False
			if sig is THREADSIG.SUCCESS:
				self.textbox_set_line(
					2,
					(
						f"Successfully processed {self.thread_last_processed_files}/"
						f"{self.thread_last_start_pending_files} files in "
						f"{round(time() - self.thread_last_start_time, 3)} seconds."
					)
				)
			self.result.state = DIAGSIG.SUCCESS
			self.canceloperationbutton.pack_forget()
			if self.pending_files or self.pending_demo_info:
				self.okbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
			self.closebutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
			with self.textbox:
				self.textbox.replace("status_start", "status_end", "Finished")
				self.textbox.delete("spinner", "spinner + 1 chars")
				self.textbox.insert("spinner", ".")

			print("Thread finished!")
			pprint = __import__("pprint").pprint
			print("Pending files:")
			pprint(self.pending_files)
			print("\nPending info:")
			pprint(self.pending_demo_info)
			print("\n")
			self.listbox.format(("col_state",))

			return THREADGROUPSIG.FINISHED

		elif sig is THREADSIG.FILE_OPERATION_SUCCESS or sig is THREADSIG.FILE_OPERATION_FAILURE:
			name = args[0]
			if sig is THREADSIG.FILE_OPERATION_SUCCESS:
				self.pending_files.remove(name)
				self.pending_demo_info[name] = self._FULL_DGM.copy()
			self.listbox.format(("col_file",), (self._listbox_idx_map[name],))

		elif sig is THREADSIG.RESULT_INFO_WRITE_RESULTS:
			mode = args[0]
			for demo_name, write_result in args[1].items():
				if demo_name in self.pending_files:
					print(f"Something went wrong: {demo_name} was still pending.")
					continue
				if write_result is None:
					if len(self.pending_demo_info[demo_name]) == 1:
						self.pending_demo_info.pop(demo_name)
						self.thread_last_processed_files += 1
					else:
						self.pending_demo_info[demo_name].remove(mode)
			self.listbox.format(("col_state",))

		return THREADGROUPSIG.CONTINUE

	def textbox_set_line(self, line, _inp):
		with self.textbox:
			self.textbox.replace(f"{line}.0", f"{line}.end", _inp)
			self.textbox.yview_moveto(1.0)
			self.textbox.update()

	def destroy(self):
		self._stopoperation()
		# Thread is done at this point, which means self.pending_* contains all
		# non-completed work units.

		super().destroy()
