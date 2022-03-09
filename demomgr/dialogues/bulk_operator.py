from itertools import chain, cycle, repeat
from time import time
import tkinter as tk
from tkinter import filedialog as tk_fid
import tkinter.ttk as ttk

from multiframe_list import MultiframeList, SELECTION_TYPE

from demomgr import constants as CNST, platforming
from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG
from demomgr.helpers import frmd_label
from demomgr.tk_widgets import TtkText
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, CMDDemosThread, CMDDemoInfoThread


_TMP = {CNST.DATA_GRAB_MODE.JSON: "JSON file", CNST.DATA_GRAB_MODE.EVENTS: "_events.txt entry"}

class FileState:
	# __slots__ = ("processed", "processed_data_grab_modes", "success")

	def __init__(self):
		self.processed = False
		self.success = False
		self.processed_data_grab_modes = {}

	def set(self, success, action):
		self.processed = True
		self.success = success

	def __str__(self):
		if not self.processed:
			return ""

		if not self.success:
			return "Failure."

		r = ["Processed."]
		for mode in CNST.DATA_GRAB_MODE:
			if mode is CNST.DATA_GRAB_MODE.NONE or mode not in self.processed_data_grab_modes:
				continue
			if self.processed_data_grab_modes[mode] is not None:
				r.append(
					f"Error removing {_TMP[mode]}."
				)
		return " ".join(r)


class BulkOperator(BaseDialog):
	"""
	Dialog that offers operations over multiple demos, while retaining
	their info.
	Able to start deletion, moving and copying threads.

	# TODO change below
	After the dialog is closed:
	`self.result.state` will be SUCCESS if a thread was run
		and the filesystem was likely modified in some way.
		Otherwise, it will be FAILURE.
	`self.result.data` will be # TODO.
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

		self._listbox_idx_map = {}
		self.thread_start_time = 0
		self._processed_files = {}
		self.pending_files = set() # Files that still need to be processed
		self.pending_demo_info = {} # Demo info that still needs to be processed

		self.demo_threadgroup = ThreadGroup(CMDDemosThread, self.master)
		self.demo_threadgroup.build_cb_method(self._demo_after_callback)

		self.demoinfo_threadgroup = ThreadGroup(CMDDemoInfoThread, self.master)
		self.demoinfo_threadgroup.build_cb_method(self._demoinfo_after_callback)

	def body(self, master):
		self.protocol("WM_DELETE_WINDOW", self.destroy)

		master.grid_columnconfigure(0, weight = 1)
		master.grid_rowconfigure((0, 1, 2, 3), weight = 1)

		button_frame = ttk.Frame(master)
		self.okbutton = ttk.Button(button_frame, text = "Start", command = lambda: self._start_demo_processing)
		self.closebutton = ttk.Button(button_frame, text = "Cancel", command = self.destroy)
		self.canceloperationbutton = ttk.Button(button_frame, text = "Abort", command = self._stopoperation)

		self.listbox = MultiframeList(
			master,
			(
				{"col_id": "col_file", "name": "Filename"},
				{"col_id": "col_state", "name": "State", "formatter": str},
			),
			rightclickbtn = platforming.get_rightclick_btn(),
			resizable = True,
			selection_type = SELECTION_TYPE.SINGLE,
		)
		self.listbox.set_data({
			"col_file": self.files,
			"col_state": [FileState() for _ in self.files],
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

		self.textbox.grid(column = 0, row = 0, sticky = "news", padx = (0, 3), pady = (0, 3))
		textframe.grid(row = 1, column = 0, sticky = "nesw")

		radiobutton_frame.grid(row = 0, column = 0, pady = (0, 5))
		self.target_entry.grid(row = 1, column = 0, sticky = "ew")
		self.target_sel_button.grid(row = 1, column = 1, padx = (3, 0))
		self.target_path_frame.grid(row = 1, column = 0, sticky = "ew")
		self.warning_label.grid(row = 2, column = 0, columnspan = 2, sticky = "ew")
		option_frame.grid(row = 2, column = 0, sticky = "ew", pady = (0, 5))

		self.okbutton.pack(side = tk.LEFT, anchor = tk.CENTER, fill = tk.X, expand = 1, padx = (0, 3))
		self.closebutton.pack(side = tk.LEFT, anchor = tk.CENTER, fill = tk.X, expand = 1, padx = (3, 0))
		button_frame.grid(row = 3, column = 0, columnspan = 2, sticky = "ew")

		# Pokes all widgets that may need to be modified depending to the operation the dialog was
		# initialized with
		self._on_operation_change()

	def _start_demo_processing(self):
		self.thread_start_time = time()

		self.textbox.replace("status_start", "status_end", "Running")
		self.okbutton.pack_forget()
		self.closebutton.pack_forget()
		self.canceloperationbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		self._locked_operation = CNST.BULK_OPERATION(self.operation_var.get())

		self.pending_files = set(self.files)

		target_dir = None
		if (
			self._locked_operation is CNST.BULK_OPERATION.COPY or
			self._locked_operation is CNST.BULK_OPERATION.MOVE
		):
			target_dir = self.target_directory_var.get()

		self.demo_threadgroup.start_thread(
			source_dir = self.demodir,
			target_dir = target_dir,
			mode = self._locked_operation,
			to_process = self.files,
			cfg = self.cfg,
		)

	def _start_demo_info_processing(self):
		pass

	def _refresh_demo_to_index_map(self):
		self._listbox_idx_map = {f: i for i, f in enumerate(self.listbox.get_column("col_file"))}

	def _stopoperation(self):
		if self.active_threadgroup is not None:
			self.active_threadgroup.join_thread()

	def _on_operation_change(self):
		new_op = CNST.BULK_OPERATION(self.operation_var.get())
		if new_op is CNST.BULK_OPERATION.COPY or new_op is CNST.BULK_OPERATION.MOVE:
			self.target_sel_button.configure(state = tk.NORMAL)
			self.target_path_frame.grid()
		else:
			self.target_sel_button.configure(state = tk.DISABLED)
			self.target_path_frame.grid_remove()

	def _select_target(self):
		res = tk_fid.askdirectory(parent = self)
		if not res:
			return
		self.target_directory_var.set(res)

	def _thread_run_always(self):
		with self.textbox:
			self.textbox.delete("spinner", "spinner + 1 chars")
			self.textbox.insert("spinner", next(self.spinner))

	def _demo_after_callback(self, sig, *args):
		if sig.is_finish_signal():
			self._start_demo_info_processing()
			return THREADGROUPSIG.FINISHED

		elif sig is THREADSIG.FILE_OPERATION_SUCCESS or sig is THREADSIG.FILE_OPERATION_FAILURE:
			name = args[0]
			file_state = self.listbox.get_cell("col_state", self._listbox_idx_map[name])
			file_state.set(sig is THREADSIG.FILE_OPERATION_SUCCESS, self._locked_operation)
			if sig is THREADSIG.FILE_OPERATION_SUCCESS:
				self.pending_files.remove(name)
			self.listbox.format(("col_file",), (self._listbox_idx_map[name],))

		elif sig is THREADSIG.RESULT_INFO_WRITE_RESULTS:
			# Format the FileStates with appropiate information.
			for mode, inner in args[0].items():
				for demo_name, write_result in inner.items():
					self.listbox.get_cell(
						"col_state", self._listbox_idx_map[demo_name]
					).processed_data_grab_modes[mode] = write_result
					if demo_name in self.pending_files:
						print(f"Something went wrong: {demo_name} was still pending.")
						continue
					self.pending_files.remove(demo_name)
			self.listbox.format(("col_state",))

		return THREADGROUPSIG.CONTINUE

	def _demoinfo_after_callback(self, sig, *args):
		if sig.is_finish_signal():
			if sig is THREADSIG.SUCCESS:
				self.appendtextbox(
					f"Successfully processed {len(self._processed_files)}/"
					f"{len(self.files)} files in {round(time() - self.thread_start_time, 3)} "
					f"seconds."
				)
			self.result.state = DIAGSIG.SUCCESS
			self.canceloperationbutton.pack_forget()
			self.closebutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
			with self.textbox:
				self.textbox.replace("status_start", "status_end", "Finished")
				self.textbox.delete("spinner", "spinner + 1 chars")
				self.textbox.insert("spinner", ".")

	def appendtextbox(self, _inp):
		with self.textbox:
			self.textbox.insert(tk.END, str(_inp))
			self.textbox.yview_moveto(1.0)
			self.textbox.update()

	def destroy(self):
		self._stopoperation()
		self.result.data = self._processed_files
		super().destroy()
