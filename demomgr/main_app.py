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
from demomgr.get_cfg_location import get_cfg_storage_path
from demomgr.helper_tk_widgets import TtkText
from demomgr.helpers import (formatdate, readdemoheader, convertunit, format_bm_pair)
from demomgr.style_helper import StyleHelper
from demomgr.threads import ThreadFilter, ThreadReadFolder

THREADSIG = CNST.THREADSIG
RCB = "3"

__version__ = "1.1.3"
__author__ = "Square789"

def decorate_callback(hdlr_slot):
	def actual_decorator(func):
		def decorated(self):
			finished = False
			while True:
				try:
					if func(self):
						finished = True
						break
				except queue.Empty:
					break
			if not finished:
				self.after_handlers[hdlr_slot] = \
					self.root.after(CNST.GUI_UPDATE_WAIT,
					lambda: decorated(self))
		return decorated
	return actual_decorator

class MainApp():
	def __init__(self):
		"""
		Initializes values, variables, reads config, checks for firstrun,
		applies UI style, sets up interface, then shows main window.
		"""
		self.root = tk.Tk()
		self.root.withdraw()

		self.RCB = RCB
		if self.root._windowingsystem == "aqua": # should probably work
			self.RCB = "2"

		self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
		self.root.wm_title("Demomgr v" + __version__ + " by " + __author__)

		# TODO: add icon

		self.demooperations = (("Play", " selected demo...", self._playdem),
			("Delete", " selected demo...", self._deldem),
			("Manage bookmarks", " of selected demo...", self._managebookmarks))

		self.cfgpath = get_cfg_storage_path()
		self.curdir = "" # This path should not be in self.cfg["demopaths"] at any time!

		self.after_handlers = {
			"statusbar": self.root.after(0, lambda: True),
			"datafetcher": self.root.after(0, lambda: True),
			"filter": self.root.after(0, lambda: True),
			"cleanup:": self.root.after(0, lambda: True),
		}
		# Used to access output queues filled by threads
		self.threads = {
			"datafetcher": threading.Thread(target = lambda: True),
			"filterer": threading.Thread(target = lambda: True),
			"cleanup": threading.Thread(target = lambda: True),
		} # Dummies
		self.queues = {
			"datafetcher": queue.Queue(),
			"filter": queue.Queue(),
			"cleanup": queue.Queue(),
		}

		self.spinboxvar = tk.StringVar()

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

		self.root.bind("<<MultiframeSelect>>", self._updatedemowindow)
		self.root.bind("<<MultiframeRightclick>>", 
			lambda ev: context_menus.multiframelist_cb(ev, self.listbox,
				self.demooperations))

		for class_tag in ("TEntry", "TCombobox"):
			self.root.bind_class(class_tag, "<Button-" + self.RCB + ">" \
				"<ButtonRelease-" + self.RCB + ">", context_menus.entry_cb)
			self.root.bind_class(class_tag, "<Button-" + self.RCB + ">" \
				"<Leave><ButtonRelease-" + self.RCB + ">", lambda _: None)
			# This interrupts above event seq
			self.root.bind_class(class_tag, "<KeyPress-App>",
				context_menus.entry_cb)

		self.spinboxvar.trace("w", self._spinboxsel)
		if os.path.exists(self.cfg["lastpath"]):
			self.spinboxvar.set(self.cfg["lastpath"])
		elif self.cfg["demopaths"]:
			self.spinboxvar.set(self.cfg["demopaths"][0]) # This will call self._spinboxsel -> self.reloadgui, so the frames are filled.
		self.root.deiconify() #end startup; show UI
		self.root.focus()

	def _setupgui(self):
		"""Sets up UI inside of the self.mainframe widget."""
		self.filterentry_var = tk.StringVar()

		widgetframe0 = ttk.Frame(self.mainframe) #Directory Selection, Settings/About #NOTE: Resquash into tkinter.Menu ?
		widgetframe1 = ttk.Frame(self.mainframe) #Filtering / Cleanup by filter
		widgetframe2 = ttk.Frame(self.mainframe) #Buttons here interact with the currently selected demo
		self.listboxframe = ttk.Frame(self.mainframe)
		demoinfframe = ttk.Frame(self.mainframe, padding = (5, 5, 5, 5))
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

		demoinfbox_scr = ttk.Scrollbar(demoinfframe)
		self.demoinfbox = TtkText(demoinfframe, self.ttkstyle, wrap = tk.WORD,
			state = tk.DISABLED, width = 40, yscrollcommand = demoinfbox_scr.set)
		demoinfbox_scr.config(command = self.demoinfbox.yview)

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

		demoinfbox_scr.pack(side = tk.RIGHT, fill = tk.Y)
		self.demoinfbox.pack(fill = tk.BOTH, expand = 1)
		demoinfframe.pack(fill = tk.BOTH, expand = 1)

	def quit_app(self):
		for k in self.threads:
			if self.threads[k].isAlive():
				self.threads[k].join()
		for a_h in self.after_handlers:
			self.root.after_cancel(self.after_handlers[a_h])
		self.root.update()
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
		dialog = LaunchTF2(self.mainframe, demopath = path,
			cfg = self.cfg)
		dialog.show()
		if dialog.result.state == DIAGSIG.SUCCESS:
			update_needed = False
			for i in ("steampath", "hlaepath"):
				if i in dialog.result.data:
					if dialog.result[i] != self.cfg[i]:
						update_needed = True
						self.cfg[i] = dialog.result[i]
						# accesses dialog.result.data[i]
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
		dialog = Deleter(self.root, demodir = self.curdir, files = [filename],
			selected = [True], deluselessjson = False, cfg = self.cfg,
			styleobj = self.ttkstyle)
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
		dialog = BookmarkSetter(self.root, targetdemo = path,
			bm_dat = demo_bm, styleobj = self.ttkstyle)
		dialog.show()
		if dialog.result.state == DIAGSIG.SUCCESS:
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
		"""Looks at self.cfg, attempts to apply an interface theme using a
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
				filetypes = ("png", ), imgvarname = "IMG")
			stylehelper.load_theme(theme_path, theme_tuple[1])
		except TclError as error:
			tk_msg.showerror("Demomgr - error", "A tcl error occurred:\n"
				"{}".format(error))
		except (OSError, PermissionError, FileNotFoundError) as error:
			tk_msg.showerror("Demomgr - error", "The theme file was not found"
				"or a permission problem occurred:\n{}".format(error))

	def _updatedemowindow(self, _):
		"""Renew contents of demo information window"""
		index = self.listbox.getselectedcell()[1]
		self.demoinfbox.config(state = tk.NORMAL)
		self.demoinfbox.delete("0.0", tk.END)
		if _ == None:
			self.demoinfbox.insert(tk.END, "")
			self.demoinfbox.config(state = tk.DISABLED)
			return
		if not self.cfg["previewdemos"]:
			self.demoinfbox.insert(tk.END, "(Preview disabled)")
			self.demoinfbox.config(state = tk.DISABLED)
			return
		demname = "?"
		try:
			demname = self.listbox.getcell("col_filename", index) #Get headerinf
			outdict = readdemoheader(os.path.join(self.curdir, demname))
			headerinfo = ("Information for " + demname + ":\n\n" +
				"\n".join(["{} : {}".format(k, v) for k, v in outdict.items()]))
			del outdict # End headerinf
		except Exception:
			headerinfo = "Error reading demo; file is likely corrupted :("

		entry = self.listbox.getcell("col_demo_info", index) # Get info
		if entry == None:
			demmarks = "\n\nNo information on demo found."
		else:
			demmarks = "\n\n"
			for i in entry[0]:
				demmarks += (str(i[0]) + " streak at " + str(i[1]) + "\n")
			demmarks += "\n"
			for i in entry[1]:
				demmarks += ("\"" + str(i[0]) + "\" bookmark at " + str(i[1]) + "\n") # End info
		self.demoinfbox.insert(tk.END, headerinfo)
		self.demoinfbox.insert(tk.END, demmarks)
		
		self.demoinfbox.config(state = tk.DISABLED)

	def reloadgui(self):
		"""Should be called to re-fetch a directory's contents.
		This function starts the datafetcher thread.
		"""
		self.root.after_cancel(self.after_handlers["datafetcher"])
		self.listbox.clear()
		for k in self.threads:
			if self.threads[k].isAlive():
				self.threads[k].join()
		for k in self.queues:
			self.queues[k].queue.clear()
		self.threads["datafetcher"] = ThreadReadFolder(self.queues["datafetcher"],
			targetdir = self.curdir, cfg = self.cfg.copy())
		self.threads["datafetcher"].start()
		self.after_handlers["datafetcher"] = self.root.after(0,
			self._after_callback_fetchdata)
		self._updatedemowindow(None)

	@decorate_callback("datafetcher")
	def _after_callback_fetchdata(self):
		"""
		Loop worker for the after callback decorator stub.
		Grabs thread signals from the datafetcher queue and
		acts accordingly.
		"""
		queueobj = self.queues["datafetcher"].get_nowait()
		if queueobj[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queueobj[1])
		elif queueobj[0] < 0x100: # Finish
			return True
		elif queueobj[0] == THREADSIG.RESULT_DEMODATA:
			self.listbox.setdata(queueobj[1])
			self.listbox.format()
		return False

	def _cleanup(self):
		"""
		Starts a filtering thread and calls the cleanup after callback
		to open a Deleter dialog once the thread finishes.
		"""
		if self.filterentry_var.get() == "":
			return
		self.threads["cleanup"] = ThreadFilter(None, self.queues["cleanup"],
			filterstring = self.filterentry_var.get(), curdir = self.curdir,
			silent = True, cfg = self.cfg.copy())
		self.threads["cleanup"].start()
		self.cleanupbtn.config(text = "Cleanup by filter...", state = tk.DISABLED)
		self.after_handlers["cleanup"] = \
			self.root.after(0, self._after_callback_cleanup)

	@decorate_callback("cleanup")
	def _after_callback_cleanup(self):
		"""
		Loop worker for the after callback decorator stub.
		Grabs thread signals from the cleanup queue and acts
		accordingly, opening a Deletion dialog once the thread is done.
		"""
		queueobj = self.queues["cleanup"].get_nowait()
		if queueobj[0] < 0x100: # Finish
			self.cleanupbtn.config(
				text = "Cleanup by filter...", state = tk.NORMAL
			)
			return True
		elif queueobj[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queueobj[1])
		elif queueobj[0] == THREADSIG.RESULT_DEMODATA:
			del_diag = Deleter(
				parent = self.root,
				demodir = self.curdir,
				files = queueobj[1]["col_filename"],
				selected = [True for _ in queueobj[1]["col_filename"]],
				deluselessjson = False,
				cfg = self.cfg.copy(),
				styleobj = self.ttkstyle,
				eventfileupdate = "passive",
			)
			del_diag.show()
			self.cleanupbtn.config(
				text = "Cleanup by filter...", state = tk.NORMAL
			)
			# queues are cleared below, above is hacky workaround by copy pasting finish
			# which realistically will never be called if thread completes successfully.
			if del_diag.result == 0:
				self.reloadgui()
			return True
		return False

	def _filter(self):
		"""Starts a filtering thread and configures the filtering button."""
		if self.filterentry_var.get() == "":
			return
		self.filterbtn.config(text = "Stop Filtering",
			command = lambda: self._stopfilter(True))
		self.resetfilterbtn.config(state = tk.DISABLED)
		self.threads["filterer"] = ThreadFilter(None, self.queues["filter"],
			filterstring = self.filterentry_var.get(), curdir = self.curdir,
			silent = False, cfg = self.cfg.copy())
		self.threads["filterer"].start()
		self.after_handlers["filter"] = self.root.after(0,
			self._after_callback_filter)

	def _stopfilter(self, called_by_user = False):
		"""
		Stops the filtering thread by setting its stop flag, then blocking
		until it returns.
		"""
		self.threads["filterer"].join()
		self.queues["filter"].queue.clear()
		self.root.after_cancel(self.after_handlers["filter"])
		if called_by_user:
			self.setstatusbar("", 0)
		self.resetfilterbtn.config(state = tk.NORMAL)
		self.filterbtn.config(text = "Apply Filter", command = self._filter)
		self._updatedemowindow(None)

	@decorate_callback("filter")
	def _after_callback_filter(self):
		"""
		Loop worker for the after handler callback stub.
		Grabs elements from the filter queue and updates the statusbar with
		the filtering progress. If the thread is done, fills listbox with new
		dataset.
		"""
		queueobj = self.queues["filter"].get_nowait()
		if queueobj[0] < 0x100: # Finish
			finished = True
			self._stopfilter()
			return True
		elif queueobj[0] == THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*queueobj[1])
		elif queueobj[0] == THREADSIG.RESULT_DEMODATA:
			self.listbox.setdata(queueobj[1])
			self.listbox.format()
		return False

	def _spinboxsel(self, *_):
		"""
		Observer callback to self.spinboxvar; is called whenever
		self.spinboxvar (so the combobox) is updated.
		Also triggered by self._rempath.
		Kicks off the process of reading the current directory.
		"""
		selpath = self.spinboxvar.get()
		if selpath != self.curdir:
			if self.cfg["lastpath"] != selpath: #Update lastpath entry
				localcfg = self.cfg
				localcfg["lastpath"] = selpath
				self.writecfg(localcfg)
				self.cfg = self.getcfg()
			self.curdir = selpath
			self.reloadgui()

	def setstatusbar(self, data, timeout = None):
		"""Set statusbar text to data (str)."""
		self.statusbarlabel.after_cancel(self.after_handlers["statusbar"])
		self.statusbarlabel.config(text = str(data))
		self.statusbarlabel.update()
		if timeout is not None:
			self.after_handlers["statusbar"] = self.statusbarlabel.after(
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
			handleexists = False
			try:
				handle = open(self.cfgpath, "w")
				handleexists = True
				handle.write(json.dumps(data, indent = 4))
				if handleexists:
					handle.close()
				write_ok = True
			except Exception as error:
				if handleexists:
					handle.close()
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
			handleexists = False
			try:
				cfghandle = open(self.cfgpath, "r")
				handleexists = True
				localcfg.update(json.load(cfghandle))
				schema.Schema(CNST.DEFAULT_CFG_SCHEMA).validate(localcfg)
				cfg_ok = True
			except (json.decoder.JSONDecodeError, FileNotFoundError, OSError, SchemaError) as exc:
				if handleexists:
					cfghandle.close()
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = exc, mode = 0)
				dialog.show()
				if dialog.result.data == 0: # Retry
					pass
				elif dialog.result.data == 1: # Config replaced by dialog
					pass
				elif dialog.result.data == 2: # Quit
					self.quit_app()
					sys.exit()
			if handleexists:
				cfghandle.close()
		return localcfg
