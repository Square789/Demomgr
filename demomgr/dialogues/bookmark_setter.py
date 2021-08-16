"""
This module contains the BookmarkSetter dialog which offers the ability
to modify a demo's bookmarks in both json file and _events.txt.
If an info container would end up completely empty (neither killstreaks
nor bookmarks), it is ignored / not written.
"""

import tkinter as tk
import tkinter.ttk as ttk

import os

import multiframe_list as mfl

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr.helpers import frmd_label, int_validator, name_validator
from demomgr import constants as CNST
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, ThreadMarkDemo
from demomgr.tk_widgets import TtkText

class BookmarkSetter(BaseDialog):
	"""
	Dialog that offers ability to modify and then write demo
	information into a demo's json file or _events.txt entry.

	After the dialog is closed:
	If the thread succeeded at least once, `self.result.state` is SUCCESS,
	the new bookmark tuple can be found in `self.result.data["bookmarks"]`
	in the usual primitive format. These are not guaranteed to be the bookmarks
	on disk, but the ones entered in the UI by the user.
	`self.result.data["containers"]` will be a 2-value tuple of booleans denoting
	the state of information containers, True if a container now exists, False if
	it doesn't and None if something went wrong, in which case the container's
	existence is unchanged. Containers are 0: _events.txt; 1: json file
	If the thread failed or wasn't even started, `self.result.data` will be
	an empty dict.

	Widget state remembering:
	0: json checkbox (bool)
	1: _events.txt checkbox (bool)
	"""

	REMEMBER_DEFAULT = [False, False]

	def __init__(self, parent, targetdemo, bm_dat, styleobj, evtblocksz, remember):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		targetdemo: Full path to the demo that should be marked.
		bm_dat: Bookmarks for the specified demo in the usual info format
			(((killstreak_peak, tick), ...), ((bookmark_name, tick), ...))
		styleobj: Instance of `tkinter.ttk.Style`
		evtblocksz: Size of blocks to read _events.txt in.
		remember: List of arbitrary values. See class docstring for details.
		"""
		super().__init__(parent, "Insert bookmark...")

		self.result.data = {}

		self.targetdemo = targetdemo
		self.demo_dir = os.path.dirname(targetdemo)
		self.bm_dat = bm_dat
		self.styleobj = styleobj
		self.evtblocksz = evtblocksz

		u_r = self.validate_and_update_remember(remember)
		self.jsonmark_var = tk.BooleanVar()
		self.eventsmark_var = tk.BooleanVar()
		self.jsonmark_var.set(u_r[0])
		self.eventsmark_var.set(u_r[1])

		self.threadgroup = ThreadGroup(ThreadMarkDemo, parent)
		self.threadgroup.decorate_and_patch(self, self._mark_after_callback)

	def body(self, parent):
		"""UI setup, listbox filling."""
		self.protocol("WM_DELETE_WINDOW", self.destroy)

		parent.rowconfigure(0, weight = 1, pad = 5)
		parent.rowconfigure(1, pad = 5)
		parent.columnconfigure((0, 1), weight = 1)

		widgetcontainer = ttk.Frame(parent)#, style = "Contained.TFrame")
		self.bind("<<MultiframeSelect>>", self._callback_bookmark_selected)
		widgetcontainer.columnconfigure(0, weight = 4)
		widgetcontainer.columnconfigure(1, weight = 1)
		widgetcontainer.columnconfigure(2, weight = 1)
		widgetcontainer.rowconfigure(3, weight = 1)

		self.listbox = mfl.MultiframeList(widgetcontainer, inicolumns = (
			{"name": "Name", "col_id": "col_name"},
			{"name": "Tick", "col_id": "col_tick"},
		))
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

		save_loc_lblfrm = ttk.Labelframe(
			widgetcontainer, labelwidget = frmd_label(widgetcontainer, "Save changes to:")
		)
		json_checkbox = ttk.Checkbutton(
			save_loc_lblfrm, text = ".json",
			variable = self.jsonmark_var, style = "Contained.TCheckbutton"
		)
		events_checkbox = ttk.Checkbutton(
			save_loc_lblfrm, text = CNST.EVENT_FILE, variable = self.eventsmark_var,
			style = "Contained.TCheckbutton"
			)
		json_checkbox.grid(sticky = "w", ipadx = 2, padx = 5, pady = 5)
		events_checkbox.grid(sticky = "w", ipadx = 2, padx = 5, pady = 5)
		save_loc_lblfrm.grid(
			row = 2, column = 1, sticky = "ew", padx = (5, 0), columnspan = 2
		)

		widgetcontainer.grid(row = 0, column = 0, columnspan = 2, sticky = "news")

		self.textbox = TtkText(
			parent, self.styleobj, height = 8, wrap = "none", takefocus = False
		)
		self.textbox.grid(row = 1, column = 0, columnspan = 2, sticky = "news", pady = 5)
		self.textbox.lower()

		self.savebtn = ttk.Button(parent, text = "Save", command = self._mark)
		cancelbtn = ttk.Button(parent, text = "Close", command = self.destroy)

		self.savebtn.grid(row = 2, column = 0, padx = (0, 3), sticky = "ew")
		cancelbtn.grid(row = 2, column = 1, padx = (3, 0), sticky = "ew")

		self._fill_gui()
		self._log(f"Marking {os.path.split(self.targetdemo)[1]}\n")

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
		index = self.listbox.get_selected_cell()[1]
		if index is None:
			self._log("No bookmark selected to change.")
			return
		new_name, new_tick = self.name_entry.get(), self.tick_entry.get()
		new_tick = int(new_tick) if new_tick else 0
		self.listbox.remove_row(index)
		new_idx = self._find_insertion_index(int(new_tick))
		self.listbox.insert_row({"col_name": new_name, "col_tick": new_tick}, new_idx)
		self.listbox.set_selected_cell(0, new_idx)

	def _callback_bookmark_selected(self, *_):
		self.name_entry.delete(0, tk.END)
		self.tick_entry.delete(0, tk.END)
		idx = self.listbox.get_selected_cell()[1]
		if idx is None:
			return
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
		for n, t in self.bm_dat:
			self.listbox.insert_row({"col_name": n, "col_tick": t})

	def _log(self, tolog):
		"""Inserts "\n" + tolog into self.textbox."""
		with self.textbox:
			self.textbox.insert(tk.END, "\n" + tolog)
			if self.textbox.yview()[1] < 1.0:
				self.textbox.delete("1.0", "2.0")
				self.textbox.yview_moveto(1.0)

	def _mark(self):
		mark_json = self.jsonmark_var.get()
		mark_evts = self.eventsmark_var.get()

		raw_bookmarks = tuple(zip(
			self.listbox.get_column("col_name"),
			self.listbox.get_column("col_tick"),
		))

		self.savebtn.configure(text = "Cancel", command = self._cancel_mark)
		self.threadgroup.start_thread(
			mark_json = mark_json,
			mark_events = mark_evts,
			bookmarks = raw_bookmarks,
			targetdemo = self.targetdemo,
			evtblocksz = self.evtblocksz,
		)

	def _mark_after_callback(self, queue_elem):
		if queue_elem[0] < 0x100: # Finish
			self.savebtn.configure(text = "Save", command = self._mark)
			if queue_elem[0] == THREADSIG.SUCCESS:
				self.result.state = DIAGSIG.SUCCESS
				self.result.data["bookmarks"] = tuple(zip(
					self.listbox.get_column("col_name"),
					map(int, self.listbox.get_column("col_tick"))
				))
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.INFO_INFORMATION_CONTAINERS:
			self.result.data["containers"] = queue_elem[1]
		elif queue_elem[0] == THREADSIG.INFO_CONSOLE:
			self._log(queue_elem[1])
			return THREADGROUPSIG.CONTINUE

	def _rem_bookmark(self):
		index = self.listbox.get_selected_cell()[1]
		if index is None:
			self._log("No bookmark to remove selected.")
			return
		self.listbox.remove_row(index)

	def destroy(self):
		self._cancel_mark()
		self.result.remember = [self.jsonmark_var.get(), self.eventsmark_var.get()]
		super().destroy()
