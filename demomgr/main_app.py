import os
from copy import deepcopy
import json
import sys
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg
from _tkinter import TclError

import multiframe_list.multiframe_list as mfl
from schema import SchemaError

from demomgr import constants as CNST
from demomgr import context_menus
from demomgr.config import Config
from demomgr.demo_info import DemoInfo
from demomgr.dialogues import *
from demomgr.tk_widgets import KeyValueDisplay, HeadedFrame
from demomgr.helpers import build_date_formatter, convertunit, deepupdate_dict, \
	none_len_formatter, none_len_sortkey
from demomgr.style_helper import StyleHelper
from demomgr import platforming
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, ThreadFilter, ThreadReadFolder, ThreadDemoInfo

__version__ = "1.9.0"
__author__ = "Square789"

class MainApp():
	def __init__(self):
		"""
		Initializes values, variables, reads config, checks for firstrun,
		applies UI style, sets up interface, then shows main window.
		"""
		self.root = tk.Tk()
		self.root.withdraw()

		self.RCB = platforming.get_rightclick_btn()

		self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
		self.root.wm_title(f"Demomgr v{__version__} by {__author__}")

		self.demooperations = (
			("Play", " selected demo...", self._playdem),
			("Delete", " selected demo...", self._deldem),
			("Manage bookmarks", " of selected demo...", self._managebookmarks)
		)

		self.cfgpath = platforming.get_cfg_storage_path()
		self.curdir = "" # Should NEVER be in self.cfg.demo_paths!
		self.spinboxvar = tk.StringVar()

		self.after_handle_statusbar = self.root.after(0, lambda: True)

		# Threading setup
		self.threadgroups = {
			"cleanup": ThreadGroup(ThreadFilter, self.root),
			"demoinfo": ThreadGroup(ThreadDemoInfo, self.root),
			"fetchdata": ThreadGroup(ThreadReadFolder, self.root),
			"filter": ThreadGroup(ThreadFilter, self.root),
		}

		self.threadgroups["cleanup"].register_finalize_method(self._finalization_cleanup)
		self.threadgroups["fetchdata"].register_finalize_method(self._finalization_fetchdata)

		self.threadgroups["cleanup"].decorate_and_patch(self, self._after_callback_cleanup)
		self.threadgroups["demoinfo"].decorate_and_patch(self, self._after_callback_demoinfo)
		self.threadgroups["fetchdata"].decorate_and_patch(self, self._after_callback_fetchdata)
		self.threadgroups["filter"].decorate_and_patch(self, self._after_callback_filter)

		# startup routine
		is_firstrun = False
		if os.path.exists(self.cfgpath):
			self.cfg = self.getcfg()
			if self.cfg is None: # Quit
				return
			if self.cfg.first_run:
				is_firstrun = True
		else:
			try:
				os.makedirs(
					os.path.dirname(self.cfgpath), # self.cfgpath ends in a file, should be ok
					exist_ok = True
				)
			except (OSError, IOError, PermissionError) as exc:
				tk_msg.showerror(
					"Demomgr - Error", f"The following error occurred during startup: {exc}"
				)
				self.quit_app(False)
				return
			self.cfg = Config.get_default()
			self.writecfg()
			is_firstrun = True

		# load style (For FirstRun)
		self.ttkstyle = ttk.Style() # Used later-on too.
		# Fallback that is different depending on the platform.
		self._DEFAULT_THEME = self.ttkstyle.theme_use()
		self._applytheme()

		if is_firstrun:
			fr_dialog = FirstRun(self.root)
			fr_dialog.show()
			if fr_dialog.result.state != DIAGSIG.SUCCESS:
				self.quit_app()
				return
			self.cfg.first_run = False

		#set up UI; create widgets
		self._setupgui()

		self.root.bind("<<MultiframeSelect>>", self._mfl_lc_callback)
		self.root.bind("<<MultiframeRightclick>>", self._mfl_rc_callback)

		ctxmen_name = platforming.get_contextmenu_btn()
		for class_tag in ("TEntry", "TCombobox"):
			self.root.bind_class(
				class_tag,
				f"<Button-{self.RCB}><ButtonRelease-{self.RCB}>",
				context_menus.entry_cb
			)
			# This interrupts the event seq above
			self.root.bind_class(
				class_tag,
				f"<Button-{self.RCB}><Leave><ButtonRelease-{self.RCB}>",
				lambda _: None
			)
			if ctxmen_name is not None:
				self.root.bind_class(
					class_tag, f"<KeyPress-{ctxmen_name}>", context_menus.entry_cb
				)

		last_path = ""
		if self.cfg.last_path is not None:
			last_path = self.cfg.demo_paths[self.cfg.last_path]
		self.curdir = last_path
		self.spinboxvar.set(last_path)
		self.reloadgui()
		# All subsequent changes to the spinbox will call
		# self._spinboxsel -> self.reloadgui, and update main view.
		self.spinboxvar.trace("w", self._spinboxsel)

		self.root.deiconify() # end startup; show UI
		self.root.focus()

	def _setupgui(self):
		"""Sets up UI inside of self.root widget."""
		self.mainframe = ttk.Frame(self.root, padding = (5, 3, 5, 3))

		self.mainframe.grid_columnconfigure(0, weight = 10)
		self.mainframe.grid_columnconfigure(1, weight = 15)
		self.mainframe.grid_rowconfigure(3, weight = 2)
		self.mainframe.grid_rowconfigure(4, weight = 1)

		self.filterentry_var = tk.StringVar()

		widgetframe0 = ttk.Frame(self.mainframe) # Directory Selection, Settings/About
		widgetframe1 = ttk.Frame(self.mainframe) # Filtering / Cleanup by filter
		widgetframe2 = ttk.Frame(self.mainframe) # Buttons here interact with the currently selected demo
		self.listboxframe = ttk.Frame(self.mainframe)
		demoinfframe = HeadedFrame(self.mainframe, hlabel_conf = {"text": "Demo information"})
		dirinfframe = HeadedFrame(self.mainframe, hlabel_conf = {"text": "Directory information"})
		self.statusbar = ttk.Frame(self.mainframe, padding = (1, 2, 1, 1), style = "Statusbar.TFrame")

		dirinfframe.internal_frame.grid_columnconfigure(0, weight = 1)
		dirinfframe.internal_frame.grid_rowconfigure((1, 2), weight = 1)

		demoinfframe.internal_frame.grid_columnconfigure(0, weight = 1)
		demoinfframe.internal_frame.grid_rowconfigure(1, weight = 1)

		# Hardcoded weights that approximately relate to the length of each of the column's strings
		self.listbox = mfl.MultiframeList(
			self.listboxframe, inicolumns = (
				{"name": "Name", "col_id": "col_filename", "sort": True,
					"weight": round(1.5 * mfl.WEIGHT), "dblclick_cmd": lambda _: self._playdem()},
				{"name": "Killstreaks", "col_id": "col_ks", "sort": True,
					"weight": round(0.2 * mfl.WEIGHT), "formatter": none_len_formatter,
					"sortkey": none_len_sortkey},
				{"name": "Bookmarks", "col_id": "col_bm", "sort": True,
					"weight": round(0.2 * mfl.WEIGHT), "formatter": none_len_formatter,
					"sortkey": none_len_sortkey, "dblclick_cmd": lambda _: self._managebookmarks()},
				{"name": "Creation time", "col_id": "col_ctime", "sort": True,
					"weight": round(0.9 * mfl.WEIGHT), "formatter": build_date_formatter(self.cfg)},
				{"name": "Size", "col_id": "col_filesize", "sort": True,
					"weight": round(0.42 * mfl.WEIGHT), "formatter": convertunit}
			), rightclickbtn = self.RCB, resizable = True, reorderable = True,
		)

		self.pathsel_spinbox = ttk.Combobox(widgetframe0, state = "readonly")
		self.pathsel_spinbox.config(values = tuple(self.cfg.demo_paths))
		self.pathsel_spinbox.config(textvariable = self.spinboxvar)

		rempathbtn = ttk.Button(widgetframe0, text = "Remove demo path", command = self._rempath)
		addpathbtn = ttk.Button(widgetframe0, text = "Add demo path...", command = self._addpath)
		settingsbtn = ttk.Button(widgetframe0, text = "Settings...", command = self._opensettings)

		self.demo_header_kvd = KeyValueDisplay(
			demoinfframe.internal_frame, self.ttkstyle,
			inipairs = ({"id_": v, "name": v} for v in CNST.HEADER_HUMAN_NAMES.values()),
			width = 240, height = 80,
		)
		self.demoeventmfl = mfl.MultiframeList(
			demoinfframe.internal_frame, inicolumns = (
				{"name": "Type", "col_id": "col_type", "sort": True, "minsize": 40},
				{"name": "Tick", "col_id": "col_tick", "sort": True, "minsize": 30},
				{"name": "Value", "col_id": "col_value", "sort": False},
			), rightclickbtn = self.RCB, listboxheight = 5,
		)

		self.directory_inf_kvd = KeyValueDisplay(
			dirinfframe.internal_frame, self.ttkstyle, inipairs = (
				{"id_": "l_totalsize", "name": "Size", "formatter": convertunit},
				{"id_": "l_amount", "name": "Amount of demos"}
			), width = 240, height = 60,
		)

		filterlabel = ttk.Label(widgetframe1, text = "Filter demos: ")
		self.filterentry = ttk.Entry(widgetframe1, textvariable = self.filterentry_var)
		self.filterentry.bind("<Return>", self._filter)
		self.filterbtn = ttk.Button(widgetframe1, text = "Apply Filter", command = self._filter)
		self.resetfilterbtn = ttk.Button(
			widgetframe1, text = "Clear Filter / Refresh", command = self.reloadgui
		)
		self.cleanupbtn = ttk.Button(
			widgetframe1, text = "Cleanup by Filter...", command = self._cleanup
		)

		demoopbuttons = [
			ttk.Button(widgetframe2, text = s0 + s1, command = cmd)
			for s0, s1, cmd in self.demooperations
		]
		self.statusbarlabel = ttk.Label(self.statusbar, text = "Ready.", style = "Statusbar.TLabel")

		#widget geometry mgmt here
		#widgetframe0
		self.pathsel_spinbox.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		rempathbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		addpathbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		settingsbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (3, 0))
		widgetframe0.grid(column = 0, row = 0, columnspan = 2, sticky = "ew", pady = 5)

		#widgetframe1
		filterlabel.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (0, 3))
		self.filterentry.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = 3)
		self.filterbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		self.resetfilterbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		self.cleanupbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (3, 0))
		widgetframe1.grid(column = 0, row = 1, columnspan = 2, sticky = "ew", pady = 5)

		#widgetframe2
		for i in demoopbuttons:
			i.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (0, 6))
		widgetframe2.grid(column = 0, row = 2, columnspan = 2, sticky = "ew", pady = 5)

		#listbox
		self.listboxframe.grid_columnconfigure(0, weight = 1, minsize = 500)
		self.listboxframe.grid_rowconfigure(0, weight = 1)
		self.listbox.grid(column = 0, row = 0, sticky = "nesw")
		self.listboxframe.grid(column = 0, row = 3, rowspan = 2, sticky = "nesw")

		#demoinfframe
		self.demoeventmfl.grid(sticky = "nesw", padx = 5, pady = 5)
		self.demo_header_kvd.grid(sticky = "nesw", padx = 5, pady = (0, 5))
		demoinfframe.grid(column = 1, row = 3, sticky = "nesw", padx = 5)

		#dirinfframe
		self.directory_inf_kvd.grid(sticky = "nesw", padx = 5, pady = 5)
		dirinfframe.grid(column = 1, row = 4, sticky = "nesw", padx = 5, pady = (5, 0))

		#Statusbar
		self.statusbarlabel.pack(anchor = tk.W)
		self.statusbar.grid(column = 0, row = 5, columnspan = 2, sticky = "ew")

		#Main frame
		self.mainframe.pack(expand = 1, fill = tk.BOTH, side = tk.TOP, anchor = tk.NW)

	def _mfl_rc_callback(self, event):
		if event.widget._w == self.listbox._w:
			context_menus.multiframelist_cb(event, self.listbox, self.demooperations)

	def _mfl_lc_callback(self, event):
		if event.widget._w == self.listbox._w:
			self._updatedemowindow()

	def quit_app(self, save_cfg = True):
		for g in self.threadgroups.values():
			g.cancel_after() # Calling first to cancel running after callbacks asap
		for g in self.threadgroups.values():
			g.join_thread(finalize = False)
		if save_cfg:
			if self.curdir in self.cfg.demo_paths:
				self.cfg.lastpath = self.cfg.demo_paths.index(self.curdir)
				self.writecfg()
		# Without the stuff below, the root.destroy method will produce
		# strange errors on closing, due to some dark magic regarding after
		# commands.
		for c in list(self.root.children.values()):
			try:
				c.destroy()
			except TclError:
				pass
		self.root.tk.call('destroy', self.root._w)
		tk.Misc.destroy(self.root)
		if tk._support_default_root and tk._default_root is self.root:
			tk._default_root = None
		# Above section copied from tkinter's __init__.py
		try:
			self.root.destroy()
		except TclError:
			pass
		self.root.quit()

	def _opensettings(self):
		"""Opens settings, acts based on results"""
		dialog = Settings(
			self.root,
			cfg = self.cfg,
			remember = self.cfg.ui_remember["settings"],
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.GLITCHED:
			return
		self.cfg.ui_remember["settings"] = dialog.result.remember
		if dialog.result.state == DIAGSIG.SUCCESS:
			# what a hardcoded piece of garbage, there must be better ways
			if self.cfg.date_format != dialog.result.data["date_format"]:
				self.listbox.config_column(
					"col_ctime", formatter = build_date_formatter(dialog.result.data)
				)
			self.cfg.update(**dialog.result.data)
			self.reloadgui()
			self._applytheme()

	def _playdem(self):
		"""Opens dialog which arranges for TF2 launch."""
		index = self.listbox.get_active_cell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		dialog = Play(
			self.root,
			demo_dir = self.curdir,
			info = DemoInfo(
				self.listbox.get_cell("col_filename", index),
				self.listbox.get_cell("col_ks", index),
				self.listbox.get_cell("col_bm", index),
			),
			cfg = self.cfg,
			style = self.ttkstyle,
			remember = self.cfg.ui_remember["launch_tf2"],
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.GLITCHED:
			return
		self.cfg.ui_remember["launch_tf2"] = dialog.result.remember

	def _deldem(self):
		"""Deletes the currently selected demo."""
		index = self.listbox.get_active_cell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.get_cell("col_filename", index)
		dialog = Deleter(
			self.root,
			demodir = self.curdir,
			files = [filename],
			selected = [True],
			evtblocksz = self.cfg.events_blocksize,
			deluselessjson = False,
			styleobj = self.ttkstyle,
		)
		dialog.show()
		if dialog.state == DIAGSIG.GLITCHED:
			return
		if dialog.result.state == DIAGSIG.SUCCESS:
			if self.cfg.lazy_reload:
				self.directory_inf_kvd.set_value(
					"l_amount",
					self.directory_inf_kvd.get_value("l_amount") - 1
				)
				self.directory_inf_kvd.set_value(
					"l_totalsize",
					self.directory_inf_kvd.get_value("l_totalsize") - \
						self.listbox.get_cell("col_filesize", index)
				)
				self.listbox.remove_row(index)
				self._updatedemowindow(clear = True)
			else:
				self.reloadgui()

	def _managebookmarks(self):
		"""Offers dialog to manage a demo's bookmarks."""
		index = self.listbox.get_active_cell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.get_cell("col_filename", index)
		path = os.path.join(self.curdir, filename)
		dialog = BookmarkSetter(
			self.root,
			targetdemo = path,
			bm_dat = self.listbox.get_cell("col_bm", index),
			styleobj = self.ttkstyle,
			evtblocksz = self.cfg.events_blocksize,
			remember = self.cfg.ui_remember["bookmark_setter"],
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.GLITCHED:
			return
		self.cfg.ui_remember["bookmark_setter"] = dialog.result.remember
		if dialog.result.state == DIAGSIG.SUCCESS:
			if self.cfg.lazy_reload:
				if self.cfg.data_grab_mode == 0:
					return
				container_state = dialog.result.data["containers"][self.cfg.data_grab_mode - 1]
				if container_state is None:
					return
				self.listbox.set_cell(
					"col_bm", index, dialog.result.data["bookmarks"] if container_state else None
				)
				self.listbox.format(("col_bm", ), (index, ))
				self._updatedemowindow(no_io = True)
			else:
				self.reloadgui()

	def _applytheme(self):
		"""
		Looks at self.cfg, attempts to apply an interface theme using a
		StyleHelper.
		"""
		if self.cfg.ui_theme == "_DEFAULT":
			self.root.tk.call("ttk::setTheme", self._DEFAULT_THEME)
			return
		try:
			theme_tuple = CNST.THEME_PACKAGES[self.cfg.ui_theme]
			# Really hacky way of doing this
			theme_path = os.path.join(os.path.dirname(__file__), CNST.THEME_SUBDIR, theme_tuple[0])
		except KeyError:
			tk_msg.showerror("Demomgr - Error", "Cannot find Tcl theme, using default.")
			return
		try:
			stylehelper = StyleHelper(self.root)
			imgdir = os.path.join(os.path.dirname(__file__), CNST.THEME_SUBDIR, theme_tuple[2])
			stylehelper.load_image_dir(imagedir = imgdir, filetypes = ("png", ), imgvarname = "IMG")
			stylehelper.load_theme(theme_path, theme_tuple[1])
		except TclError as error:
			tk_msg.showerror("Demomgr - Error", f"A Tcl error occurred:\n{error}")
		except (OSError, PermissionError, FileNotFoundError) as error:
			tk_msg.showerror(
				"Demomgr - Error",
				f"The theme file was not found or a permission problem occurred:\n{error}"
			)

	def _updatedemowindow(self, clear = False, no_io = False):
		"""Renew contents of demo information windows"""
		index = self.listbox.get_active_cell()[1]
		if not no_io:
			self.demo_header_kvd.clear()
		self.demoeventmfl.clear()
		if clear or index is None:
			return

		ks = self.listbox.get_cell("col_ks", index)
		bm = self.listbox.get_cell("col_bm", index)
		if not (ks is None or bm is None):
			for t, n in ((ks, "Killstreak"), (bm, "Bookmark")):
				for streak, tick in t:
					self.demoeventmfl.insert_row({
						"col_type": n,
						"col_tick": tick,
						"col_value": str(streak),
					})

		if not self.cfg.preview_demos or no_io:
			return

		demname = self.listbox.get_cell("col_filename", index)
		# In case of a super slow drive, this will hang in order to
		# prevent multiple referenceless threads going wild in the demo directory
		self.threadgroups["demoinfo"].join_thread()
		self.threadgroups["demoinfo"].start_thread(target_demo_path = os.path.join(self.curdir, demname))

	def _after_callback_demoinfo(self, queue_elem):
		"""
		Loop worker for the demo_info thread.
		Updates demo info window with I/O-obtained information.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if queue_elem[0] < 0x100: # Finish
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.RESULT_HEADER:
			for k, v in queue_elem[1].items():
				if k in CNST.HEADER_HUMAN_NAMES:
					self.demo_header_kvd.set_value(CNST.HEADER_HUMAN_NAMES[k], str(v))
			return THREADGROUPSIG.CONTINUE
		elif queue_elem[0] == THREADSIG.RESULT_FS_INFO:
			return THREADGROUPSIG.CONTINUE

	def reloadgui(self):
		"""
		Re-fetches a directory's contents.
		This function starts the fetchdata thread.
		"""
		for g in self.threadgroups.values():
			g.cancel_after()
		self.listbox.clear()
		self.directory_inf_kvd.clear()
		for g in self.threadgroups.values():
			g.join_thread(finalize = False)
		self.threadgroups["fetchdata"].start_thread(
			targetdir = self.curdir,
			cfg = self.cfg,
		)
		self._updatedemowindow(clear = True)

	def _after_callback_fetchdata(self, queue_elem):
		"""
		Loop worker for the after callback decorator stub.
		Grabs thread signals from the fetchdata queue and
		acts accordingly.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if queue_elem[0] < 0x100: # Finish
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queue_elem[1])
		elif queue_elem[0] == THREADSIG.RESULT_DEMO_AMOUNT:
			self.directory_inf_kvd.set_value("l_amount", queue_elem[1])
		elif queue_elem[0] == THREADSIG.RESULT_DEMODATA:
			self.listbox.set_data(queue_elem[1])
			self.listbox.format()
		return THREADGROUPSIG.CONTINUE

	def _finalization_fetchdata(self, qeue_elem):
		self.directory_inf_kvd.set_value(
			"l_totalsize", sum(self.listbox.get_column("col_filesize"))
		)

	def _cleanup(self):
		"""
		Starts a filtering thread and calls the cleanup after callback
		to open a Deleter dialog once the thread finishes.
		"""
		if self.filterentry_var.get() == "":
			return
		self.threadgroups["cleanup"].start_thread(
			filterstring = self.filterentry_var.get(),
			curdir = self.curdir,
			silent = True,
			cfg = self.cfg,
		)
		self.cleanupbtn.config(text = "Cleanup by filter...", state = tk.DISABLED)

	def _after_callback_cleanup(self, queue_elem):
		"""
		Loop worker for the after callback decorator stub.
		Grabs thread signals from the cleanup queue and acts
		accordingly, opening a Deletion dialog once the thread is done.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if queue_elem[0] < 0x100: # Finish
			self.cleanupbtn.config(text = "Cleanup by filter...", state = tk.NORMAL)
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queue_elem[1])
			return THREADGROUPSIG.CONTINUE
		elif queue_elem[0] == THREADSIG.RESULT_DEMODATA:
			return THREADGROUPSIG.HOLDBACK

	def _finalization_cleanup(self, queue_elem):
		if queue_elem is None:
			return
		if queue_elem[0] != THREADSIG.RESULT_DEMODATA: # weird
			return
		del_diag = Deleter(
			self.root,
			demodir = self.curdir,
			files = queue_elem[1]["col_filename"],
			selected = [True for _ in queue_elem[1]["col_filename"]],
			deluselessjson = False,
			evtblocksz = self.cfg.events_blocksize,
			styleobj = self.ttkstyle,
			eventfileupdate = "passive",
		)
		del_diag.show()
		if del_diag.result.state == DIAGSIG.SUCCESS:
			self.reloadgui() # Can not honor lazyreload here.

	def _filter(self, *_):
		"""Starts a filtering thread and configures the filtering button."""
		if not self.filterentry_var.get() or self.curdir == "":
			return
		self.filterbtn.config(
			text = "Stop Filtering", command = lambda: self._stopfilter(True)
		)
		self.filterentry.unbind("<Return>")
		self.resetfilterbtn.config(state = tk.DISABLED)
		self.threadgroups["filter"].start_thread(
			filterstring = self.filterentry_var.get(),
			curdir = self.curdir,
			silent = False,
			cfg = self.cfg,
		)

	def _stopfilter(self, called_by_user = False):
		"""
		Stops the filtering thread by calling the threadgroup's join method.
		As this invokes the after callback, button states will be reverted.
		"""
		self.threadgroups["filter"].join_thread()

	def _after_callback_filter(self, queue_elem):
		"""
		Loop worker for the after handler callback stub.
		Grabs elements from the filter queue and updates the statusbar with
		the filtering progress. If the thread is done, fills listbox with new
		dataset.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if queue_elem[0] < 0x100: # Finish
			if queue_elem[0] == THREADSIG.ABORTED:
				self.setstatusbar("", 0)
			self.resetfilterbtn.config(state = tk.NORMAL)
			self.filterbtn.config(text = "Apply Filter", command = self._filter)
			self.filterentry.bind("<Return>", self._filter)
			self._updatedemowindow(clear = True)
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queue_elem[1])
			return THREADGROUPSIG.CONTINUE
		elif queue_elem[0] == THREADSIG.RESULT_DEMODATA:
			self.listbox.set_data(queue_elem[1])
			self.listbox.format()
			return THREADGROUPSIG.CONTINUE

	def _spinboxsel(self, *_):
		"""
		Observer callback to self.spinboxvar; is called whenever
		self.spinboxvar (so the combobox) is updated.
		Also triggered by self._rempath.
		Kicks off the process of reading the current directory.
		"""
		selpath = self.spinboxvar.get()
		if selpath != self.curdir:
			self.curdir = selpath
			self.reloadgui()

	def setstatusbar(self, data, timeout = None):
		"""Set statusbar text to data (str)."""
		self.statusbarlabel.after_cancel(self.after_handle_statusbar)
		self.statusbarlabel.config(text = str(data))
		self.statusbarlabel.update()
		if timeout is not None:
			self.after_handle_statusbar = self.statusbarlabel.after(
				timeout, lambda: self.setstatusbar(CNST.STATUSBARDEFAULT)
			)

	def _addpath(self):
		"""
		Offers a directory selection dialog and writes the selected
		directory path to config after validating.
		"""
		dirpath = tk_fid.askdirectory(title = "Select the folder containing your demos.")
		if dirpath == "":
			return
		if dirpath in self.cfg.demo_paths:
			return
		self.cfg.demo_paths.append(dirpath)
		# NOTE: doesnt this call reloadgui twice? check it
		self.spinboxvar.set(dirpath)
		self.pathsel_spinbox.config(values = tuple(self.cfg.demo_paths))
		self.reloadgui()

	def _rempath(self):
		"""
		Removes the current directory from the registered directories,
		automatically moves to another one or sets the current directory
		to "" if none are available anymore.
		"""
		if not self.cfg.demo_paths:
			return
		popindex = self.cfg.demo_paths.index(self.curdir)
		self.cfg.demo_paths.pop(popindex)
		if len(self.cfg.demo_paths) > 0:
			self.spinboxvar.set(self.cfg.demo_paths[(popindex - 1) % len(self.cfg.demo_paths)])
		else:
			self.spinboxvar.set("")
		self.pathsel_spinbox.config(values = tuple(self.cfg.demo_paths))

	def writecfg(self):
		"""
		Writes the `Config` in `self.cfg` to self.cfgpath, converted to JSON.
		On write error, opens the CfgError dialog, blocking until the issue is 
		ixed.
		"""
		write_ok = False
		while not write_ok:
			try:
				with open(self.cfgpath, "w") as handle:
					handle.write(self.cfg.to_json())
				write_ok = True
			except Exception as error:
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = error, mode = 1)
				dialog.show()
				if dialog.result.data == 0: # Retry
					pass
				elif dialog.result.data == 1: # Config replaced by dialog
					pass
				elif dialog.result.data == 2 or dialog.result.state == DIAGSIG.GLITCHED: # Quit
					self.quit_app(False)
					return

	def getcfg(self):
		"""
		Gets config from self.cfgpath and returns it. On error, blocks
		until program is closed, config is replaced or fixed.
		If the user chose to quit demomgr after an error, this method will
		return `None`.
		"""
		cfg = None
		while cfg is None:
			try:
				cfg = Config.load_and_validate(self.cfgpath)
			except (json.decoder.JSONDecodeError, FileNotFoundError, OSError, SchemaError) as exc:
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = exc, mode = 0)
				dialog.show()
				if dialog.result.data == 0: # Retry
					pass
				elif dialog.result.data == 1: # Config replaced by dialog
					pass
				elif dialog.result.data == 2 or dialog.result.state == DIAGSIG.GLITCHED: # Quit
					self.quit_app(False)
					return None
		return cfg
