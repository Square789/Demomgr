if __name__ == "__main__":
	raise RuntimeError("This script should not be executed directly, " \
		"but via demomgr.py from the parent directory.")

import sys
import os

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg
from _tkinter import TclError

import threading
import queue
import json
import time

from source import multiframe_list as mfl
from source.style_helper import StyleHelper
from source import context_menus

from source.helper_tk_widgets import TtkText

from source import constants as CNST
from source.helpers import (formatdate, readdemoheader, convertunit,
	formatbookmarkdata, format_bm_pair)

from source.dialogues import *
from source.threads import ThreadFilter, ThreadReadFolder

__version__ = "0.9.1"
__author__ = "Square789"

RCB = "3"

class MainApp():
	def __init__(self):
		'''Init values, variables, read config, go through startup routine,
		applies UI style, sets up interface, then show main window.
		'''
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
			("Manage bookmarks", " of selected demo...", self._managebookmarks), )

		self.cfgpath = os.path.join(os.getcwd(), CNST.CFG_FOLDER, CNST.CFG_NAME)
		self.curdir = "" # This path should not be in self.cfg["demopaths"] at any time!

		self.after_handlers = {
			"statusbar": self.root.after(0, lambda: True),
			"datafetcher": self.root.after(0, lambda: True),
			"filter": self.root.after(0, lambda: True),
			"cleanup:": self.root.after(0, lambda: True), }
		# Used to access output queues filled by threads
		self.threads = {
			"datafetcher": threading.Thread(target = lambda: True),
			"filterer": threading.Thread(target = lambda: True),
			"cleanup": threading.Thread(target = lambda: True), } # Dummies
		self.queues = {
			"datafetcher": queue.Queue(),
			"filter": queue.Queue(),
			"cleanup": queue.Queue(), }

		self.spinboxvar = tk.StringVar()

		# Startup routine
		# NOTE : Merge into _init_() maybe.
		startupres = self._startup() # loads self.cfg

		#load style (For FirstRun)
		self.ttkstyle = ttk.Style() # Used later-on too.
		self._DEFAULT_THEME = self.ttkstyle.theme_use()
		#Fallback that is different depending on the platform.
		self._applytheme()

		if startupres["res"] == -1:
			tk_msg.showerror("Demomgr - Error", "The following error" \
				" occurred during startup: " + startupres["msg"])
			sys.exit()
		elif startupres["res"] == 1:
			d = FirstRun(self.root)
			if not d.result: # Is either None; 1 or 0
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

	def _startup(self):
		'''Will go through a startup routine, then return a value whether startup was successful, this is first launch etc.'''
		if os.path.exists(self.cfgpath):
			self.cfg = self.getcfg()
			if self.cfg["firstrun"]:
				return {"res":1, "msg":"Firstlaunch"}
		else:
			try:
				os.makedirs(CNST.CFG_FOLDER, exist_ok = True)
				self.writecfg(CNST.DEFAULT_CFG)
				self.cfg = CNST.DEFAULT_CFG
			except Exception as exception:
				return {"res":-1, "msg":str(exception)}
			return {"res":1, "msg":"Firstlaunch"}
		return {"res":0, "msg":"Success."}

	def _setupgui(self):
		'''Sets up UI inside of the self.mainframe widget.'''
		self.filterentry_var = tk.StringVar()

		widgetframe0 = ttk.Frame(self.mainframe) #Directory Selection, Settings/About #NOTE: Resquash into tkinter.Menu ?
		widgetframe1 = ttk.Frame(self.mainframe) #Filtering / Cleanup by filter
		widgetframe2 = ttk.Frame(self.mainframe) #Buttons here interact with the currently selected demo
		self.listboxframe = ttk.Frame(self.mainframe)
		demoinfframe = ttk.Frame(self.mainframe, padding = (5, 5, 5, 5))
		self.statusbar = ttk.Frame(self.mainframe, padding = (1, 2, 1, 1),
			style = "Statusbar.TFrame" )

		self.listbox = mfl.MultiframeList(self.listboxframe, inicolumns = (
			{"name":"Filename", "col_id":"col_filename", "sort":True,
				"weight": 5, "minsize": 100, "w_width": 20},
			{"name":"Bookmarks", "col_id":"col_bookmark", "sort":False,
				"minsize":26, "weight":1, "w_width":26,
				"formatter":format_bm_pair, },
			{"name":"Date created", "col_id":"col_ctime", "sort":True,
				"minsize":19, "weight":1, "w_width":19,
				"formatter":formatdate, },
			{"name":"Filesize", "col_id":"col_filesize", "sort":True,
				"minsize":10, "weight":1, "w_width":10,
				"formatter":convertunit, }, ), rightclickbtn = self.RCB )

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
		# Without the try/except below, the root.destroy method will produce
		# an error on closing, due to some dark magic regarding after
		# commands in self.setstatusbar().
		# Safe destroy probably better/cleaner than self.root.quit()
		try: self.root.destroy()
		except TclError: pass


	def _opensettings(self):
		'''Opens settings, acts based on results'''
		dialog = Settings(self.mainframe, self.getcfg())
		if dialog.result is not None:
			localcfg = self.cfg
			localcfg.update(dialog.result)
			self.writecfg(localcfg)
			self.cfg = self.getcfg()
			self.reloadgui()
			self._applytheme()

	def _playdem(self):
		'''Opens dialog which arranges for tf2 launch.'''
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.getcell("col_filename", index)
		path = os.path.join(self.curdir, filename)
		dialog = LaunchTF2(self.mainframe, demopath = path,
			cfg = self.cfg)
		if dialog.result is not None:
			if "steampath" in dialog.result:
				if dialog.result["steampath"] != self.cfg["steampath"]:
					self.cfg["steampath"] = dialog.result["steampath"]
					self.writecfg(self.cfg)
					self.cfg = self.getcfg()

	def _deldem(self):
		'''Deletes the currently selected demo.'''
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.getcell("col_filename", index)
		dialog = Deleter(self.root, demodir = self.curdir, files = [filename],
			selected = [True], deluselessjson = False, cfg = self.cfg,
			styleobj = self.ttkstyle)
		if dialog.result["state"] != 0:
			if self.cfg["lazyreload"]:
				self.listbox.removerow(index)
				self._updatedemowindow(None)
			else:
				self.reloadgui()

	def _managebookmarks(self):
		'''Offers dialog to manage a demo's bookmarks.'''
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.getcell("col_filename", index)
		demo_bm = self.listbox.getcell("col_bookmark", index)
		path = os.path.join(self.curdir, filename)
		dialog = BookmarkSetter(self.root, targetdemo = path,
			bm_dat = demo_bm, styleobj = self.ttkstyle)
		if dialog.result == 1:
			ksdata = self.listbox.getcell("col_bookmark", index)[0]
			new_bmdata = (ksdata, list(dialog.new_bm))
			if self.cfg["lazyreload"]:
				self.listbox.setcell("col_bookmark", index, new_bmdata)
				self.listbox.format(("col_bookmark", ), (index, ))
				self._updatedemowindow(None)
			else:
				self.reloadgui()

	def _applytheme(self):
		'''Looks at self.cfg, attempts to apply an interface theme using a
		StyleHelper.
		'''
		if self.cfg["ui_theme"] == "_DEFAULT":
			self.root.tk.call("ttk::setTheme", self._DEFAULT_THEME)
			return
		theme_subdir = CNST.THEME_SUBDIR
		try:
			theme_tuple = CNST.THEME_PACKAGES[self.cfg["ui_theme"]]
			pathappendix = os.path.join(theme_subdir, theme_tuple[0])
		except (KeyError):
			tk_msg.showerror("Demomgr - error", "Cannot load theme, interface "
				"will look butchered.")
			return
		try:
			stylehelper = StyleHelper(self.root)
			imgdir = os.path.join(theme_subdir, theme_tuple[2])
			stylehelper.load_image_dir(imagedir = imgdir,
				filetypes = ("png", ), imgvarname = "IMG")
			stylehelper.load_theme(os.path.join(os.getcwd(), pathappendix),
				theme_tuple[1])
		except TclError as error:
			tk_msg.showerror("Demomgr - error", "A tcl error occurred:\n"
				"{}".format(error))
		except (OSError, PermissionError, FileNotFoundError) as error:
			tk_msg.showerror("Demomgr - error", "The theme file was not found"
				"or a permission problem occurred:\n{}".format(error))

	def _updatedemowindow(self, _):
		'''Renew contents of demo information window'''
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

		entry = self.listbox.getcell("col_bookmark", index) # Get bookmarks
		if entry == None:
			demmarks = "\n\nNo bookmark container found."
		else:
			demmarks = "\n\n"
			for i in entry[0]:
				demmarks += (str(i[0]) + " streak at " + str(i[1]) + "\n")
			demmarks += "\n"
			for i in entry[1]:
				demmarks += ("\"" + str(i[0]) + "\" bookmark at " + str(i[1]) + "\n")#End bookmarks
		self.demoinfbox.insert(tk.END, headerinfo)
		self.demoinfbox.insert(tk.END, demmarks)
		
		self.demoinfbox.config(state = tk.DISABLED)

	def reloadgui(self):
		'''Should be called to re-fetch a directory's contents.
		This function starts the datafetcher thread.
		'''
		self.root.after_cancel(self.after_handlers["datafetcher"])
		self.listbox.clear()
		for k in self.threads:
			if self.threads[k].isAlive():
				self.threads[k].join()
		for k in self.queues:
			self.queues[k].queue.clear()
		self.threads["datafetcher"] = ThreadReadFolder(None,
			self.queues["datafetcher"], {"curdir":self.curdir,
			"cfg":self.cfg.copy(), })
		self.threads["datafetcher"].start()
		self.after_handlers["datafetcher"] = self.root.after(0,
			self._after_callback_fetchdata)
		self._updatedemowindow(None)

	def _after_callback_fetchdata(self):
		'''A code snippet that grabs elements from the datafetcher queue and
		configures the UI based on what is returned. This method is supposed
		to be run as a Tk after function and will call itself until the thread
		has sent a termination signal.
		'''
		finished = False
		while True:
			try:
				queueobj = self.queues["datafetcher"].get_nowait()
				if queueobj[0] == "SetStatusbar":
					self.setstatusbar(*queueobj[1])
				elif queueobj[0] == "Finish":
					finished = True
				elif queueobj[0] == "Result":
					self.listbox.setdata(queueobj[1])
					self.listbox.format()
			except queue.Empty:
				break
		if not finished:
			self.after_handlers["datafetcher"] = self.root.after(
				CNST.GUI_UPDATE_WAIT, self._after_callback_fetchdata)
		else:
			self.root.after_cancel(self.after_handlers["datafetcher"])

	def _cleanup(self):
		'''
		Starts a filtering thread and calls the cleanup after handler to open
		a Deleter dialog once the thread finishes.
		'''
		if self.filterentry_var.get() == "":
			return
		self.threads["cleanup"] = ThreadFilter(None, self.queues["cleanup"],
			filterstring = self.filterentry_var.get(), curdir = self.curdir,
			silent = True, cfg = self.cfg.copy())
		self.threads["cleanup"].start()
		self.cleanupbtn.config(text = "Cleanup by filter...", state = tk.DISABLED)
		self.after_handlers["cleanup"] = \
			self.root.after(0, self._after_callback_cleanup)

	def _after_callback_cleanup(self):
		finished = False
		while True:
			try:
				queueobj = self.queues["cleanup"].get_nowait()
				if queueobj[0] == "Finish":
					finished = True
				elif queueobj[0] == "SetStatusbar":
					self.setstatusbar(*queueobj[1])
				elif queueobj[0] == "Result":
					del_diag = Deleter(
						parent = self.root,
						demodir = self.curdir,
						files = queueobj[1]["col_filename"],
						selected = [True for _ in queueobj[1]["col_filename"]],
						deluselessjson = False,
						cfg = self.cfg.copy(),
						styleobj = self.ttkstyle,
						eventfileupdate = "selectivemove",
					)
					if del_diag.result["state"] == 1:
						self.reloadgui()
			except queue.Empty:
				break
		if not finished:
			self.after_handlers["cleanup"] = self.root.after(
				CNST.GUI_UPDATE_WAIT, self._after_callback_cleanup)
		else:
			self.cleanupbtn.config(text = "Cleanup by filter...", state = tk.NORMAL)

	def _filter(self):
		'''Starts a filtering thread and configures the filtering button.'''
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
		'''Stops the filtering thread by setting its stop flag, then blocking
		until it returns.
		'''
		self.threads["filterer"].join()
		self.queues["filter"].queue.clear()
		self.root.after_cancel(self.after_handlers["filter"])
		if called_by_user:
			self.setstatusbar("", 0)
		self.resetfilterbtn.config(state = tk.NORMAL)
		self.filterbtn.config(text = "Apply Filter", command = self._filter)
		self._updatedemowindow(None)

	def _after_callback_filter(self):
		'''Grabs elements from the filter queue and updates the statusbar with
		the filtering progress. This method is supposed to be run as a Tk after
		function and will call itself until the thread has sent a termination
		signal.
		'''
		finished = False
		while True:
			try:
				queueobj = self.queues["filter"].get_nowait()
				if queueobj[0] == "Finish":
					finished = True
				elif queueobj[0] == "SetStatusbar":
					self.setstatusbar(*queueobj[1])
				elif queueobj[0] == "Result":
					self.listbox.setdata(queueobj[1])
					self.listbox.format()
			except queue.Empty:
				break
		if not finished:
			self.after_handlers["filter"] = self.root.after(
				CNST.GUI_UPDATE_WAIT, self._after_callback_filter)
		else:
			self._stopfilter()

	def _spinboxsel(self, *_):
		'''Observer callback to self.spinboxvar; is called whenever
		self.spinboxvar (so the combobox) is updated.
		Also triggered by self._rempath.
		Kicks off the process of reading the current directory.
		'''
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
		'''Set statusbar text to data (str).'''
		self.statusbarlabel.after_cancel(self.after_handlers["statusbar"])
		self.statusbarlabel.config(text = str(data))
		self.statusbarlabel.update()
		if timeout != None:
			self.after_handlers["statusbar"] = self.statusbarlabel.after(
				timeout, lambda: self.setstatusbar(CNST.STATUSBARDEFAULT) )

	def _addpath(self):
		'''Offers a directory selection dialog and writes the selected
		directory path to config after validating.
		'''
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
		'''Removes the current directory from the registered directories,
		automatically moves to another one or sets the current directory
		to "" if none are available anymore.
		'''
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
		'''Writes config dict specified in data to self.cfgpath, converted
		to JSON. On write error, calls the CfgError dialog, blocking until
		the issue is fixed.
		'''
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
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = error, mode =  1)
				if dialog.result_ == 0: # Retry
					pass
				elif dialog.result_ == 1: # Config replaced by dialog
					pass
				elif dialog.result_ == 2: # Quit
					self.quit_app()
					sys.exit()

	def getcfg(self):
		'''Gets config from self.cfgpath and returns it. On error, blocks until
		program is closed, config is replaced or fixed.
		'''
		localcfg = CNST.DEFAULT_CFG.copy()
		cfg_ok = False
		while not cfg_ok:
			handleexists = False
			try:
				cfghandle = open(self.cfgpath, "r")
				handleexists = True
				localcfg.update(json.load(cfghandle))
				#TODO: REFURBISH, demopaths is hardcoded badly.
				for k in CNST.DEFAULT_CFG_TYPES:
					if k == "demopaths":
						if not all( (isinstance(i, str) for i in localcfg[k]) ):
							raise ValueError("Bad config type: Non-String type in demopaths")
						if "" in localcfg[k]:
							raise ValueError("Unallowed directory: \"\" in demopaths")
					if not CNST.DEFAULT_CFG_TYPES[k] == type(localcfg[k]):
						raise ValueError("Bad config type: {} is not of type \"{}\"".format(localcfg[k]._repr_(), CNST.DEFAULT_CFG_TYPES[k]._name_))
				cfg_ok = True
			except (json.decoder.JSONDecodeError, FileNotFoundError, ValueError, OSError) as error:
				if handleexists:
					cfghandle.close()
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = error, mode = 0)
				if dialog.result_ == 0: # Retry
					pass
				elif dialog.result_ == 1: # Config replaced by dialog
					pass
				elif dialog.result_ == 2: # Quit
					self.quit_app()
					sys.exit()
			if handleexists:
				cfghandle.close()
		return localcfg
