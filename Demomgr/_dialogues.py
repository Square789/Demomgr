import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg
from helper_tk_widgets import TtkText

import json
import os
import queue
import subprocess
import threading

import handle_events as handle_ev
import multiframe_list as mfl

from _filterlogic import filterstr_to_lambdas
from _helpers import (assignbookmarkdata, formatdate, convertunit,
	formatbookmarkdata, HeaderFetcher, FileStatFetcher, readdemoheader,
	frmd_label)
from _threads import ThreadFilter, ThreadDeleter
import _constants as _DEF

class _BaseDialog(tk.Toplevel):
	'''A base dialog that serves as ground for all other dialogs in the
	program. Override self.body(), call self.cancel() or
	self.destroy() for closing the dialog. The self.result attribute will stay
	after the dialogue has closed and given control back to the parent window.

	Code "borrowed" from tk.simpledialog.Dialog, overrides the 5px
	border that is unstylable.
	'''
	def __init__(self, parent, title = None):
		super().__init__(parent, bg = "#000000")

		self.result = None
		self.withdraw()
		if parent.winfo_viewable():
			self.transient(parent)

		if title != None:
			self.title(title)

		self.parent = parent
		rootframe = ttk.Frame(self, padding = (5, 5, 5, 5))
		rootframe.pack(expand = 1, fill = tk.BOTH)
		mainframe = ttk.Frame(rootframe)
		self.body(mainframe)
		mainframe.pack(expand = 1, fill = tk.BOTH)

		self.protocol("WM_DELETE_WINDOW", self.cancel)

		if self.parent is not None:
			self.geometry("+{}+{}".format(parent.winfo_rootx() + 50,
				parent.winfo_rooty() + 50))
		self.deiconify()

		self.wait_visibility()
		self.grab_set()
		self.wait_window(self)

	def body(self, master):
		'''Override this'''
		pass

	def cancel(self):
		self.destroy()

	def destroy(self):
		super().destroy()

"""class BookmarkSetter(_BaseDialog): #TODO: Work on this.
	'''Dialog that writes a bookmark into a demo's json file or _events.txt
	entry.
	'''
	def __init__(self, parent, targetdemo = None):
		'''Args: parent tkinter window, keyword args targetdemo:

		targetdemo: Full path to the demo that should be marked.
		'''
		self.targetdemo = options["targetdemo"]
		
		self.jsonmark_var = tk.BooleanVar()
		self.eventsmark_var = tk.BooleanVar()
		super().__init__(parent, "Insert bookmark...")

	def body(self, parent):
		'''UI'''
		def numchecker(inp):
			try:
				int(inp)
			except ValueError:
				return False
			if len(inp) > 60:
				return False
			return True

		marksel_labelframe = ttk.LabelFrame(parent, text = "Mark demo in:")
		jsonsel_checkbox = ttk.Checkbutton(marksel_labelframe,
			text = "json file", variable = self.jsonmark_var)
		eventssel_checkbox = ttk.Checkbutton(marksel_labelframe,
			text = "_events file", variable = self.eventsmark_var)

		tickinp_frame = ttk.Frame(marksel_labelframe)
		ttk.Label(tickinp_frame, text = "Mark at: ").pack(side = tk.LEFT)
		tick_entry = ttk.Entry(tickinp_frame, validate = "key",
			validatecommand = (parent.register(numchecker), "%S"))

		markbtn = ttk.Button(parent, text = "Mark!")
		cancelbtn = ttk.Button(parent, text = "Cancel", command = self.cancel)

		jsonsel_checkbox.pack()
		eventssel_checkbox.pack()
		marksel_labelframe.pack(expand = 1, fill = tk.BOTH)

		tick_entry.pack(side = tk.LEFT)
		tickinp_frame.pack()

		markbtn.pack(fill = tk.X, side = tk.LEFT, padx = (0, 3))
		cancelbtn.pack(fill = tk.X, side = tk.LEFT, padx = (3, 0))

	def __mark(self):#NOTE: Probably multithread, idk it's not like this'll take eons
		markJson, markEvts = self.jsonmark_var.get(), self.eventsmark_var.get()
		if markJson:
			pass
		if markEvts:
			pass

		self.cancel()
"""

class CfgError(_BaseDialog):
	'''Dialog that opens on malformed config and offers three options:
	Retry, Replace, Quit.
	Takes:
	tkinter parent element
	cfgpath <str>
	error string <str>
	mode <int>: 0 for read access error, 1 for write error'''
	def __init__(self, parent, cfgpath, error, mode):
		self.result_ = None
		self.cfgpath = cfgpath
		self.error = error
		self.mode = mode #0: Read; 1: Write
		super().__init__(parent, "Configuration error!")

	def body(self, parent):
		'''UI'''
		ifread = abs(self.mode - 1)
		msg = (	"The configuration file could not be " +
			("read from" * ifread + "written to" * self.mode) +
			", meaning it was " + ("either corrupted, deleted, " * ifread) +
			"made inaccessible" + (" or has bad values" * ifread) +
			".\nDemomgr can not continue but you can select from the options "
			"below.\n\nRetry: Try performing the action again\nReplace: Write "
			"the default config to the config path, then retry.\nQuit: Quit Demomgr" +
			"\n\n{}: {}".format(self.error.__class__.__name__, str(self.error)) )
		slickframe = ttk.Frame(parent, relief = tk.SUNKEN, border = 5,
			style = "Contained.TFrame")
		msg_label = ttk.Label(slickframe, font = ("TkDefaultFont", 10),
			wrap = 400, text = msg, style = "Contained.TLabel")
		self.inf_updating = ttk.Label(slickframe,
			font = ("TkDefaultFont", 10), wrap = 400, style = "Contained.TLabel",
			text = "Attempting to rewrite default config...")
		self.err_rewrite_fail = ttk.Label(slickframe,
			font = ("TkDefaultFont", 10), wrap = 400, style = "Contained.TLabel")
		retrybtn = ttk.Button(parent, text = "Retry", command = self.__retry)
		replbtn = ttk.Button(parent, text = "Replace", command = self.__replacecfg)
		quitbtn = ttk.Button(parent, text = "Quit", command = self.__quit)

		slickframe.pack(expand = 1, fill = tk.BOTH)
		msg_label.pack(side = tk.TOP, expand = 1, fill = tk.BOTH)
		retrybtn.pack(fill = tk.X, side = tk.LEFT, expand = 1, padx = (0, 3))
		replbtn.pack(fill = tk.X, side = tk.LEFT, expand = 1, padx = 3)
		quitbtn.pack(fill = tk.X, side = tk.LEFT, expand = 1, padx = (3, 0))

	def cancel(self):
		self.__quit()

	def __retry(self):
		self.result_ = 0
		self.destroy()

	def __replacecfg(self):
		cfgtowrite = _DEF.DEFAULT_CFG
		try:
			self.err_rewrite_fail.pack_forget()
			self.inf_updating.pack(side = tk.TOP, expand = 1, fill = tk.BOTH)
			os.makedirs(_DEF.CFG_FOLDER, exist_ok = True)
			handle = open(self.cfgpath, "w")
			handle.write(json.dumps(cfgtowrite, indent = 4))
			handle.close()
			self.cfg = _DEF.DEFAULT_CFG
		except Exception as exception:
			self.inf_updating.pack_forget()
			self.err_rewrite_fail.config(text = "Rewrite failed: {}".format(
				str(exception)) )
			self.err_rewrite_fail.pack(side = tk.TOP, expand = 1,
				fill = tk.BOTH)
			return
		self.result_ = 1
		self.destroy()

	def __quit(self):
		self.result_ = 2
		self.destroy()

class Cleanup(_BaseDialog): #TODO: Add thread
	def __init__(self, parent, options):
		'''Args: parent tkinter window, options dict with:
		bookmarkdata, files, dates, filesizes, curdir, cfg, styleobj'''
		self.master = parent

		self.bookmarkdata = options["bookmarkdata"]
		self.files = options["files"]
		self.dates = options["dates"]
		self.filesizes = options["filesizes"]
		self.curdir = options["curdir"]
		self.cfg = options["cfg"]
		self.styleobj = options["styleobj"]

		self.bookmarkdata = assignbookmarkdata(self.files, self.bookmarkdata)

		self.symbollambda = lambda x: " X" if x else ""

		self.keepevents_var = tk.BooleanVar()
		self.deluselessjson_var = tk.BooleanVar()
		self.selall_var = tk.BooleanVar()
		self.filterbox_var = tk.StringVar()

		self.result_ = {"state":0}

		super().__init__(parent, "Cleanup...")

	def body(self, master):
		'''UI'''
		master.bind("<<MultiframeSelect>>", self.__procentry)

		okbutton = ttk.Button(master, text = "Delete",
			command = lambda: self.done(1) )
		cancelbutton = ttk.Button(master, text= "Cancel",
			command = lambda: self.done(0) )

		self.listbox = mfl.MultiframeList(master, inicolumns = (
			{"name":"", "col_id":"col_sel", "width":2,
				"formatter": self.symbollambda},
			{"name":"Filename", "col_id":"col_filename", "sort":True, },
			{"name":"Bookmarks", "col_id":"col_bookmark", "width":26, },
			{"name":"Date created", "col_id":"col_ctime", "width":19,
				"formatter":formatdate, "sort":True, },
			{"name":"Filesize", "col_id":"col_filesize",  "width":10,
				"formatter":convertunit, "sort":True, }, ),
			ttkhook = True )
		self.listbox.setdata({
			"col_sel":[False for _ in self.files],
			"col_filename":self.files,
			"col_ctime":self.dates,
			"col_bookmark":formatbookmarkdata(self.files, self.bookmarkdata),
			"col_filesize":self.filesizes, })
		self.listbox.format()

		self.demoinflabel = ttk.Label(master, text = "", justify = tk.LEFT,
			anchor = tk.W, font = ("Consolas", 8) )

		#NOTE: looks icky
		self.listbox.frames[0][2].pack_propagate(False)
		selall_checkbtn = ttk.Checkbutton(self.listbox.frames[0][2],
			variable = self.selall_var, text = "", command = self.selall)

		optframe = ttk.LabelFrame(master, padding = (3, 8, 3, 8),
			labelwidget = frmd_label(master, "Options") )
		keepevents_checkbtn = ttk.Checkbutton(optframe,
			variable = self.keepevents_var, text = "Make backup of " +
			_DEF.EVENT_FILE, style = "Contained.TCheckbutton")
		deljson_checkbtn = ttk.Checkbutton(optframe,
			variable = self.deluselessjson_var, text = "Delete orphaned "
			"json files", style = "Contained.TCheckbutton")

		condframe = ttk.LabelFrame(master, padding = (3, 8),
			labelwidget = frmd_label(master, "Demo selector / Filterer"))
		self.filterbox = ttk.Entry(condframe, textvariable = self.filterbox_var)
		self.applybtn = ttk.Button(condframe, text = "Apply filter",
			command = self.__applycond, style = "Contained.TButton")

		self.applybtn.pack(side = tk.RIGHT)
		self.filterbox.pack(side = tk.RIGHT, fill = tk.X, expand = 1, padx = (0, 5))
		condframe.pack(fill = tk.BOTH, pady = (4, 5))

		deljson_checkbtn.pack(side = tk.LEFT, ipadx = 2, padx = 4)
		keepevents_checkbtn.pack(side = tk.LEFT, ipadx = 2, padx = 4)
		optframe.pack(fill = tk.BOTH, pady = 5)

		selall_checkbtn.pack(side = tk.LEFT, anchor = tk.W)
		self.listbox.pack(side = tk.TOP, fill = tk.BOTH, expand = 1)
		self.demoinflabel.pack(side = tk.TOP, fill = tk.BOTH, expand = 0, anchor = tk.W)

		okbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		cancelbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (3, 0))

	def __setinfolabel(self, content):
			self.demoinflabel.config(text = content)

	def __procentry(self, event):
		index = self.listbox.getselectedcell()[1]
		if self.cfg["previewdemos"]:
			try:
				hdr = readdemoheader(os.path.join(self.curdir,
					self.listbox.getcell("col_filename", index)) )
			except Exception:
				hdr = _DEF.FALLBACK_HEADER
			self.__setinfolabel("Host: {}| ClientID: {}| Map: {}".format(
				hdr["hostname"], hdr["clientid"], hdr["map_name"]))

		if self.listbox.getselectedcell()[0] != 0: return
		if index == None: return
		self.listbox.setcell("col_sel", index,
			(not self.listbox.getcell("col_sel", index)))
		if False in self.listbox.getcolumn("col_sel"):
			self.selall_var.set(0)
		else:
			self.selall_var.set(1)

	def __setitem(self, index, value, lazyui = False): #value: bool
		self.listbox.setcell("col_sel", index, value)
		if not lazyui:
			if False in self.listbox.getcolumn("col_sel"): #~ laggy
				self.selall_var.set(0)
			else:
				self.selall_var.set(1)
			# Do not refresh ui. This is done while looping over the elements,
			# then a final refresh is performed.

	def __applycond(self):
		'''Apply user-entered condition to the files. This blocks the
		UI, as I cannot be bothered to do it otherwise tbf.'''
		filterstr = self.filterbox_var.get()
		if filterstr == "":
			return
		self.__setinfolabel("Parsing filter conditions...")
		try:
			filters = filterstr_to_lambdas(filterstr)
		except Exception as error:
			self.__setinfolabel("Error parsing filter: " + str(error))
			return
		self.__setinfolabel("Applying filters, please hold on...")
		for i, j in enumerate(self.files):
			curfile = {"name":j, "killstreaks":self.bookmarkdata[i][1],
				"bookmarks":self.bookmarkdata[i][2],
				"header": HeaderFetcher(os.path.join(self.curdir, j)),
				"filedata": FileStatFetcher(os.path.join(self.curdir, j))}
			curdemook = True
			for f in filters:
				if not f(curfile):
					curdemook = False
					break
			if curdemook:
				self.__setitem(i, True, True)
			else:
				self.__setitem(i, False, True)
		if len(self.listbox.getcolumn("col_sel")) != 0: #set sel_all checkbox
			self.__setitem(0, self.listbox.getcell("col_sel", 0), False)
		self.__setinfolabel("Done.")

	def selall(self):
		if False in self.listbox.getcolumn("col_sel"):
			self.listbox.setcolumn("col_sel", [True for _ in self.files])
		else:
			self.listbox.setcolumn("col_sel", [False for _ in self.files])
		self.listbox.format(["col_sel"])

	def done(self, param):
		if param:
			dialog_ = Deleter(self.master, {"cfg":self.cfg,
				"files":self.listbox.getcolumn("col_filename"),
				"demodir":self.curdir,
				"selected":self.listbox.getcolumn("col_sel"),
				"keepeventsfile":self.keepevents_var.get(),
				"deluselessjson":self.deluselessjson_var.get(),
				"eventfileupdate":"selectivemove", "styleobj":self.styleobj} )
			self.grab_set() #NOTE: This is quite important.
			if dialog_.result_["state"] != 0:
				self.result_["state"] = 1
				self.destroy()
		else:
			self.destroy()

class Deleter(_BaseDialog):
	def __init__(self, parent, options):
		'''Args: parent tkinter window, options dict with:
		demodir, files, selected, keepeventsfile, deluselessjson
		cfg, styleobj, (eventfileupdate)
		len(files) = len(selected); selected[x] = True/False;
		file[n] will be deleted if selected[n] == True'''
		self.master = parent
		self.demodir = options["demodir"]
		self.files = options["files"]
		self.selected = options["selected"]
		self.keepeventsfile = options["keepeventsfile"]
		self.deluselessjson = options["deluselessjson"]
		self.cfg = options["cfg"]
		self.styleobj = options["styleobj"]

		if "eventfileupdate" in options:
			self.eventfileupdate = options["eventfileupdate"]
		else:
			self.eventfileupdate = "passive"

		self.filestodel = [j for i, j in enumerate(self.files) if self.selected[i]]

		self.startmsg = "This operation will delete the following file(s):\n\n" + "\n".join(self.filestodel)

		try: #Try block should only catch from the os.listdir call directly below.
			jsonfiles = [i for i in os.listdir(self.demodir) if os.path.splitext(i)[1] == ".json"]
			choppedfilestodel = [os.path.splitext(i)[0] for i in self.filestodel] #add json files to self.todel if their demo files are in todel
			choppedfiles = None

			for i, j in enumerate(jsonfiles):
				if os.path.splitext(j)[0] in choppedfilestodel:
					self.filestodel.append(jsonfiles[i])
			if self.deluselessjson: #also delete orphaned files
				choppedfilestodel = None
				choppedfiles = [os.path.splitext(i)[0] for i in self.files]
				for i, j in enumerate(jsonfiles):
					if not os.path.splitext(j)[0] in choppedfiles:
						self.filestodel.append(jsonfiles[i])
			del jsonfiles, choppedfilestodel, choppedfiles
			self.startmsg = "This operation will delete the following file(s):\n\n" + "\n".join(self.filestodel)
		except (OSError, PermissionError, FileNotFoundError) as error:
			self.startmsg = "! Error getting JSON files: !\n{}{}\n\n{}".format(error.__class__.__name__, str(error), self.startmsg)

		self.delthread = threading.Thread() #Dummy thread in case self.cancel is called through window manager
		self.after_handler = None
		self.queue_out = queue.Queue()

		self.result_ = {"state":0} #exit state. set to 1 if successful

		super().__init__(parent, "Delete...")

	def body(self, master):
		'''UI'''
		self.okbutton = ttk.Button(master, text = "Delete!", command = lambda: self.confirm(1) )
		self.cancelbutton = ttk.Button(master, text = "Cancel", command = self.destroy )
		self.closebutton = ttk.Button(master, text = "Close", command = self.destroy )
		self.canceloperationbutton = ttk.Button(master, text = "Abort", command = self.__stopoperation)
		textframe = ttk.Frame(master, padding = (5, 5, 5, 5))
		textframe.grid_columnconfigure(0, weight = 1)
		textframe.grid_rowconfigure(0, weight = 1)

		self.textbox = TtkText(textframe, self.styleobj, wrap = tk.NONE, width = 40, height = 20)
		self.vbar = ttk.Scrollbar(textframe, orient = tk.VERTICAL, command = self.textbox.yview)
		self.vbar.grid(column = 1, row = 0, sticky = "ns")
		self.hbar = ttk.Scrollbar(textframe, orient = tk.HORIZONTAL, command = self.textbox.xview)
		self.hbar.grid(column = 0, row = 1, sticky = "ew")
		self.textbox.config(xscrollcommand = self.hbar.set, yscrollcommand = self.vbar.set)
		self.textbox.grid(column = 0, row = 0, sticky = "news", padx = (0, 3), pady = (0, 3))

		self.textbox.delete("0.0", tk.END)
		self.textbox.insert(tk.END, self.startmsg)
		self.textbox.config(state = tk.DISABLED)

		textframe.pack(fill = tk.BOTH, expand = 1)

		self.okbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		self.cancelbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (3, 0))

	def confirm(self, param):
		if param == 1:
			self.okbutton.pack_forget()
			self.cancelbutton.pack_forget()
			self.canceloperationbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)
			self.__startthread()

	def __stopoperation(self):
		if self.delthread.isAlive():
			self.delthread.join()

	def __startthread(self):
		self.delthread = ThreadDeleter(None, self.queue_out, {
			"keepeventsfile":	self.keepeventsfile,
			"demodir":			self.demodir,
			"files":			self.files,
			"selected":			self.selected,
			"filestodel":		self.filestodel,
			"cfg":				self.cfg,
			"eventfileupdate":	self.eventfileupdate} )
		self.delthread.start()
		self.after_handler = self.after(0, self.__after_callback)

	def __after_callback(self):
		'''Gets stuff from self.queue_out that the thread writes to, then
		modifies UI based on queue elements.
		'''
		finished = [False, 0]
		while True:
			try:
				procelem = self.queue_out.get_nowait()
				if procelem[0] == "ConsoleInfo":
					self.appendtextbox(procelem[1])
				elif procelem[0] == "Finish":
					finished = [True, procelem[1]]
			except queue.Empty:
				break
		if not finished[0]:
			self.after_handler = self.after(_DEF.GUI_UPDATE_WAIT,
				self.__after_callback)
			return
		else: #THREAD DONE
			self.after_cancel(self.after_handler)
			self.result_["state"] = finished[1]
			self.canceloperationbutton.pack_forget()
			self.closebutton.pack(side = tk.LEFT, fill = tk.X, expand = 1)

	def appendtextbox(self, _inp):
		self.textbox.config(state = tk.NORMAL)
		self.textbox.insert(tk.END, str(_inp) )
		self.textbox.yview_moveto(1.0)
		self.textbox.update()
		self.textbox.config(state = tk.DISABLED)

	def cancel(self):
		self.__stopoperation()
		self.destroy()

class FirstRunDialog(_BaseDialog):
	'''Will open up when no config file is found on startup, prompts
	user to accept a text.'''
	def __init__(self, parent = None):
		if not parent:
			parent = tk._default_root
		super().__init__(parent, "Welcome!")

	def body(self, master):
		'''UI'''
		master.columnconfigure(0, weight = 1)
		master.columnconfigure(1, weight = 1)
		master.columnconfigure(2, weight = 0)
		master.rowconfigure(0, weight = 1)

		scrlbar = ttk.Scrollbar(master, orient = tk.VERTICAL)
		txtbox = TtkText(master, ttk.Style(), wrap = tk.WORD,
			yscrollcommand = scrlbar.set)
		scrlbar.config(command = txtbox.yview)
		txtbox.insert(tk.END, _DEF.WELCOME)
		txtbox.config(state = tk.DISABLED)
		txtbox.grid(column = 0, row = 0, columnspan = 2, sticky = "news")
		scrlbar.grid(column = 2, row = 0, sticky = "sn")

		btconfirm = ttk.Button(master, text = "I am okay with that and I"
			" accept.", command = lambda: self.done(1))
		btcancel = ttk.Button(master, text = "Cancel!",
			command = lambda: self.done(0))
		btconfirm.grid(column = 0, row = 1, padx = (0, 3), sticky = "ew")
		btcancel.grid(column = 1, row = 1, padx = (3, 0), sticky = "ew")

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		self.result = param
		self.destroy()

class LaunchTF2(_BaseDialog):
	def __init__(self, parent, options):
		'''Args: parent tkinter window, options dict with:
			demopath (Absolute file path to the demo to be played),
			steamdir
		'''
		self.result_ = {}

		self.parent = parent

		self.demopath = options["demopath"]
		self.steamdir = tk.StringVar()
		self.steamdir.set(options["steamdir"])

		self.errstates = [False, False, False, False, False]
		# 0:Bad config, 1: Steamdir on bad drive, 2: VDF missing,
		# 3:Demo outside /tf/, 4:No launchoptions

		self.playdemoarg = tk.StringVar()
		self.userselectvar = tk.StringVar()
		try:
			self.userselectvar.set(self.getusers()[0])
		except: pass
		self.launchoptionsvar = tk.StringVar()

		self.shortdemopath = ""
		self.__constructshortdemopath()

		super().__init__( self.parent, "Play demo / Launch TF2...")

	def body(self, master):
		'''UI'''
		steamdirframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8), 
			labelwidget = frmd_label(master, "Steam install path") )
		widgetframe = ttk.Frame(steamdirframe)
		self.steamdirentry = ttk.Entry(widgetframe, state = "readonly",
			textvariable = self.steamdir)
		self.steamdirbtn = ttk.Button(widgetframe,
			style = "Contained.TButton", command = self.askfordir,
			text = "Select Steam install path")
		widgetframe.pack(side = tk.TOP, expand = 1, fill = tk.X)
		self.error_steamdir_invalid = ttk.Label(steamdirframe, anchor = tk.N,
			justify = tk.CENTER, style = "Error.Contained.TLabel",
			text = ("Getting steam users failed! Please select the root folder"
			" called \"Steam\".\nEventually check for permission conflicts.") )
		self.warning_steamdir_mislocated = ttk.Label(steamdirframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("The queried demo and the Steam directory are on"
			" seperate drives.") )

		userselectframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8),
			labelwidget = frmd_label(master, "Select user profile if needed"))
		self.info_launchoptions_not_found = ttk.Label(userselectframe,
			anchor = tk.N, style = "Info.Contained.TLabel", text = ("Launch "
			"configuration not found, it likely does not exist.") )
		self.userselectbox = ttk.Combobox(userselectframe,
			textvariable = self.userselectvar, values = self.getusers(),
			state = "readonly")#Once changed, observer callback triggered by self.userselectvar

		launchoptionsframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8),
			labelwidget = frmd_label(master, "Launch options:") )
		launchoptwidgetframe = ttk.Frame(launchoptionsframe, borderwidth = 4,
			relief = tk.RAISED, padding = (5, 4, 5, 4), width = 450,
			height = 50)
		self.launchlabel1 = ttk.Label(launchoptwidgetframe,
			text = "[...]/hl2.exe -steam -game tf")
		self.launchoptionsentry = ttk.Entry(launchoptwidgetframe,
			textvariable = self.launchoptionsvar)
		pluslabel = ttk.Label(launchoptwidgetframe, text = "+")
		self.launchlabelentry = ttk.Entry(launchoptwidgetframe,
			state = "readonly", textvariable = self.playdemoarg)
		launchoptwidgetframe.pack_propagate(False)

		self.warning_vdfmodule = ttk.Label(launchoptionsframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("Please install the vdf module in order to launch TF2 with"
			" your default settings.\n(Run cmd in admin mode; type "
			"\"python -m pip install vdf\")"), justify = tk.CENTER)

		self.warning_not_in_tf_dir = ttk.Label(launchoptionsframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("The demo can not be played as it is not in"
			" Team Fortress\' file system (/tf/)") )
		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)

		#pack start
		self.steamdirentry.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		self.steamdirbtn.pack(side = tk.LEFT, fill = tk.X)
		self.error_steamdir_invalid.pack()
		self.warning_steamdir_mislocated.pack()
		steamdirframe.pack(fill = tk.BOTH, expand = 1, pady = 5)

		self.userselectbox.pack(fill = tk.X)
		self.info_launchoptions_not_found.pack()
		userselectframe.pack(fill = tk.BOTH, expand = 1, pady = 5)

		self.warning_vdfmodule.pack()
		self.launchlabel1.pack(side = tk.LEFT, fill = tk.Y)
		self.launchoptionsentry.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		pluslabel.pack(side = tk.LEFT)
		self.launchlabelentry.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		launchoptwidgetframe.pack(side = tk.TOP, expand = 1, fill = tk.X)
		self.warning_not_in_tf_dir.pack()
		launchoptionsframe.pack(fill = tk.BOTH, expand = 1, pady = (5, 10))

		self.btconfirm = ttk.Button(master, text = "Launch!",
			command = lambda: self.done(1))
		self.btcancel = ttk.Button(master, text = "Cancel",
			command = lambda: self.done(0))

		self.btconfirm.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (0, 3))
		self.btcancel.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (3, 0))
		self.userchange()

		self.__showerrs()
		self.userselectvar.trace("w", self.userchange) # If applied before,
		# method would be triggered and UI elements would be accessed that do not exist yet.

	def __showerrs(self):#NOTE: Could update that, do in case you ever change this dialog
		'''Update all error labels after looking at conditions'''
		if self.errstates[0]:
			self.error_steamdir_invalid.pack(side = tk.BOTTOM)
		else:
			self.error_steamdir_invalid.pack_forget()
		if self.errstates[1]:
			self.warning_steamdir_mislocated.pack(side = tk.BOTTOM)
		else:
			self.warning_steamdir_mislocated.pack_forget()
		if self.errstates[2]:
			self.warning_vdfmodule.pack(side = tk.TOP)
		else:
			self.warning_vdfmodule.pack_forget()
		if self.errstates[3]:
			self.warning_not_in_tf_dir.pack(side = tk.BOTTOM, anchor = tk.S,
				fill = tk.BOTH)
		else:
			self.warning_not_in_tf_dir.pack_forget()
		if self.errstates[4]:
			self.info_launchoptions_not_found.pack(fill = tk.BOTH)
		else:
			self.info_launchoptions_not_found.pack_forget()

	def getusers(self):
		'''Executed once by body(), by askfordir(), and used to insert value
		into self.userselectvar.
		'''
		toget = os.path.join(self.steamdir.get(), _DEF.STEAM_CFG_PATH0)
		try:
			users = os.listdir(toget)
		except (OSError, PermissionError, FileNotFoundError):
			self.errstates[0] = True
			return []
		self.errstates[0] = False
		return users

	def __getlaunchoptions(self):
		try:
			import vdf
			self.errstates[2] = False
			with open(os.path.join( self.steamdir.get(),
				_DEF.STEAM_CFG_PATH0, self.userselectvar.get(),
				_DEF.STEAM_CFG_PATH1) ) as h:
				launchopt = vdf.load(h)
			for i in _DEF.LAUNCHOPTIONSKEYS:
				try:
					launchopt = eval("launchopt" + i)
					break
				except KeyError:
					pass
			else: # Loop completed normally --> No break statement encountered -> No key found
				raise KeyError("No launch options key found.")
			self.errstates[4] = False
			return launchopt
		except ModuleNotFoundError:
			self.errstates[2] = True
			self.errstates[4] = False
			return ""
		except (KeyError, FileNotFoundError, OSError, PermissionError,
			SyntaxError): #SyntaxError raised by vdf module
			self.errstates[4] = True
			return ""

	def askfordir(self): #Triggered by user clicking on the Dir choosing btn
		'''Opens up a file selection dialog and sets the steam directory to
		the selected directory, updating related widgets.
		'''
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steamdir.set(sel)
		self.userselectbox.config(values = self.getusers())
		try:
			self.userselectvar.set(self.getusers()[0])
		except Exception:
			self.userselectvar.set("") # will trigger self.userchange
		self.__constructshortdemopath()
		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)
		self.__showerrs()

	def userchange(self, *_): # Triggered by observer on combobox variable.
		launchopt = self.__getlaunchoptions()
		self.launchoptionsvar.set(launchopt)
		self.__showerrs()

	def __constructshortdemopath(self):
		try:
			self.shortdemopath = os.path.relpath(self.demopath,
				os.path.join(self.steamdir.get(), _DEF.TF2_HEAD_PATH))
			self.errstates[1] = False
		except ValueError:
			self.shortdemopath = ""
			self.errstates[1] = True
			self.errstates[3] = True
		if ".." in self.shortdemopath:
			self.errstates[3] = True
		else:
			self.errstates[3] = False
		self.playdemoarg.set("playdemo " + self.shortdemopath)

	def done(self, param):
		if param:
			executable = os.path.join(self.steamdir.get(), _DEF.TF2_EXE_PATH)
			launchopt = self.launchoptionsvar.get()
			launchopt = launchopt.split(" ")
			launchoptions = ([executable] + _DEF.TF2_LAUNCHARGS +
				launchopt + ["+playdemo", self.shortdemopath])
			try:
				subprocess.Popen(launchoptions) #Launch tf2; -steam param may cause conflicts when steam is not open but what do I know?
				self.result_ = {"success":True, "steampath":self.steamdir.get()}
			except FileNotFoundError:
				self.result_ = {"success":False, "steampath":self.steamdir.get()}
				tk_msg.showerror("Demomgr - Error", "hl2 executable not found.", parent = self)
			except (OSError, PermissionError) as error:
				self.result_ = {"success":False, "steampath":self.steamdir.get()}
				tk_msg.showerror("Demomgr - Error",
					"Could not access hl2.exe :\n{}".format(str(error)), parent = self)
		self.destroy()

class Settings(_BaseDialog):
	def __init__(self, parent, cfg):
		'''Args: parent tkinter window, program configuration'''
		self.cfg = cfg

		self.datagrabmode_var = tk.IntVar()
		self.datagrabmode_var.set(cfg["datagrabmode"])
		self.preview_var = tk.BooleanVar()
		self.preview_var.set(cfg["previewdemos"])
		self.steampath_var = tk.StringVar()
		self.steampath_var.set(cfg["steampath"])
		self.ui_style_var = tk.StringVar()
		self.ui_style_var.set(cfg["ui_theme"])

		self.blockszvals = {convertunit(i, "B"): i for i in [2**pw for pw in range(12, 28)] }

		super().__init__( parent, "Settings")

	def body(self, master):
		'''UI'''
		display_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Display"))
		ttk.Checkbutton(display_labelframe, variable = self.preview_var,
			text="Preview demos?", style = "Contained.TCheckbutton").pack(
			ipadx = 4, anchor = tk.NW)
		ui_style_labelframe = ttk.Labelframe(display_labelframe,
			style = "Contained.TLabelframe", padding = 8,
			labelwidget = frmd_label(display_labelframe, "UI Style") )
		radiobtnframe = ttk.Frame(ui_style_labelframe, style = "Contained.TFrame")
		for i in _DEF.THEME_PACKAGES.keys():
			b = ttk.Radiobutton(radiobtnframe, variable = self.ui_style_var,
				text = i, value = i, style = "Contained.TRadiobutton")
			b.pack(side = tk.TOP, anchor = tk.W, ipadx = 4)
		ttk.Radiobutton(radiobtnframe, variable = self.ui_style_var,
			text = "Default", value = "_DEFAULT", style =
			"Contained.TRadiobutton").pack(side = tk.TOP, anchor = tk.W, ipadx = 4)
		radiobtnframe.pack(side = tk.TOP, fill = tk.X)
		ui_style_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 4)

		steampath_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Steam path"))
		self.steampathentry = ttk.Entry(steampath_labelframe, state = "readonly",
			textvariable = self.steampath_var)
		steampath_choosebtn = ttk.Button(steampath_labelframe, text = "Change...",
			command = self.choosesteampath, style = "Contained.TButton")
		self.steampathentry.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.N)
		steampath_choosebtn.pack(side = tk.RIGHT, expand = 0, fill = tk.X, anchor = tk.N)

		datagrab_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Get bookmark information via..."))
		radiobtnframe = ttk.Frame(datagrab_labelframe, style = "Contained.TFrame")
		for i, j in ((".json files", 2), (_DEF.EVENT_FILE, 1), ("None", 0)):
			b = ttk.Radiobutton(radiobtnframe, value = j,
				variable = self.datagrabmode_var, text = i,
				style = "Contained.TRadiobutton")
			b.pack(side = tk.TOP, anchor = tk.W, ipadx = 4)
		radiobtnframe.pack(side = tk.TOP, fill = tk.X)
		del radiobtnframe

		eventread_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Read _events.txt in chunks of size...") )
		self.blockszselector = ttk.Combobox(eventread_labelframe,
			state = "readonly", values = [k for k in self.blockszvals])
		self.blockszselector.pack(side = tk.TOP, expand = 1, fill = tk.X, anchor = tk.N)

		try:
			self.blockszvals[convertunit(self.cfg["evtblocksz"], "B")]
			self.blockszselector.set(convertunit(self.cfg["evtblocksz"], "B"))
		except KeyError:
			self.blockszselector.set(next(iter(self.blockszvals)))

		display_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)
		steampath_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)
		datagrab_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)
		eventread_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)

		btconfirm = ttk.Button(master, text = "Ok", command = lambda: self.done(1))
		btcancel = ttk.Button(master, text = "Cancel", command = lambda: self.done(0))

		btconfirm.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (0, 3))
		btcancel.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (3, 0))

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		if param:
			self.result = {	"datagrabmode":self.datagrabmode_var.get(),
							"previewdemos":self.preview_var.get(),
							"steampath":self.steampath_var.get(),
							"evtblocksz":self.blockszvals[self.blockszselector.get()],
							"ui_theme":self.ui_style_var.get()}
		else:
			self.result = None
		self.destroy()

	def choosesteampath(self):
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steampath_var.set(sel)
