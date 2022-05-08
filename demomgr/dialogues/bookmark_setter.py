"""
This module contains the BookmarkSetter dialog which offers the ability
to modify a demo's bookmarks in both json file and _events.txt.
If an info container would end up completely empty (neither killstreaks
nor bookmarks), it is ignored / not written.
"""

from datetime import datetime
import os
import tkinter as tk
import tkinter.ttk as ttk

import multiframe_list as mfl
from demomgr.demo_info import DemoEvent

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr.helpers import frmd_label, int_validator, name_validator
from demomgr import constants as CNST
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, ThreadMarkDemo
from demomgr.tk_widgets import TtkText
from demomgr.tk_widgets.misc import DynamicLabel

class BookmarkSetter(BaseDialog):
	"""
	Dialog that offers ability to modify and then write demo
	information into a demo's json file or _events.txt entry.

	After the dialog is closed:
		If the thread succeeded at least once, `self.result.state`
			is SUCCESS and the new bookmarks can be found in
			`self.result.data["bookmarks"]` in the usual primitive
			format. They are the ones a successful marking thread was
			most recently started with but not guaranteed to be the ones
			on disk. Check the `"containers"` key to verify that the
			bookmarks were successfully written to a specific container.
			`self.result.data["containers"]` will be a sequence of booleans
			denoting the state of information containers, `True` if a
			container now exists, `False` if it doesn't and `None` if
			something went wrong, in which case the container's
			existence and contents are unchanged.
			Containers are 0: _events.txt; 1: json file
		If the thread only failed or wasn't even started,
		`self.result.data` will be an empty dict.
	"""
	# this docstring and class hurts my head, is needlessly overcomplicated and
	# i hope i don't have to deal with it again

	def __init__(self, parent, targetdemo, bm_dat, styleobj, cfg):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		targetdemo: Full path to the demo that should be marked.
		bm_dat: Bookmarks for the specified demo as a list of DemoEvents.
			May also be None, which is treated as an empty list.
		styleobj: Instance of `tkinter.ttk.Style`
		cfg: Program configuration.
		"""
		super().__init__(parent, "Bookmark Setter")

		self.result.data = {}

		self.targetdemo = targetdemo
		self.demo_dir = os.path.dirname(targetdemo)
		self.bm_dat = bm_dat
		self.styleobj = styleobj
		self.cfg = cfg

		# Bookmarks that should be written by the thread
		self.thread_target_bookmarks = None
		# Container state maintained while thread is running; dropped
		# if thread fails
		self.thread_container_state = None

		self.threadgroup = ThreadGroup(ThreadMarkDemo, parent)
		self.threadgroup.build_cb_method(self._mark_after_callback)

	def body(self, parent):
		"""UI setup, listbox filling."""
		self.protocol("WM_DELETE_WINDOW", self.destroy)

		parent.rowconfigure(0, weight = 1, pad = 5)
		parent.rowconfigure(2, pad = 5)
		parent.columnconfigure((0, 1), weight = 1)

		widgetcontainer = ttk.Frame(parent)#, style = "Contained.TFrame")
		widgetcontainer.columnconfigure(0, weight = 4)
		widgetcontainer.columnconfigure((1, 2), weight = 1)
		widgetcontainer.rowconfigure(3, weight = 1)

		self.listbox = mfl.MultiframeList(
			widgetcontainer,
			inicolumns = (
				{"name": "Name", "col_id": "col_name"},
				{"name": "Tick", "col_id": "col_tick"},
			),
			selection_type = mfl.SELECTION_TYPE.SINGLE,
		)
		self.listbox.grid(row = 0, column = 0, rowspan = 4, sticky = "news")
		insert_opt_lblfrm = ttk.Labelframe(
			widgetcontainer, labelwidget = frmd_label(widgetcontainer, "Bookmark data:")
		)
		insert_opt_lblfrm.columnconfigure(1, weight = 1)
		ttk.Label(
			insert_opt_lblfrm, style = "Contained.TLabel", text = "Name:"
		).grid(row = 0, column = 0)
		ttk.Label(
			insert_opt_lblfrm, style = "Contained.TLabel", text = "Tick:"
		).grid(row = 1, column = 0)
		self.name_entry = ttk.Entry(
			insert_opt_lblfrm, validate = "key",
			validatecommand = (parent.register(name_validator), "%P")
		)
		self.tick_entry = ttk.Entry(
			insert_opt_lblfrm, validate = "key",
			validatecommand = (parent.register(int_validator), "%S", "%P")
		)
		apply_btn = ttk.Button(
			insert_opt_lblfrm, text = "Apply", command = self._apply_changes
		)
		self.name_entry.grid(row = 0, column = 1, sticky = "ew", padx = 5, pady = 5)
		self.tick_entry.grid(row = 1, column = 1, sticky = "ew", padx = 5, pady = 5)
		self.name_entry.bind("<Return>", self._apply_changes)
		self.tick_entry.bind("<Return>", self._apply_changes)
		apply_btn.grid(row = 2, column = 1, sticky = "ew", padx = 5, pady = 5)
		insert_opt_lblfrm.grid(
			row = 0, column = 1, sticky = "ew", padx = (5, 0), columnspan = 2
		)

		add_bm_btn = ttk.Button(widgetcontainer, text = "New", command = self._add_bookmark)
		rem_bm_btn = ttk.Button(widgetcontainer, text = "Remove", command = self._rem_bookmark)

		add_bm_btn.grid(row = 1, column = 1, sticky = "ew", padx = (5, 0), pady = 5)
		rem_bm_btn.grid(row = 1, column = 2, sticky = "ew", padx = (5, 0), pady = 5)

		widgetcontainer.grid(row = 0, column = 0, columnspan = 2, sticky = "news")

		self.warning_label = DynamicLabel(
			500, 250, parent,
			text = (
				"Note: Hitting \"Save\" will replace all existing bookmarks for this demo "
				"with the ones specified in the listbox above."
			),
			style = "Info.TLabel",
			wraplength = 500,
		)
		self.warning_label.grid(row = 1, column = 0, columnspan = 2, sticky = "news", pady = 5)

		self.textbox = TtkText(
			parent, self.styleobj, height = 8, wrap = "none", takefocus = False
		)
		self.textbox.grid(row = 2, column = 0, columnspan = 2, sticky = "news", pady = 5)
		self.textbox.lower()

		self.savebtn = ttk.Button(parent, text = "Save", command = self._mark)
		cancelbtn = ttk.Button(parent, text = "Close", command = self.destroy)

		self.savebtn.grid(row = 3, column = 0, padx = (0, 3), sticky = "ew")
		cancelbtn.grid(row = 3, column = 1, padx = (3, 0), sticky = "ew")

		self.listbox.bind("<<MultiframeSelect>>", self._callback_bookmark_selected)

		self._fill_gui()
		self._log(f"\nMarking {os.path.split(self.targetdemo)[1]}")

	def _add_bookmark(self):
		name = self.name_entry.get()
		tick = self.tick_entry.get()
		tick = int(tick) if tick else 0
		self.listbox.insert_row(
			{"col_name": name, "col_tick": tick},
			self._find_insertion_index(tick),
		)

	def _apply_changes(self, *_):
		"""
		Apply user-entered name and tick to the mfl entry and reinsert it
		into the list at correct position.
		"""
		if not self.listbox.selection:
			self._log("No bookmark selected to change.")
			return
		index = self.listbox.get_selection()
		new_name, new_tick = self.name_entry.get(), self.tick_entry.get()
		new_tick = int(new_tick) if new_tick else 0
		self.listbox.remove_rows(index)
		new_idx = self._find_insertion_index(int(new_tick))
		self.listbox.insert_row({"col_name": new_name, "col_tick": new_tick}, new_idx)
		self.listbox.set_selection((new_idx,))

	def _callback_bookmark_selected(self, *_):
		self.name_entry.delete(0, tk.END)
		self.tick_entry.delete(0, tk.END)
		if not self.listbox.selection:
			return
		idx = self.listbox.get_selection()
		data, col_idx = self.listbox.get_rows(idx)
		new_name, new_tick = data[0][col_idx["col_name"]], data[0][col_idx["col_tick"]]
		self.name_entry.insert(0, new_name)
		self.tick_entry.insert(0, str(new_tick))

	def _cancel_mark(self):
		self.threadgroup.join_thread()

	def _find_insertion_index(self, tick):
		"""
		Returns index to insert a new tick number at, assuming the list is
		sorted by tick ascending
		"""
		insidx = 0
		for i in range(self.listbox.get_length()):
			if self.listbox.get_cell("col_tick", i) > tick:
				break
			insidx += 1
		return insidx

	def _fill_gui(self):
		"""Called by body, loads bookmarks into the listbox."""
		if self.bm_dat is None:
			return
		for n, t, _ in self.bm_dat:
			self.listbox.insert_row({"col_name": n, "col_tick": t})

	def _log(self, to_log, newline = True):
		"""
		Inserts `to_log` + `"\n"` into self.textbox, or just `to_log`
		if `newline` is False.
		"""
		suffix = "\n" if newline else ""
		with self.textbox:
			self.textbox.insert(tk.END, to_log + suffix)
			if self.textbox.yview()[1] < 1.0:
				self.textbox.delete("1.0", "2.0")
				self.textbox.yview_moveto(1.0)

	def _mark(self):
		date = datetime.now().strftime("%Y/%m/%d %H:%M")
		self.thread_target_bookmarks = [
			DemoEvent(n, t, date) for n, t in zip(
				self.listbox.get_column("col_name"),
				map(int, self.listbox.get_column("col_tick")),
			)
		]
		self.thread_container_state = [None, None]

		self.savebtn.configure(text = "Cancel", command = self._cancel_mark)
		self.threadgroup.start_thread(
			bookmarks = self.thread_target_bookmarks,
			targetdemo = self.targetdemo,
			cfg = self.cfg,
		)

	def _mark_after_callback(self, sig, *args):
		if sig.is_finish_signal():
			self.savebtn.configure(text = "Save", command = self._mark)
			if sig is THREADSIG.SUCCESS:
				self.result.state = DIAGSIG.SUCCESS
				self.result.data["bookmarks"] = self.thread_target_bookmarks
				self.result.data["containers"] = self.thread_container_state
			return THREADGROUPSIG.FINISHED

		elif sig is THREADSIG.BOOKMARK_CONTAINER_UPDATE_START:
			self._log(f"Updating {args[0].get_display_name()}...", False)

		elif sig is THREADSIG.BOOKMARK_CONTAINER_UPDATE_SUCCESS:
			mode, exists = args
			self.thread_container_state[mode.value - 1] = exists
			self._log(f"Success!")

		elif sig is THREADSIG.BOOKMARK_CONTAINER_UPDATE_FAILURE:
			self._log(f"Failure: {args[1]}.")

		return THREADGROUPSIG.CONTINUE

	def _rem_bookmark(self):
		if self.listbox.selection:
			self.listbox.remove_rows(self.listbox.get_selection())
		else:
			self._log("No bookmark to remove selected.")

	def destroy(self):
		self._cancel_mark()
		super().destroy()
