if __name__ == "__main__":
	raise RuntimeError("This script should not be executed directly, only via import.")

import sys
import os
import json
import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg
from _tkinter import TclError
import queue

import multiframe_list as mfl
import schema
from schema import SchemaError

from demomgr import constants as CNST
from demomgr import context_menus
from demomgr.dialogues import *
from demomgr.platforming import get_cfg_storage_path, get_rightclick_btn, get_contextmenu_btn
from demomgr.helper_tk_widgets import TtkText, KeyValueDisplay
from demomgr.helpers import formatdate, convertunit, format_bm_pair, reduce_cfg
from demomgr.style_helper import StyleHelper
from demomgr.threadgroup import ThreadGroup
from demomgr.threads import ThreadFilter, ThreadReadFolder, ThreadDemoInfo

THREADSIG = CNST.THREADSIG
THREADGROUPSIG = CNST.THREADGROUPSIG

__version__ = "1.4.1"
__author__ = "Square789"

class MainApp():
	def __init__(self):
		"""
		Initializes values, variables, reads config, checks for firstrun,
		applies UI style, sets up interface, then shows main window.
		"""
		self.root = tk.Tk()
		self.root.withdraw()

		self.RCB = get_rightclick_btn()

		self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
		self.root.wm_title("Demomgr v" + __version__ + " by " + __author__)

		self.demooperations = (("Play", " selected demo...", self._playdem),
			("Delete", " selected demo...", self._deldem),
			("Manage bookmarks", " of selected demo...", self._managebookmarks))

		self.cfgpath = get_cfg_storage_path()
		self.curdir = "" # This path should not be in self.cfg["demopaths"] at any time!
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

		self.threadgroups["cleanup"].decorate_and_patch(self, self._after_callback_cleanup)
		self.threadgroups["demoinfo"].decorate_and_patch(self, self._after_callback_demoinfo)
		self.threadgroups["fetchdata"].decorate_and_patch(self, self._after_callback_fetchdata)
		self.threadgroups["filter"].decorate_and_patch(self, self._after_callback_filter)

		# startup routine
		is_firstrun = False
		if os.path.exists(self.cfgpath):
			self.cfg = self.getcfg()
			if self.cfg["firstrun"]:
				is_firstrun = True
		else:
			try:
				os.makedirs(
					os.path.dirname(self.cfgpath), # self.cfgpath ends in a file, should be ok
					exist_ok = True)
			except Exception as exc:
				tk_msg.showerror("Demomgr - Error", "The following error" \
					" occurred during startup: {}".format(exc))
				sys.exit()
			self.writecfg(CNST.DEFAULT_CFG)
			self.cfg = CNST.DEFAULT_CFG
			is_firstrun = True

		#load style (For FirstRun)
		self.ttkstyle = ttk.Style() # Used later-on too.
		self._DEFAULT_THEME = self.ttkstyle.theme_use()
		#Fallback that is different depending on the platform.
		self._applytheme()

		if is_firstrun:
			fr_dialog = FirstRun(self.root)
			fr_dialog.show()
			if fr_dialog.result.state == DIAGSIG.FAILURE:
				self.quit_app()
				sys.exit()
			self.cfg["firstrun"] = False
			self.writecfg(self.cfg)

		#set up UI
		self.mainframe = ttk.Frame(self.root, padding = (5, 3, 5, 3))
		self.mainframe.pack(expand = 1, fill = tk.BOTH, side = tk.TOP, anchor = tk.NW)

		#create widgets
		self._setupgui()

		self.root.bind("<<MultiframeSelect>>", self._mfl_lc_callback)
		self.root.bind("<<MultiframeRightclick>>", self._mfl_rc_callback)

		for class_tag in ("TEntry", "TCombobox"):
			self.root.bind_class(class_tag, "<Button-" + self.RCB + ">" \
				"<ButtonRelease-" + self.RCB + ">", context_menus.entry_cb)
			self.root.bind_class(class_tag, "<Button-" + self.RCB + ">" \
				"<Leave><ButtonRelease-" + self.RCB + ">", lambda _: None)
			# This interrupts above event seq
			ctxmen_name = get_contextmenu_btn()
			if ctxmen_name is not None:
				self.root.bind_class(class_tag, "<KeyPress-{}>".format(ctxmen_name),
					context_menus.entry_cb)

		self.spinboxvar.trace("w", self._spinboxsel)
		if os.path.exists(self.cfg["lastpath"]):
			self.spinboxvar.set(self.cfg["lastpath"])
		elif self.cfg["demopaths"]:
			# This will call self._spinboxsel -> self.reloadgui, so the frames are filled.
			self.spinboxvar.set(self.cfg["demopaths"][0])
		self.root.deiconify() #end startup; show UI
		self.root.focus()

	def _setupgui(self):
		"""Sets up UI inside of the self.mainframe widget."""
		self.filterentry_var = tk.StringVar()

		widgetframe0 = ttk.Frame(self.mainframe) #Directory Selection, Settings/About #NOTE: Resquash into tkinter.Menu ?
		widgetframe1 = ttk.Frame(self.mainframe) #Filtering / Cleanup by filter
		widgetframe2 = ttk.Frame(self.mainframe) #Buttons here interact with the currently selected demo
		self.listboxframe = ttk.Frame(self.mainframe)
		demoinfframe = ttk.Frame(self.mainframe, padding = (5, 0, 0, 0))
		dirinfframe = ttk.Frame(self.mainframe, padding = (5, 5, 5, 5))
		self.statusbar = ttk.Frame(self.mainframe, padding = (1, 2, 1, 1),
			style = "Statusbar.TFrame" )

		self.listbox = mfl.MultiframeList(self.listboxframe, inicolumns = (
			{"name": "Filename", "col_id": "col_filename", "sort": True,
				"weight": 5, "minsize": 100, "w_width": 20},
			{"name": "Information", "col_id": "col_demo_info", "sort": False,
				"minsize": 26, "weight": 1, "w_width": 26,
				"formatter": format_bm_pair},
			{"name": "Date created", "col_id": "col_ctime", "sort": True,
				"minsize": 19, "weight": 1, "w_width": 19,
				"formatter": formatdate},
			{"name": "Filesize", "col_id": "col_filesize", "sort": True,
				"minsize": 10, "weight": 1, "w_width": 10,
				"formatter": convertunit}), rightclickbtn = self.RCB)

		self.pathsel_spinbox = ttk.Combobox(widgetframe0, state = "readonly")
		self.pathsel_spinbox.config(values = tuple(self.cfg["demopaths"]))
		self.pathsel_spinbox.config(textvariable = self.spinboxvar)

		rempathbtn = ttk.Button(widgetframe0, text = "Remove demo path",
			command = self._rempath)
		addpathbtn = ttk.Button(widgetframe0, text = "Add demo path...",
			command = self._addpath)
		settingsbtn = ttk.Button(widgetframe0, text = "Settings...",
			command = self._opensettings)

		self.demo_header_kvd = KeyValueDisplay(demoinfframe, self.ttkstyle,
			inikeys = tuple(CNST.HEADER_HUMAN_NAMES.values()), # Below are canvas options
			width = 300, height = 80,
		)
		self.demoeventmfl = mfl.MultiframeList(demoinfframe, inicolumns = (
			{"name": "Type", "col_id": "col_type", "sort": True, "w_width": 10},
			{"name": "Tick", "col_id": "col_tick", "sort": True, "w_width": 8},
			{"name": "Value", "col_id": "col_value", "sort": False},
		), rightclickbtn = self.RCB, listboxheight = 5)

		self.directory_inf_kvd = KeyValueDisplay(dirinfframe, self.ttkstyle)

		filterlabel = ttk.Label(widgetframe1, text = "Filter demos: ")
		filterentry = ttk.Entry(widgetframe1, textvariable = self.filterentry_var)
		self.filterbtn = ttk.Button(widgetframe1, text = "Apply Filter",
			command = self._filter)
		self.resetfilterbtn = ttk.Button(widgetframe1,
			text = "Clear Filter / Refresh", command = self.reloadgui)
		self.cleanupbtn = ttk.Button(widgetframe1, text = "Cleanup by Filter...",
			command = self._cleanup)

		demoopbuttons = [ttk.Button(widgetframe2, text = i[0] + i[1],
			command = i[2]) for i in self.demooperations]
		self.statusbarlabel = ttk.Label(self.statusbar, text = "Ready.",
			style = "Statusbar.TLabel")

		#packing here
		self.statusbarlabel.pack(anchor = tk.W)
		self.statusbar.pack(fill = tk.X, expand = 0, side = tk.BOTTOM)

		#widgetframe0
		self.pathsel_spinbox.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		rempathbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		addpathbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		settingsbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (3, 0))
		widgetframe0.pack(anchor = tk.N, fill = tk.X, pady = 5)

		#widgetframe1
		filterlabel.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (0, 3))
		filterentry.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = 3)
		self.filterbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		self.resetfilterbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		self.cleanupbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (3, 0))
		widgetframe1.pack(anchor = tk.N, fill = tk.X, pady = 5)

		#widgetframe2
		for i in demoopbuttons:
			i.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (0, 6))
		widgetframe2.pack(anchor = tk.N, fill = tk.X, pady = 5)

		self.listbox.pack(fill = tk.BOTH, expand = 1)
		self.listboxframe.pack(fill = tk.BOTH, expand = 1, side = tk.LEFT)

		self.demoeventmfl.pack(expand = 1, fill = tk.BOTH, pady = (0, 5))
		self.demo_header_kvd.pack(expand = 1, fill = tk.BOTH)
		demoinfframe.pack(fill = tk.BOTH, expand = 1)

	def _mfl_rc_callback(self, event):
		if event.widget == self.listbox:
			context_menus.multiframelist_cb(event,
				self.listbox, self.demooperations)

	def _mfl_lc_callback(self, event):
		if event.widget == self.listbox:
			self._updatedemowindow(event)

	def quit_app(self):
		for g in self.threadgroups.values():
			g.cancel_after() # Calling first to cancel running after callbacks asap
		for g in self.threadgroups.values():
			g.join_thread()
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
		dialog = Settings(self.mainframe, self.getcfg())
		dialog.show()
		if dialog.result.state == DIAGSIG.SUCCESS:
			localcfg = self.cfg
			localcfg.update(dialog.result.data)
			self.writecfg(localcfg)
			self.cfg = self.getcfg()
			self.reloadgui()
			self._applytheme()

	def _playdem(self):
		"""Opens dialog which arranges for TF2 launch."""
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.getcell("col_filename", index)
		path = os.path.join(self.curdir, filename)
		dialog = LaunchTF2(self.mainframe,
			demopath = path,
			cfg = reduce_cfg(self.cfg),
			remember = self.cfg["ui_remember"]["launch_tf2"]
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.SUCCESS:
			update_needed = False
			if self.cfg["ui_remember"]["launch_tf2"] != dialog.result.remember:
				update_needed = True
				self.cfg["ui_remember"]["launch_tf2"] = dialog.result.remember
			for i in ("steampath", "hlaepath"):
				if i in dialog.result.data:
					if dialog.result.data[i] != self.cfg[i]:
						update_needed = True
						self.cfg[i] = dialog.result.data[i]
			if update_needed:
				self.writecfg(self.cfg)
				self.cfg = self.getcfg()

	def _deldem(self):
		"""Deletes the currently selected demo."""
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.getcell("col_filename", index)
		dialog = Deleter(self.root,
			demodir = self.curdir,
			files = [filename],
			selected = [True],
			deluselessjson = False,
			cfg = reduce_cfg(self.cfg),
			styleobj = self.ttkstyle
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.SUCCESS:
			if self.cfg["lazyreload"]:
				self.listbox.removerow(index)
				self._updatedemowindow(None)
			else:
				self.reloadgui()

	def _managebookmarks(self):
		"""Offers dialog to manage a demo's bookmarks."""
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.getcell("col_filename", index)
		demo_bm = self.listbox.getcell("col_demo_info", index)
		path = os.path.join(self.curdir, filename)
		dialog = BookmarkSetter(self.root,
			targetdemo = path,
			bm_dat = demo_bm,
			styleobj = self.ttkstyle,
			remember = self.cfg["ui_remember"]["bookmark_setter"]
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.SUCCESS:
			if self.cfg["ui_remember"]["bookmark_setter"] != dialog.result.remember:
				self.cfg["ui_remember"]["bookmark_setter"] = dialog.result.remember
				self.writecfg(self.cfg)
			if self.cfg["lazyreload"]:
				if self.cfg["datagrabmode"] != 0:
					ksdata = self.listbox.getcell("col_demo_info", index)
					ksdata = ksdata[0] if ksdata is not None else ()
					new_bmdata = (ksdata, list(dialog.result.data))
					self.listbox.setcell("col_demo_info", index, new_bmdata)
					self.listbox.format(("col_demo_info", ), (index, ))
					self._updatedemowindow(None)
			else:
				self.reloadgui()

	def _applytheme(self):
		"""
		Looks at self.cfg, attempts to apply an interface theme using a
		StyleHelper.
		"""
		if self.cfg["ui_theme"] == "_DEFAULT":
			self.root.tk.call("ttk::setTheme", self._DEFAULT_THEME)
			return
		try:
			theme_tuple = CNST.THEME_PACKAGES[self.cfg["ui_theme"]]
			theme_path = os.path.join(os.path.dirname(__file__),
				CNST.THEME_SUBDIR, theme_tuple[0]) # Really hacky way of doing this
		except (KeyError):
			tk_msg.showerror("Demomgr - error", "Cannot load theme, interface "
				"will look butchered.")
			return
		try:
			stylehelper = StyleHelper(self.root)
			imgdir = os.path.join(os.path.dirname(__file__),
				CNST.THEME_SUBDIR, theme_tuple[2]) # Still hacky
			stylehelper.load_image_dir(imagedir = imgdir,
				filetypes = ("png", ), imgvarname = "IMG"
			)
			stylehelper.load_theme(theme_path, theme_tuple[1])
		except TclError as error:
			tk_msg.showerror("Demomgr - error", "A tcl error occurred:\n"
				"{}".format(error))
		except (OSError, PermissionError, FileNotFoundError) as error:
			tk_msg.showerror("Demomgr - error", "The theme file was not found "
				"or a permission problem occurred:\n{}".format(error))

	def _updatedemowindow(self, _):
		"""Renew contents of demo information windows"""
		index = self.listbox.getselectedcell()[1]
		self.demo_header_kvd.clear()
		self.demoeventmfl.clear()
		if _ is None or index is None:
			return

		demo_info = self.listbox.getcell("col_demo_info", index)
		if demo_info is not None:
			for t, n in ((demo_info[0], "Killstreak"), (demo_info[1], "Bookmark")):
				for i in t: # Killstreaks
					self.demoeventmfl.insertrow({
						"col_type": n,
						"col_tick": i[1],
						"col_value": str(i[0]),
					})

		if not self.cfg["previewdemos"]:
			# Add "preview disabled" message here
			return
		demname = self.listbox.getcell("col_filename", index) #Get headerinf
		self.threadgroups["demoinfo"].start_thread(
			target_demo_path = os.path.join(self.curdir, demname),
		)

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
		Should be called to re-fetch a directory's contents.
		This function starts the fetchdata thread.
		"""
		for g in self.threadgroups.values():
			g.cancel_after()
		self.listbox.clear()
		for g in self.threadgroups.values():
			g.join_thread(finalize = False)
		self.threadgroups["fetchdata"].start_thread(
			targetdir = self.curdir,
			cfg = self.cfg.copy()
		)
		self._updatedemowindow(None)

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
			return THREADGROUPSIG.CONTINUE
		elif queue_elem[0] == THREADSIG.RESULT_DEMODATA:
			self.listbox.setdata(queue_elem[1])
			self.listbox.format()
			return THREADGROUPSIG.CONTINUE

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
			cfg = self.cfg.copy()
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
			self.cleanupbtn.config(
				text = "Cleanup by filter...", state = tk.NORMAL
			)
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queue_elem[1])
			return THREADGROUPSIG.CONTINUE
		elif queue_elem[0] == THREADSIG.RESULT_DEMODATA:
			return THREADGROUPSIG.HOLDBACK

	def _finalization_cleanup(self, queue_elem):
		if queue_elem[0] != THREADSIG.RESULT_DEMODATA: # weird
			return
		del_diag = Deleter(
			parent = self.root,
			demodir = self.curdir,
			files = queue_elem[1]["col_filename"],
			selected = [True for _ in queue_elem[1]["col_filename"]],
			deluselessjson = False,
			cfg = reduce_cfg(self.cfg),
			styleobj = self.ttkstyle,
			eventfileupdate = "passive",
		)
		del_diag.show()
		if del_diag.result.state == DIAGSIG.SUCCESS:
			self.reloadgui() # Can not honor lazyreload here.

	def _filter(self):
		"""Starts a filtering thread and configures the filtering button."""
		if self.filterentry_var.get() == "" or self.curdir == "":
			return
		self.filterbtn.config(text = "Stop Filtering",
			command = lambda: self._stopfilter(True))
		self.resetfilterbtn.config(state = tk.DISABLED)
		self.threadgroups["filter"].start_thread(
			filterstring = self.filterentry_var.get(),
			curdir = self.curdir,
			silent = False,
			cfg = self.cfg.copy()
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
			self.setstatusbar("", 0)
			self.resetfilterbtn.config(state = tk.NORMAL)
			self.filterbtn.config(text = "Apply Filter", command = self._filter)
			self._updatedemowindow(None)
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queue_elem[1])
			return THREADGROUPSIG.CONTINUE
		elif queue_elem[0] == THREADSIG.RESULT_DEMODATA:
			self.listbox.setdata(queue_elem[1])
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
			if self.cfg["lastpath"] != selpath: # Update lastpath entry
				localcfg = self.cfg
				localcfg["lastpath"] = selpath
				self.writecfg(localcfg)
				self.cfg = self.getcfg()
			self.curdir = selpath
			self.reloadgui()

	def setstatusbar(self, data, timeout = None):
		"""Set statusbar text to data (str)."""
		self.statusbarlabel.after_cancel(self.after_handle_statusbar)
		self.statusbarlabel.config(text = str(data))
		self.statusbarlabel.update()
		if timeout is not None:
			self.after_handle_statusbar = self.statusbarlabel.after(
				timeout, lambda: self.setstatusbar(CNST.STATUSBARDEFAULT))

	def _addpath(self):
		"""
		Offers a directory selection dialog and writes the selected
		directory path to config after validating.
		"""
		dirpath = tk_fid.askdirectory(initialdir = "C:\\",
			title = "Select the folder containing your demos.")
		if dirpath == "":
			return
		localcfg = self.cfg
		if dirpath in localcfg["demopaths"]:
			return
		localcfg["demopaths"].append(dirpath)
		self.writecfg(localcfg)
		self.cfg = self.getcfg()
		self.spinboxvar.set(dirpath)
		self.pathsel_spinbox.config(values = tuple(self.cfg["demopaths"]))
		self.reloadgui()

	def _rempath(self):
		"""
		Removes the current directory from the registered directories,
		automatically moves to another one or sets the current directory
		to "" if none are available anymore.
		"""
		localcfg = self.cfg
		if len(localcfg["demopaths"]) == 0:
			return
		popindex = localcfg["demopaths"].index(self.curdir)
		localcfg["demopaths"].pop(popindex)
		self.writecfg(self.cfg)
		self.cfg = self.getcfg()
		if len(localcfg["demopaths"]) > 0:
			self.spinboxvar.set(localcfg["demopaths"][
				(popindex -1) % len(localcfg["demopaths"])])
		else:
			self.spinboxvar.set("")
		self.pathsel_spinbox.config(values = tuple(localcfg["demopaths"]))

	def writecfg(self, data):
		"""
		Writes config dict specified in data to self.cfgpath, converted
		to JSON. On write error, calls the CfgError dialog, blocking until
		the issue is fixed.
		"""
		write_ok = False
		while not write_ok:
			try:
				with open(self.cfgpath, "w") as handle:
					handle.write(json.dumps(data, indent = 4))
				write_ok = True
			except Exception as error:
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = error, mode = 1)
				dialog.show()
				if dialog.result.data == 0: # Retry
					pass
				elif dialog.result.data == 1: # Config replaced by dialog
					pass
				elif dialog.result.data == 2: # Quit
					self.quit_app()
					sys.exit()

	def getcfg(self):
		"""
		Gets config from self.cfgpath and returns it. On error, blocks
		until program is closed, config is replaced or fixed.
		"""
		localcfg = CNST.DEFAULT_CFG.copy()
		cfg_ok = False
		while not cfg_ok:
			try:
				with open(self.cfgpath, "r") as cfghandle:
					localcfg.update(json.load(cfghandle))
				schema.Schema(CNST.DEFAULT_CFG_SCHEMA).validate(localcfg)
				cfg_ok = True
			except (json.decoder.JSONDecodeError, FileNotFoundError, OSError, SchemaError) as exc:
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = exc, mode = 0)
				dialog.show()
				if dialog.result.data == 0: # Retry
					pass
				elif dialog.result.data == 1: # Config replaced by dialog
					pass
				elif dialog.result.data == 2: # Quit
					self.quit_app()
					sys.exit()
		return localcfg
