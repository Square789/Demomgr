"""
This module contains the BookmarkSetter dialog which offers the ability
to modify a demo's bookmarks in both json file and _events.txt.
If a bookmark container would end up completely empty (neither killstreaks
nor bookmarks), it is ignored / not written.
"""

import tkinter as tk
import tkinter.ttk as ttk

import os
import re
import threading
import queue

import multiframe_list as mfl

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr.helpers import (frmd_label, )
from demomgr import constants as CNST
from demomgr import handle_events as handle_ev
from demomgr.threads import ThreadMarkDemo
from demomgr.helper_tk_widgets import TtkText

THREADSIG = CNST.THREADSIG

class BookmarkSetter(BaseDialog):
	"""
	Dialog that offers ability to modify and then write demo
	information into a demo's json file or _events.txt entry.

	After the dialog is closed:
	If the thread succeeded at least once, `self.result.state` is SUCCESS,
	the new bookmark tuple can be found in `self.result.data` in the usual
	primitive format.
	Else the thread failed or wasn't even started, in which case the data
	is None.
	"""
	def __init__(self, parent, targetdemo, bm_dat, styleobj):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		targetdemo: Full path to the demo that should be marked.
		bm_dat: Bookmarks for the specified demo in the usual bookmark format
			(((killstreak_peak, tick), ...), ((bookmark_name, tick), ...))
		styleobj: Instance of `tkinter.ttk.Style`
		"""
		super().__init__(parent, "Insert bookmark...")

		self.targetdemo = targetdemo
		self.demo_dir = os.path.dirname(targetdemo)
		self.bm_dat = bm_dat
		self.styleobj = styleobj

		self.jsonmark_var = tk.BooleanVar()
		self.eventsmark_var = tk.BooleanVar()

		self.mark_thread = threading.Thread(target = lambda: False)
		self.queue_out = queue.Queue()
		self.after_handler = self.after(0, lambda: None)

	def body(self, parent):
		"""UI setup, listbox filling."""
		def tick_validator(inp, ifallowed):
			if len(ifallowed) > 10:
				return False
			try:
				if int(inp) < 0:
					return False
			except ValueError:
				return False
			return True

		def name_validator(ifallowed):
			if len(ifallowed) > 40:
				return False
			return True

		parent.rowconfigure(0, weight = 1, pad = 5)
		parent.rowconfigure((1, 2), pad = 5)
		parent.columnconfigure((0, 1), weight = 1)

		widgetcontainer = ttk.Frame(parent)#, style = "Contained.TFrame")
		widgetcontainer.columnconfigure(0, weight = 3)
		widgetcontainer.columnconfigure(1, weight = 1)
		widgetcontainer.rowconfigure(4, weight = 1)

		self.listbox = mfl.MultiframeList(widgetcontainer, inicolumns = (
			{"name": "Name", "col_id": "col_name"},
			{"name": "Tick", "col_id": "col_tick"}))
		self.listbox.grid(row = 0, column = 0, rowspan = 2, sticky = "news")

		add_bm_btn = ttk.Button(widgetcontainer, text = "Insert bookmark",
			command = self._add_bookmark)
		rem_bm_btn = ttk.Button(widgetcontainer, text = "Remove bookmark",
			command = self._rem_bookmark)

		self.listbox.grid(row = 0, column = 0, rowspan = 5, sticky = "news")
		add_bm_btn.grid(row = 0, column = 1, sticky = "ew", padx = 5, pady = 5)
		rem_bm_btn.grid(row = 1, column = 1, sticky = "ew", padx = 5, pady = 5)

		insert_opt_lblfrm = ttk.Labelframe(widgetcontainer, labelwidget = \
			frmd_label(widgetcontainer, "Insert options:"))
		insert_opt_lblfrm.columnconfigure(1, weight = 1)
		ttk.Label(insert_opt_lblfrm, style = "Contained.TLabel",
			text = "Name:").grid(row = 0, column = 0)
		ttk.Label(insert_opt_lblfrm, style = "Contained.TLabel",
			text = "Tick:").grid(row = 1, column = 0)
		self.name_entry = ttk.Entry(insert_opt_lblfrm, validatecommand = (
			parent.register(name_validator), "%P"), validate = "key")
		self.tick_entry = ttk.Entry(insert_opt_lblfrm, validatecommand = (
			parent.register(tick_validator), "%S", "%P"), validate = "key")
		self.name_entry.grid(row = 0, column = 1, sticky = "ew", padx = 5, pady = 5)
		self.tick_entry.grid(row = 1, column = 1, sticky = "ew", padx = 5, pady = 5)
		insert_opt_lblfrm.grid(row = 2, column = 1, sticky = "ew", padx = 5,
			pady = 5)

		save_loc_lblfrm = ttk.Labelframe(widgetcontainer, labelwidget = \
			frmd_label(widgetcontainer, "Save changes to:"))
		json_checkbox = ttk.Checkbutton(save_loc_lblfrm, text = ".json",
			variable = self.jsonmark_var, style = "Contained.TCheckbutton")
		events_checkbox = ttk.Checkbutton(save_loc_lblfrm,
			text = CNST.EVENT_FILE, variable = self.eventsmark_var, style = \
			"Contained.TCheckbutton")
		json_checkbox.invoke(); events_checkbox.invoke()
		json_checkbox.grid(sticky = "w", ipadx = 2, padx = 5, pady = 5)
		events_checkbox.grid(sticky = "w", ipadx = 2, padx = 5, pady = 5)
		save_loc_lblfrm.grid(row = 3, column = 1, sticky = "ew", padx = 5,
			pady = 5)

		widgetcontainer.grid(row = 0, column = 0, columnspan = 2,
			sticky = "news")

		self.textbox = TtkText(parent, self.styleobj, height = 8,
			wrap = "none", takefocus = False)
		self.textbox.grid(row = 1, column = 0, columnspan = 2, sticky = "news")
		self.textbox.lower()

		self.savebtn = ttk.Button(parent, text = "Save", command = self._mark)
		cancelbtn = ttk.Button(parent, text = "Close", command = self.destroy)

		self.savebtn.grid(row = 2, column = 0, padx = (0, 3), sticky = "ew")
		cancelbtn.grid(row = 2, column = 1, padx = (3, 0), sticky = "ew")

		self._fill_gui()
		self._log("Marking " + os.path.split(self.targetdemo)[1] + "\n")

	def _log(self, tolog):
		"""Inserts "\n" + tolog into self.textbox ."""
		self.textbox.configure(state = tk.NORMAL)
		self.textbox.insert(tk.END, "\n" + tolog)
		if self.textbox.yview()[1] < 1.0:
			self.textbox.delete("1.0", "2.0")
			self.textbox.yview_moveto(1.0)
		self.textbox.configure(state = tk.DISABLED)

	def _fill_gui(self):
		"""Called by body, loads bookmarks into the listbox."""
		if self.bm_dat == None:
			return
		for i in self.bm_dat[1]:
			self.listbox.insertrow({"col_name":i[0], "col_tick":i[1]})

	def _add_bookmark(self):
		name = self.name_entry.get()
		tick = self.tick_entry.get()
		if name == "" or tick == "":
			self._log("Please specify a name and tick.")
			return
		self.listbox.insertrow({"col_name":name, "col_tick":tick})

	def _rem_bookmark(self):
		index = self.listbox.getselectedcell()[1]
		if index is None:
			self._log("No bookmark to remove selected.")
			return
		self.listbox.removerow(index)

	def _mark(self):
		mark_json = self.jsonmark_var.get()
		mark_evts = self.eventsmark_var.get()
		raw_bookmarks = tuple(zip(self.listbox.getcolumn("col_name"),
			self.listbox.getcolumn("col_tick")))

		self.savebtn.configure(text = "Cancel", command = self._cancel_mark)
		self.mark_thread = ThreadMarkDemo(self.queue_out,
			mark_json = mark_json, mark_events = mark_evts,
			bookmarks = raw_bookmarks, targetdemo = self.targetdemo)
		self.mark_thread.start()
		self.after_handler = self.after(0, self._mark_after_callback)

	def _mark_after_callback(self, call_once = False):
		finished = False
		while True:
			try:
				queueobj = self.queue_out.get_nowait()
				if queueobj[0] < 0x100: # Finish
					finished = True
					self.savebtn.configure(text = "Save", command = self._mark)
					if queueobj[0] == 0x0:
						self.result.state = DIAGSIG.SUCCESS
						self.result.data = tuple(zip(self.listbox.getcolumn("col_name"),
							[int(i) for i in self.listbox.getcolumn("col_tick")]))
				elif queueobj[0] == THREADSIG.INFO_CONSOLE:
					self._log(queueobj[1])
			except queue.Empty:
				break
		if (not finished) and (not call_once):
			self.after_handler = self.after(CNST.GUI_UPDATE_WAIT, self._mark_after_callback)

	def _cancel_mark(self):
		self.after_cancel(self.after_handler)
		if self.mark_thread.isAlive():
			self.mark_thread.join()
		self._mark_after_callback(call_once = True)
		self.queue_out.queue.clear()

	def destroy(self):
		self._cancel_mark()
		super().destroy()
