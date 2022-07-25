import os
import tkinter as tk
import tkinter.ttk as ttk
import typing as t

import demomgr.constants as CNST
from demomgr.demo_data_manager import DemoDataManager
from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG
from demomgr.tk_widgets import DmgrEntry

if t.TYPE_CHECKING:
	from demomgr.config import Config


class Rename(BaseDialog):
	"""
	Rename dialog that tries to stay out of the way.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if the rename process went
		through successfully, else FAILURE.

	`self.result.data` will be the new name as string if the dialog
		succeeded, else None.
	"""

	def __init__(self, parent: tk.Wm, cfg: "Config", dir: str, file: str) -> None:
		super().__init__(parent, "Rename")
		self.cfg = cfg
		self.dir = dir
		self.target_file = file

		self.pending_rename = True
		self.pending_modes = {x for x in CNST.DATA_GRAB_MODE if x is not CNST.DATA_GRAB_MODE.NONE}

	def body(self, master: tk.Widget) -> None:
		self.protocol("WM_DELETE_WINDOW", self._exit)
		self.bind("<Escape>", lambda _: self._exit())
		self.bind("<Return>", lambda _: self._rename())

		self.new_name_entry = DmgrEntry(master, CNST.FILENAME_MAX, width = 48)

		self.button_frame = ttk.Frame(master, padding = 5)
		self.ok_but = ttk.Button(self.button_frame, text = "Rename", command = self._rename)
		self.notok_but = ttk.Button(self.button_frame, text = "Cancel", command = self._exit)

		master.grid_columnconfigure(0, weight = 1)
		self.new_name_entry.grid(row = 0, column = 0, sticky = "ew")
		self.button_frame.grid_columnconfigure((0, 1), weight = 1)
		self.ok_but.grid(row = 0, column = 0, sticky = "ew", padx = (0, 5))
		self.notok_but.grid(row = 0, column = 1, sticky = "ew")
		self.button_frame.grid(row = 1, column = 0, sticky = "ew")

		sel_len = tk.END
		root, ext = os.path.splitext(self.target_file)
		if ext == ".dem":
			# It most definitely will be since Demomgr only lists files with that as their ending
			sel_len = len(root)
		self.new_name_entry.insert(0, self.target_file)
		self.new_name_entry.select_range(0, sel_len)
		self.new_name_entry.icursor(sel_len)
		self.new_name_entry.focus()

	def _rename(self) -> None:
		# Do it in the UI thread, the hassle with a threadgroup
		# is really not worth it as cancellation would block just like
		# the I/O does anyways.
		# Also why on earth would you want to cancel this when you
		# explicitly started it
		new_name = self.new_name_entry.get()
		if not new_name.endswith(".dem") or new_name == "":
			return

		if new_name == self.target_file:
			self.destroy()
			return

		if self.pending_rename:
			try:
				os.rename(
					os.path.join(self.dir, self.target_file),
					os.path.join(self.dir, new_name),
				)
				self.pending_rename = False
			except OSError as e:
				# fail
				pass

		ddm = DemoDataManager(self.dir, self.cfg)
		for mode in self.pending_modes:
			di = ddm.get_demo_info([self.target_file], mode)[0]
			if isinstance(di, Exception):
				print("0Failure.")
				continue
			ddm.write_demo_info([self.target_file], [None], mode)
			# NOTE: If something fails here, info is destroyed. Could of course store it
			# from above but it's such a stupidly unlikely condition.
			ddm.write_demo_info([new_name], [di], mode)

		ddm.flush()

		res = ddm.get_write_results()
		for mode in tuple(self.pending_modes):
			if (
				mode not in res or
				res[mode][new_name] is not None or res[mode][self.target_file] is not None
			):
				# Fail. mode may not even be in res due to failure getting demo info.
				print("1Failure.", res[mode])
			else:
				self.pending_modes.remove(mode)

		if self.pending_rename or self.pending_modes:
			# failure
			print("2Failure.")
		else:
			self.result.data = new_name
			self.result.state = DIAGSIG.SUCCESS
			self.destroy()

	def _exit(self) -> None:
		self.result.data = None
		self.result.state = DIAGSIG.FAILURE
		self.destroy()

	def destroy(self):
		super().destroy()
