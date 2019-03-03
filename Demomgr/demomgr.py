#!/usr/bin/env python3
#Demomgr
#Created by Square789, 2018 - 2019
import os
import sys
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as tk_msg
import tkinter.scrolledtext as tk_scr
import tkinter.filedialog as tk_fid
from tkinter.simpledialog import Dialog
from math import log10, floor
import time
import struct
import re
import datetime
import subprocess
import json
import shutil

sys.path.append(os.getcwd())#Bad idea, fix soon
import multiframe_list as mfl
import handle_events as handle_ev

__version__ = 0.1
__author__ = "Square789"

#NOTE: This program likes ("", (), ()) a lot, which will cause problems because it is hardcoded in a very bad manner

_DEF = {"cfgfolder":".demomgr", #Values. Is important. No changerooni.
		"cfgname":"config.cfg",
		"iconname":"demmgr.ico",
		"defaultcfg":	{	"demopaths":[],
							"lastpath":"",
							"firstrun":True,
							"__comment":"By messing with the firstrun parameter you acknowledge that you've read the Terms of use.",
							"datagrabmode":0,
							"previewdemos":True,
							"steampath":"",
							"evtblocksz":65536
						},
		"eventbackupfolder":"_eventbackup",
		"WELCOME":"Hi and Thank You for using DemoManager!\n\nA config file has been created in a folder next to the script.\n\nThis script is able to delete files if you tell it to.\nI in no way guarantee that this script is safe or 100% reliable and will not take any responsibility for lost data, damaged drives and/or destroyed hopes and dreams. If something goes wrong, data recovery tools are a thing.\nThis program is licensed via the MIT Licence, by clicking the accept button below, you confirm that you have read and accepted the license.",
		"eventfile":"_events.txt",#If this name should for whatever reason change at some point, change this variable
		"dateformat":"%d.%m.%Y  %H:%M:%S",
		"eventfile_filenameformat":" \\(\".+\" at",#regex
		"eventfile_bookmark":"Bookmark",
		"eventfile_killstreak":"Killstreak",
		"eventfile_ticklogsep":" at \\d+\\)",#regex
		"eventfile_argident":" [a-zA-Z0-9]+ \\(",#regex
		"demlabeldefault":"No demo selected.",
		"statusbardefault":"Ready.",
		"tf2exepath":"steamapps/common/team fortress 2/hl2.exe",
		"tf2headpath":"steamapps/common/team fortress 2/tf/",
		"tf2launchargs":["-steam", "-game", "tf"],
		"steamconfigpath1":"userdata/",
		"steamconfigpath2":"config/localconfig.vdf",
		"launchoptionskey":"[\"UserLocalConfigStore\"][\"Software\"][\"valve\"][\"Steam\"][\"Apps\"][\"440\"][\"LaunchOptions\"]",
		"errlogfile":"err.log",
		"filterdict":	{	"name":("\"{}\" in x[\"name\"]", str),#[0] will be passed through eval(); all keys will be prefixed with "lambda x: "; {} replaced with element [1] called with ESCAPED user input as parameter
							"killstreak_min":("len(x[\"killstreaks\"]) >= {}", int),
							"killstreak_max":("len(x[\"killstreaks\"]) <= {}", int),
							"bookmark_min":("len(x[\"bookmarks\"]) >= {}", int),
							"bookmark_max":("len(x[\"bookmarks\"]) <= {}", int),
							"bookmark_contains":("\"{}\" in \"\".join((i[0] for i in x[\"bookmarks\"]))", str),
							"map_name":("\"{}\" in x[\"header\"][\"map_name\"]", str),
							"hostname":("\"{}\" in x[\"header\"][\"hostname\"]", str),
							"clientid":("\"{}\" in x[\"header\"][\"clientid\"]", str),
							"beststreak_min":("max((i[0] for i in x[\"killstreaks\"]), default=0) >= {}", int),
							"beststreak_max":("max((i[0] for i in x[\"killstreaks\"]), default=99999) <= {}", int),
							"moddate_min":("x[\"filedata\"][\"modtime\"] >= {}", int),
							"moddate_max":("x[\"filedata\"][\"modtime\"] <= {}", int),
							"filesize_min":("x[\"filedata\"][\"filesize\"] >= {}", int),
							"filesize_max":("x[\"filedata\"][\"filesize\"] <= {}", int),
						},
		"filterneg":"!",
		"filterkeysep":":",
		"filterparamsep":"*",
		}

_convpref = ["y","z","a","f","p","n","µ","m","","k","M","G","T","P","E","Z","Y"] #LIST HAS TO BE OF SAME LENGTH TO LEFT AND RIGHT SIDE, STARTING AT ""
def convertunit(inp, ext = "B"):
	'''Unit conversion function I cobbled together.'''
	isneg = False
	if inp < 0:
		inp = abs(inp)
		isneg = True
	elif inp == 0:
		return "0 " + ext
	mag = floor(floor(log10(inp)) / 3)
	return isneg*"-" + str(round((inp / (10**(mag * 3))), 3)) + " " + _convpref[round(len(_convpref)/2) + mag] + ext#round(2.5) results in 2, which it technically shouldn't but that's good

def formatdate(inp):
	'''Turns unix timestamp into readable format (_DEF["dateformat"])'''
	return datetime.datetime.fromtimestamp(inp).strftime(_DEF["dateformat"])

def readbinStr(handle, len = 260):
	'''Reads file handle by len bytes and attempts to decode to utf-8'''
	rawbin = handle.read(len)
	bin = rawbin.strip(b"\x00")
	return bin.decode("utf-8")

def readbinInt(handle, len = 4):
	rawbin = handle.read(len)
	return struct.unpack("i",rawbin)[0]

def readbinFlt(handle):
	rawbin = handle.read(4)
	return struct.unpack("f",rawbin)[0]

def demheaderreader(path): #Code happily duplicated from https://developer.valvesoftware.com/wiki/DEM_Format
	'''Reads the header information of a demo.'''
	demhdr = {	"dem_prot":None,
				"net_prot":None,
				"hostname":None,
				"clientid":None,
				"map_name":None,
				"game_dir":None,
				"playtime":None,
				"tick_num":None,
				"framenum":None,
				"tickrate":None,}
	
	h = open(path, "rb")
	if readbinStr(h, 8) == "HL2DEMO":
		demhdr["dem_prot"] = readbinInt(h)
		demhdr["net_prot"] = readbinInt(h)
		demhdr["hostname"] = readbinStr(h)
		demhdr["clientid"] = readbinStr(h)
		demhdr["map_name"] = readbinStr(h)
		demhdr["game_dir"] = readbinStr(h)
		demhdr["playtime"] = readbinFlt(h)
		demhdr["tick_num"] = readbinInt(h)
		demhdr["framenum"] = readbinInt(h)
		demhdr["tickrate"] = int(demhdr["tick_num"] / demhdr["playtime"])
	h.close()

	return demhdr

def extractlogarg(logchunk):
	'''Extracts the argument(killstreak number; bookmark name) from a logchunk'''
	regres = re.search(_DEF["eventfile_argident"], logchunk)
	return regres[0][1:len(regres[0]) - 2]

def convertlogchunks(logchunk):
	'''Converts each _events.txt logchunk to a tuple: (filename, [(Streak: killstreakpeaks), (tick)], [(Bookmark: bookmarkname), (tick)])'''
	loglines = logchunk.split("\n")
	if loglines:
		filenamesearch = re.search(_DEF["eventfile_filenameformat"], loglines[0])
	else:
		return ("", (), ())
	if filenamesearch:
		filename = filenamesearch[0][3:-4] + ".dem"
	else:
		return ("", (), ())
	#if the code reached this point, file name is present
	killstreaks = []
	bookmarks = []

	for i in loglines: #for each line in the feed
		if i == "": #Line empty, likely last line.
			continue
		tick = i[-(len(re.search(_DEF["eventfile_ticklogsep"], i)[0]) - 5) -1: -1]#Unreadable but eh
		searchres = i.find(_DEF["eventfile_bookmark"])
		if searchres != -1: #Line mentions a bookmark
			bmname = extractlogarg(i)
			bookmarks.append((bmname, int(tick)))
			continue
		searchres = i.find(_DEF["eventfile_killstreak"])
		if searchres != -1: #Line mentions a killstreak
			ksnum = int(extractlogarg(i))
			killstreaks.append((ksnum, int(tick)))
			continue

	streakpeaks = []
	if killstreaks == []:
		streakpeaks = []
	else:
		killstreaks.append((-1,-1))
		prv = (-1, -1)
		for i in killstreaks:
			if i[0]<=prv[0]:
				streakpeaks.append(prv)
			prv = i
	return (filename, streakpeaks, bookmarks) #there he is

def readevents(handle, blocksz):
	'''This function reads an events.txt file as it's written by the source engine, returns (filename, ( (killstreakpeak, tick)... ), ( (bookmarkname, tick)... ) )'''
	reader = handle_ev.EventReader(handle, blocksz=blocksz)
	out = []
	for chk in reader:
		out.append(convertlogchunks(chk.content))
	reader.destroy()
	return out

def assignbookmarkdata(files, bookmarkdata):
	"""Takes a list of files and the bookmarkdata; returns a list that contains the parallel bookmarkdata; ("", [], []) if no match found."""
	assignedlogs = [("",[],[]) for i in range(len(files))]
	for i in bookmarkdata:
		for j in range(len(files)):
			if i[0]==files[j]:
				assignedlogs[j] = i
	return assignedlogs

def formatbookmarkdata(filelist, bookmarkdata):
	'''Converts bookmarkdata into a list of strings: "X Bookmarks, Y Killstreaks". needs filelist to assign bookmarkdata to '''
	assignedlogs = assignbookmarkdata(filelist, bookmarkdata)
	listout = ["" for i in assignedlogs]
	for i in range(len(assignedlogs)): #convert the correctly assigned logs ("", [], []) into information displaying strings
		if assignedlogs[i] != ("",[],[]):
			listout[i] = str(len(assignedlogs[i][2])) + " Bookmarks; " + str(len(assignedlogs[i][1])) + " Killstreaks."
		else:
			listout[i] = "None"
	return listout

def escapeinput(raw):
	"""Adds escape char (\) in front of all occurrences of \\ and \" """
	out = []
	toescape = ["\"", "\\"]
	for i in raw:
		if i in toescape:
			out.append("\\")
		out.append(i)
	return "".join(out)

class HeaderFetcher: #used in MainApp.__filter
	'''Only read a header when the class is accessed.'''
	def __init__(self, filepath):
		self.filepath = filepath
		self.header = None

	def __getitem__(self, key):
		if self.header == None:
			self.header = demheaderreader(self.filepath)
		return self.header[key]

class FileStatFetcher: #used in MainApp.__filter
	'''Only read a file's size and moddate when the class is accessed.'''
	def __init__(self, filepath):
		self.filepath = filepath
		self.data = None

	def __getitem__(self, key):
		if self.data == None:
			statres = os.stat(self.filepath)
			self.data = {"filesize":statres.st_size, "modtime":statres.st_mtime}
		return self.data[key]

class FirstRunDialog(Dialog):
	def __init__(self, parent = None):
		if not parent:
			parent = tk._default_root
		super().__init__(parent, "Welcome!")

	def destroy(self):
		super().destroy()

	def body(self, master):
		txtbox = tk_scr.ScrolledText(master, wrap = tk.WORD)
		txtbox.insert(tk.END,_DEF["WELCOME"])
		txtbox.config(state = tk.DISABLED)

		txtbox.pack(expand=0, fill = tk.X)

		btconfirm = tk.Button(master, text = "I am okay with that and I accept.", command = lambda: self.done(1))
		btcancel = tk.Button(master, text="Cancel!", command = lambda: self.done(0))

		btconfirm.pack(side = tk.LEFT, anchor = tk.W, expand=1, fill = tk.X)
		btcancel.pack(side = tk.LEFT, anchor = tk.E, expand=1, fill = tk.X)

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		self.result = param
		self.destroy()

	def buttonbox(self):
		pass

class LaunchTF2(Dialog):
	def __init__(self, parent, options):

		self.result_ = {}

		self.parent = parent

		self.demopath = options["demopath"]
		self.steamdir = tk.StringVar()
		self.steamdir.set(options["steamdir"])

		self.errstates = [False, False, False, False, False] #0:Invalid steamdir, 1: Steamdir on bad drive, 2: VDF missing, 3:Demo outside /tf/, 4:No launchoptions

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
		'''Ugly UI setup'''
		steamdirframe= tk.LabelFrame(master, text="Steam install path", padx = 10, pady=8)
		self.steamdirentry = tk.Entry(steamdirframe, state="readonly", textvariable = self.steamdir)
		self.steamdirbtn = tk.Button(steamdirframe, command=self.askfordir, text="Select Steam install path")
		self.error_steamdir_invalid = tk.Label(steamdirframe, fg="#AA0000", text="Steam dir is malformed or nonexistent! Please select the root folder called \"Steam\".")
		self.warning_steamdir_mislocated = tk.Label(steamdirframe, fg="#AA0000", text="The queried demo and the Steam directory are on seperate drives.")

		userselectframe = tk.LabelFrame(master, text="Select user profile if needed", padx = 10, pady=8)
		self.info_launchoptions_not_found = tk.Label(userselectframe, fg = "#222222", text="Launch configuration not found, it likely does not exist.")
		self.userselectspinbox = tk.Spinbox(userselectframe, textvariable = self.userselectvar, values=self.getusers(), state="readonly")#Once changed, observer callback will be triggered by self.userselectvar

		launchoptionsframe = tk.LabelFrame(master, text="Launch options:", padx = 10, pady=8)
		launchoptwidgetframe = tk.Frame(launchoptionsframe, bd=4, relief = tk.RAISED, padx = 5, pady = 4)
		self.warning_vdfmodule = tk.Label(launchoptwidgetframe, fg="#AA0000", text="Please install the vdf module in order to launch TF2 with your default settings. (Run cmd in admin mode; type \"python -m pip install vdf\")")#WARNLBL
		self.launchlabel1 = tk.Label(launchoptwidgetframe, text="[...]/hl2.exe -steam -game tf")
		self.launchoptionsentry = tk.Entry(launchoptwidgetframe, textvariable=self.launchoptionsvar)
		pluslabel = tk.Label(launchoptwidgetframe, text="+")
		self.launchlabelentry = tk.Entry(launchoptwidgetframe, state="readonly", textvariable = self.playdemoarg)

		self.warning_not_in_tf_dir = tk.Label(launchoptionsframe, fg="#AA0000", text="The demo can not be played as it is not in Team Fortress\' file system (/tf/)")

		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)

		#pack start
		self.steamdirentry.pack(fill=tk.BOTH,expand=1)
		self.steamdirbtn.pack(fill=tk.BOTH,expand=1)
		self.error_steamdir_invalid.pack(fill=tk.BOTH,expand=1)
		self.warning_steamdir_mislocated.pack(fill=tk.BOTH,expand=1)
		steamdirframe.pack(fill=tk.BOTH, expand=1)

		self.userselectspinbox.pack(fill=tk.BOTH,expand=1)
		self.info_launchoptions_not_found.pack(fill=tk.BOTH, expand=1)
		userselectframe.pack(fill=tk.BOTH, expand=1)

		self.warning_vdfmodule.pack(side=tk.TOP,expand=0)
		self.launchlabel1.pack(side=tk.LEFT,fill=tk.Y,expand=0)
		self.launchoptionsentry.pack(side=tk.LEFT,fill=tk.BOTH,expand=1)
		pluslabel.pack(side=tk.LEFT,fill=tk.BOTH,expand=0)
		self.launchlabelentry.pack(side=tk.LEFT,fill=tk.BOTH,expand=0)
		launchoptwidgetframe.pack(side=tk.TOP, expand = 1, fill = tk.BOTH)

		self.warning_not_in_tf_dir.pack(side=tk.BOTTOM, anchor = tk.S, fill=tk.BOTH,expand=1)
		launchoptionsframe.pack(fill=tk.BOTH,expand=1)

		self.btconfirm = tk.Button(master, text = "Launch!", command = lambda: self.done(1))
		self.btcancel = tk.Button(master, text="Cancel", command = lambda: self.done(0))

		self.btconfirm.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)
		self.btcancel.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)
		self.userchange()

		self.__showerrs()
		self.userselectvar.trace("w", self.userchange)#If applied before, method would be triggered and UI elements would be accessed that do not exist yet.

	def __showerrs(self):#NOTE: Can't figure out what flag pack_propagate sets
		'''Update all error labels after looking at conditions'''
		if self.errstates[0]:
			self.error_steamdir_invalid.pack(fill=tk.BOTH,expand=1)
		else:
			self.error_steamdir_invalid.pack_forget()
		if self.errstates[1]:
			self.warning_steamdir_mislocated.pack(fill=tk.BOTH,expand=1)
		else:
			self.warning_steamdir_mislocated.pack_forget()
		if self.errstates[2]:
			self.warning_vdfmodule.pack(side=tk.TOP,expand=0)
		else:
			self.warning_vdfmodule.pack_forget()
		if self.errstates[3]:
			self.warning_not_in_tf_dir.pack(side=tk.BOTTOM, anchor = tk.S, fill=tk.BOTH,expand=1)
		else:
			self.warning_not_in_tf_dir.pack_forget()
		if self.errstates[4]:
			self.info_launchoptions_not_found.pack(fill=tk.BOTH, expand=1)
		else:
			self.info_launchoptions_not_found.pack_forget()

	def getusers(self):
		'''Executed once by body(), by askfordir(),  and used to insert value into self.userselectvar'''
		toget = os.path.join(self.steamdir.get(), _DEF["steamconfigpath1"])
		if not os.path.exists(toget):
			self.errstates[0] = True
			return []
		self.errstates[0] = False
		return os.listdir(toget)

	def __getlaunchoptions(self):
		try:
			import vdf
			self.errstates[2] = False
			with open(os.path.join(os.path.join(os.path.join(self.steamdir.get(), _DEF["steamconfigpath1"]), self.userselectvar.get()), _DEF["steamconfigpath2"]) ) as h:
				launchopt = vdf.load(h)
			launchopt = eval("launchopt" + _DEF["launchoptionskey"])
			self.errstates[4] = False
			return launchopt
		except ModuleNotFoundError:
			self.errstates[2] = True
			self.errstates[4] = False
			return ""
		except KeyError:
			self.errstates[4] = True
			return ""
		except FileNotFoundError:
			self.errstates[4] = True
			return ""

	def askfordir(self):#Triggered by user clicking on the Dir choosing btn
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steamdir.set(sel)
		self.userselectspinbox.config(values = self.getusers())
		try:
			self.userselectvar.set(self.getusers()[0])
		except: self.userselectvar.set("")# will trigger self.userchange
		self.__constructshortdemopath()
		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)
		self.__showerrs()

	def userchange(self, *_):#Triggered by User selection spinbox -> self.userselectvar
		launchopt = self.__getlaunchoptions()
		self.launchoptionsvar.set(launchopt)
		self.__showerrs()

	def __constructshortdemopath(self):
		try:
			self.shortdemopath = os.path.relpath(self.demopath, os.path.join(self.steamdir.get(),_DEF["tf2headpath"]))
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
			executable = os.path.join(self.steamdir.get(), _DEF["tf2exepath"])
			launchopt = self.launchoptionsvar.get()
			launchopt = launchopt.split(" ")
			launchoptions = [executable] + _DEF["tf2launchargs"] + launchopt + ["+playdemo", self.shortdemopath]
			try:
				subprocess.Popen(launchoptions) #Launch tf2; -steam param may cause conflicts when steam is not open but what do I know?
				self.result_ = {"success":True,"steampath":self.steamdir.get()}
			except FileNotFoundError:
				self.result_ = {"success":False,"steampath":self.steamdir.get()}
				tk_msg.showerror("Demomgr - Error", "hl2 executable not found.", parent = self)
		self.destroy()

	def buttonbox(self):
		pass

	def destroy(self):
		super().destroy()

class DeleteDemos(Dialog):
	def __init__(self, parent, **options):
		'''Variable setup'''
		self.master = parent

		self.bookmarkdata = options["bookmarkdata"]
		self.files = options["files"]
		self.dates = options["dates"]
		self.filesizes = options["filesizes"]
		self.curdir = options["curdir"]
		self.cfg = options["cfg"]

		self.selifnobookmarkdata_var = tk.BooleanVar()
		self.keepevents_var = tk.BooleanVar()
		self.deluselessjson_var = tk.BooleanVar()
		self.selall_var = tk.BooleanVar()
		self.onlyprocifsel_var = tk.BooleanVar()

		self.combobox_var = tk.StringVar()

		self.selected = [False for i in self.files]

		self.result_ = {"state":0}

		self.CND = {#"Map name": -1,
					"Date before [UNIX Timestamp]":{"id":0, "cond":None},
					"Date after [UNIX Timestamp]":{"id":1, "cond":None},
					"No killstreak above":{"id":2, "cond":None},
					"Less than <> killstreaks":{"id":3, "cond":None},
					"Less than <> bookmarks":{"id":4, "cond":None},
					"Filesize below":{"id":5, "cond":None},
					"Filesize above":{"id":6, "cond":None} #condition dict
					}

		super().__init__(parent, "Delete...")

	def body(self, master):
		'''UI'''
		master.bind("<<MultiframeSelect>>", self.procitem) #on select, process item selected.

		okbutton = tk.Button(master, text = "Delete", command = lambda: self.done(1) )
		cancelbutton = tk.Button(master, text= "Cancel", command = lambda: self.done(0) )

		self.listbox = mfl.Multiframe(master, columns = 5, names= ["","Name","Date created","Info","Filesize"], sort = 0, formatters = [None, None, formatdate, None, convertunit], widths = [2, None, 18, 25, 15])
		self.listbox.setdata(([self.o(i) for i in self.selected], self.files, self.dates, formatbookmarkdata(self.files, self.bookmarkdata), self.filesizes) , mfl.COLUMN)
		self.listbox.format()

		self.demoinflabel = tk.Label(master, text="", justify=tk.LEFT, anchor=tk.W, font = ("Consolas", 8) )

		self.listbox.frames[0][2].pack_propagate(False) #looks weird, is sloppy, will probably lead to problems at some point. change parent to master if problems occur and comment out this line
		selall_checkbtn = ttk.Checkbutton(self.listbox.frames[0][2], variable=self.selall_var, text="", command = self.selall) # ''

		optframe = tk.LabelFrame(master, text="Options...", pady=3, padx=8)
		keepevents_checkbtn = ttk.Checkbutton(optframe, variable = self.keepevents_var, text = "Make backup of " + _DEF["eventfile"])
		deljson_checkbtn = ttk.Checkbutton(optframe, variable = self.deluselessjson_var, text = "Delete orphaned json files")

		condframe = tk.LabelFrame(master, text="Demo selector [Incomplete feature]", pady=3, padx=8)
		condcheckbtnframe = tk.Frame(condframe)
		self.condbox = ttk.Combobox(condframe, state = "readonly", values = [i for i in self.CND]) #CND keys are values.
		self.condbox.set(next(iter(self.CND)))#dunno what this does, stole it from stackoverflow, seems to work.
		self.condvalbox = tk.Entry(condframe) #
		self.applybtn = tk.Button(condframe, text="Apply selection", command = self.applycond)
		selifnobookmarks_checkbox = ttk.Checkbutton(condcheckbtnframe, text="Select when no information on condition is found", variable = self.selifnobookmarkdata_var)
		onlyprocifsel_checkbox = ttk.Checkbutton(condcheckbtnframe, text="Only process files when they are already selected.", variable = self.onlyprocifsel_var)

		onlyprocifsel_checkbox.pack(side=tk.LEFT)
		selifnobookmarks_checkbox.pack(side=tk.LEFT)
		condcheckbtnframe.pack(side=tk.BOTTOM, expand=1, fill=tk.X)

		self.applybtn.pack(side=tk.RIGHT)
		tk.Label(condframe).pack(side=tk.RIGHT)
		self.condvalbox.pack(side=tk.RIGHT, fill=tk.X, expand=1)
		tk.Label(condframe).pack(side=tk.RIGHT)
		self.condbox.pack(side=tk.RIGHT, fill=tk.X, expand=1)
		condframe.pack(fill=tk.BOTH)

		deljson_checkbtn.pack(side=tk.LEFT)
		keepevents_checkbtn.pack(side=tk.LEFT)
		optframe.pack(fill=tk.BOTH)

		selall_checkbtn.pack(side=tk.LEFT, anchor=tk.W)

		self.listbox.pack(side=tk.TOP,fill=tk.BOTH, expand=1)

		self.demoinflabel.pack(side=tk.TOP, fill = tk.BOTH, expand = 0, anchor = tk.W)

		okbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)
		cancelbutton.pack(side=tk.LEFT, fill=tk.X,expand=1)

	def buttonbox(self):
		pass

	def destroy(self):
		super().destroy()

	def procitem(self, event):
		index = self.listbox.getindex()

		if self.cfg["previewdemos"]:
			hdrinf = demheaderreader(os.path.join(self.curdir, self.listbox.getcell(1,index)) )
			self.demoinflabel.config(text=("Hostname: " + hdrinf["hostname"] + "| ClientID: " + hdrinf["clientid"] + "| Map name: " + hdrinf["map_name"]) )
		
		if self.listbox.getrowindex() != 0: return
		if index == None: return
		self.selected[index] = not self.selected[index]
		if False in self.selected:
			self.selall_var.set(0)
		else:
			self.selall_var.set(1)
		self.listbox.setcell(0, index, self.o(self.selected[index]))

	def setitem(self, index, value, lazyui = False, only_proc_if_selected = False): #value: bool
		if only_proc_if_selected and (not self.selected[index]):
			return
		self.selected[index] = value
		if not lazyui:
			if False in self.selected: #~ laggy
				self.selall_var.set(0)
			else:
				self.selall_var.set(1)
			self.listbox.setcolumn(0, [self.o(i) for i in self.selected])#do not refresh ui. this is done while looping over the elements, then a final refresh is performed.

	def o(self, _in):
		return " " if not _in else " X"

	def applycond(self): #TODO: OPTIMIZE WITH LAMBDAS
		'''Apply user-entered condition to the files. True spaghetti code.'''
		conditionname = self.condbox.get()
		procifselected = self.onlyprocifsel_var.get()#Assigning to local namespace, i have no idea if this makes it go faster
		if conditionname == "": #empty value of stringvar
			return
		conditionvalue = self.condvalbox.get()#is good, unless empty string
		if conditionvalue == "":
			return
		conditionid = self.CND[conditionname]["id"] #hardcoded conditions, they work much, much faster.
		if conditionid == 0: #Date before
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			for i, j in enumerate(self.files):
				if self.dates[i] < conditionvalue:
					self.setitem(i, True, True, procifselected)
				else:
					self.setitem(i, False, True, procifselected)

		elif conditionid == 1: #Date after
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			for i, j in enumerate(self.files):
				if self.dates[i] > conditionvalue:
					self.setitem(i, True, True, procifselected)
				else:
					self.setitem(i, False, True, procifselected)

		elif conditionid == 2: #No killstreak above condval
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			assigneddata = assignbookmarkdata(self.files, self.bookmarkdata)
			for i, j in enumerate(self.files):
				if assigneddata[i][0] == "":
					self.setitem(i, bool(selifnoinfo), True, procifselected)
					continue
				for k in assigneddata[i][1]:
					if k[0] >= conditionvalue:
						self.setitem(i, True, True, procifselected)
						break
				else:
					self.setitem(i, False, True, procifselected)

		elif conditionid == 3: #Less than condval killstreaks
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			assigneddata = assignbookmarkdata(self.files, self.bookmarkdata)
			for i, j in enumerate(self.files):
				if assigneddata[i][0] == "":
					self.setitem(i, bool(selifnoinfo), True, procifselected)
					continue
				if len(assigneddata[i][1]) < conditionvalue:
					self.setitem(i, True, True, procifselected)
				else:
					self.setitem(i, False, True, procifselected)

		elif conditionid == 4: #Less than condval bookmarks
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			assigneddata = assignbookmarkdata(self.files, self.bookmarkdata)
			for i, j in enumerate(self.files):
				if assigneddata[i][0] == "":
					self.setitem(i, bool(selifnoinfo), True, procifselected)
					continue
				if len(assigneddata[i][2]) < conditionvalue:
					self.setitem(i, True, True, procifselected)
				else:
					self.setitem(i, False, True, procifselected)

		elif conditionid == 5: # Filesize less than condval
			conditionvalue = int(conditionvalue)
			for i, j in enumerate(self.files):
				if self.filesizes[i] < conditionvalue:
					self.setitem(i, True, True, procifselected)
				else:
					self.setitem(i, False, True, procifselected)

		elif conditionid == 6: #Filesize more than condval
			conditionvalue = int(conditionvalue)
			for i, j in enumerate(self.files):
				if self.filesizes[i] > conditionvalue:
					self.setitem(i, True, True, procifselected)
				else:
					self.setitem(i, False, True, procifselected)

		if len(self.selected) != 0: #set select all checkbox
			self.setitem(0, self.selected[0], False, False)

	def getheaders(self, path): #Soon (TM); this function isn't called anywhere.
		result = []
		files = [i for i in os.listdir(path) if os.path.splitext(i)[1] == ".dem"]
		for i in files:
			result.append((i, demheaderreader(i) ) )
		return result

	def selall(self):
		if False in self.selected:
			self.selected = [True for i in self.files]
		else:
			self.selected = [False for i in self.files]
		self.listbox.setcolumn(0, [self.o(i) for i in self.selected])

	def done(self, param):
		if param:
			dialog_ = Deleter(self.master, {"cfg":self.cfg,"files":self.files, "demodir":self.curdir, "selected":self.selected, "keepeventsfile":self.keepevents_var.get(), "deluselessjson":self.deluselessjson_var.get(), "eventfileupdate":"selectivemove"} )
			if dialog_.result_["state"] == 1:
				self.result_["state"] = 1
				self.destroy()
		else:
			self.destroy()

class Deleter(Dialog):
	def __init__(self, parent, options = {}):
		'''Args: parent tkinter window, options dict with:
		demodir, files, selected, keepeventsfile, deluselessjson, cfg
		len(files) = len(selected); selected[x] = True/False; file[n] will be deleted if selected[n] == True'''
		self.master = parent
		self.demodir = options["demodir"]
		self.files = options["files"]
		self.selected = options["selected"]
		self.keepeventsfile = options["keepeventsfile"]
		self.deluselessjson = options["deluselessjson"]
		self.cfg = options["cfg"]

		if "eventfileupdate" in options:
			self.eventfileupdate = options["eventfileupdate"]
		else:
			self.eventfileupdate = "passive"

		self.filestodel = [j for i, j in enumerate(self.files) if self.selected[i]]

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

		self.result_ = {"state":0} #exit state. set to 1 if successful

		super().__init__(parent, "Delete...")

	def buttonbox(self):
		pass

	def body(self, master):
		self.okbutton = tk.Button(master, text = "Delete!", command = lambda: self.confirm(1) )
		self.cancelbutton = tk.Button(master, text= "Cancel", command = self.destroy )

		self.closebutton = tk.Button(master, text="Close", command = self.destroy)

		textframe = tk.Frame(master, pady = 5, padx = 5)

		self.textbox = tk.Text(textframe, wrap = tk.NONE, width = 40, height = 20)
		self.vbar = ttk.Scrollbar(textframe, orient = tk.VERTICAL, command = self.textbox.yview)
		self.vbar.pack(side = tk.RIGHT, fill = tk.Y, expand = 0)
		self.hbar = ttk.Scrollbar(textframe, orient = tk.HORIZONTAL, command = self.textbox.xview)
		self.hbar.pack(side = tk.BOTTOM, anchor = tk.S, fill = tk.X, expand = 0)
		self.textbox.config( **{"xscrollcommand" : self.hbar.set, "yscrollcommand" : self.vbar.set} )
		self.textbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

		self.textbox.delete("0.0", tk.END)
		self.textbox.insert(tk.END, "This operation will delete the following file(s):\n\n" + "\n".join(self.filestodel))
		self.textbox.config(state=tk.DISABLED)

		#self.progbar = ttk.Progressbar(master)

		self.textbox.pack(fill = tk.BOTH, expand = 1)
		textframe.pack(fill = tk.BOTH, expand = 1)

		self.okbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)
		self.cancelbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)

	def confirm(self, param):
		if param == 1:
			#self.progbar.pack(fill=tk.X, )
			self.okbutton.pack_forget()
			self.cancelbutton.pack_forget()

			self.delete()

			self.closebutton.pack(side=tk.LEFT, fill=tk.X, expand=1)

	def delete(self): #TODO: Add stats (time taken, files deleted, write errors encountered?)
		if self.keepeventsfile: #---Backup _events file
			backupfolder = os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"])
			if not os.path.exists(backupfolder):
				os.makedirs(backupfolder)
			i = 0
			while True:
				if os.path.exists( os.path.join(backupfolder, os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt" )  ): #enumerate files: _events0.txt; _events1.txt; _events2.txt ...
					i += 1
				else:
					break
			self.appendtextbox("\n\nCreating eventfile backup at " + os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"], (os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt") ) + " ...\n"  )
			shutil.copy2( os.path.join(self.demodir, _DEF["eventfile"]), os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"], (os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt") )  )

	#-----------Deletion loop-----------#
		errorsencountered = 0
		deletedfiles = 0
		starttime = time.time()
		for i in self.filestodel: #---Delete files
			try:
				os.remove( os.path.join(self.demodir, i))
				deletedfiles += 1
			except BaseException:
				errorsencountered += 1
			self.appendtextbox("\nDeleted " + os.path.join(self.demodir, i) )
	#-----------------------------------#
		
		self.appendtextbox("\n\nUpdating " + _DEF["eventfile"] + "..." )

		evtpath = os.path.join(self.demodir, _DEF["eventfile"])
		tmpevtpath = os.path.join(self.demodir, "."+_DEF["eventfile"])

		if os.path.exists(evtpath):
			reader = handle_ev.EventReader(evtpath, blocksz = self.cfg["evtblocksz"])
			writer = handle_ev.EventWriter(tmpevtpath, clearfile = True)

			if self.eventfileupdate == "passive":
				while True:#NOTE: Could update those to be for loops, but I dont wanna break this
					outchunk = next(reader)
					regres = re.search(_DEF["eventfile_filenameformat"], outchunk.content)
					if regres: curchunkname = regres[0][3:-4] + ".dem"
					else: curchunkname = ""
					if not curchunkname in self.filestodel:#Dilemma: should i create a new list of okay files or basically waste twice the time going through all the .json files?
						writer.writechunk(outchunk)
					if outchunk.message["last"]: break

			elif self.eventfileupdate == "selectivemove":#Requires to have entire dir/actual files present;
				okayfiles = set([j for i, j in enumerate(self.files) if not self.selected[i]])
				while True:
					chunkexists = False
					outchunk = next(reader)
					regres = re.search(_DEF["eventfile_filenameformat"], outchunk.content)
					if regres: curchunkname = regres[0][3:-4] + ".dem"
					else: curchunkname = ""
					if curchunkname in okayfiles:
						okayfiles.remove(curchunkname)
						chunkexists = True
					if chunkexists:
						writer.writechunk(outchunk)
					if outchunk.message["last"]: break
			reader.destroy()
			writer.destroy()

			os.remove(evtpath)
			os.rename(tmpevtpath, evtpath)
			self.appendtextbox(" Done!" )
		else:
			self.appendtextbox(" Event file not found, skipping.")
		self.appendtextbox("\n\n==========\nTime taken: {} seconds\nFiles deleted: {}\nErrors encountered: {}\n==========".format( round(time.time() - starttime, 3), deletedfiles, errorsencountered))

		self.result_["state"] = 1

	def destroy(self):
		self.withdraw()
		self.update_idletasks()
		super().destroy()

	def appendtextbox(self, _inp):
		self.textbox.config(state = tk.NORMAL)
		self.textbox.insert(tk.END, str(_inp) )
		self.textbox.yview_moveto(1.0)
		self.textbox.update()
		self.textbox.config(state = tk.DISABLED)

class Settings(Dialog):
	def __init__(self, parent, cfg):
		'''Variable and dialog setup'''

		self.cfg = cfg

		self.datagrabmode_var = tk.IntVar()
		self.datagrabmode_var.set(cfg["datagrabmode"])
		self.preview_var = tk.BooleanVar()
		self.preview_var.set(cfg["previewdemos"])
		self.steampath_var = tk.StringVar()
		self.steampath_var.set(cfg["steampath"])

		self.datagrabbtns = ( (_DEF["eventfile"], 1), (".json files", 2), ("None", 0) )
		self.blockszvals = dict( [ (convertunit(i,"B") , i) for i in [2**pw for pw in range(12, 28)]] )

		super().__init__( parent, "Settings")


	def destroy(self):
		super().destroy()

	def body(self, master):
		'''UI'''
		datagrab_labelframe = tk.LabelFrame(master, text="Get bookmark information via...", padx=8, pady=8)
		for i, j in self.datagrabbtns:
			b = ttk.Radiobutton(datagrab_labelframe, variable = self.datagrabmode_var, text = i, value = j)
			b.pack()

		preview_labelframe = tk.LabelFrame(master, text="Display", padx=8, pady=8)
		ttk.Checkbutton(preview_labelframe, variable = self.preview_var, text="Preview demos?").pack()

		steampath_labelframe = tk.LabelFrame(master, text="Steam path", padx=8, pady=8)
		self.steampathentry = tk.Entry(steampath_labelframe, state = "readonly", textvariable = self.steampath_var)
		tk.Button(steampath_labelframe, text = "Change...", command = self.choosesteampath).pack(side=tk.RIGHT, fill=tk.X, expand=0)

		eventread_labelframe = tk.LabelFrame(master, text="Read _events.txt in chunks of size...", padx=8, pady=8)
		self.blockszselector = ttk.Combobox(eventread_labelframe, state = "readonly", values = [k for k in self.blockszvals])

		try:
			self.blockszvals[convertunit(self.cfg["evtblocksz"], "B")]
			self.blockszselector.set(convertunit(self.cfg["evtblocksz"], "B"))
		except KeyError:#If evtblocksz has been changed(probably for debug purposes)
			self.blockszselector.set(next(iter(self.blockszvals)))

		preview_labelframe.pack(expand=1, fill = tk.BOTH)

		self.steampathentry.pack(side=tk.LEFT, expand=1, fill=tk.X)
		steampath_labelframe.pack(expand=1, fill = tk.BOTH)

		datagrab_labelframe.pack(expand=1, fill = tk.BOTH)

		self.blockszselector.pack(expand=1, fill = tk.BOTH)
		eventread_labelframe.pack(expand=1, fill = tk.BOTH)

		btconfirm = tk.Button(master, text = "Ok", command = lambda: self.done(1))
		btcancel = tk.Button(master, text="Cancel", command = lambda: self.done(0))

		btconfirm.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)
		btcancel.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		if param:
			self.result = {	"datagrabmode":self.datagrabmode_var.get(),
							"previewdemos":self.preview_var.get(),
							"steampath":self.steampath_var.get(),
							"evtblocksz":self.blockszvals[self.blockszselector.get()]
							}
		else:
			self.result = None
		self.destroy()

	def choosesteampath(self):
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steampath_var.set(sel)

	def buttonbox(self):
		pass#Override buttonbox thing, I'll make my own damn buttons!

class AboutHelp(Dialog):
	def __init__(self, parent):
		self.parent = parent

		super().__init__(parent, "DemoMgr - About / Help")

	def body(self, master):
		mesg = tk.Message(master, text="DemoMgr Version {VER}, created by {AUTHOR}.".format(VER = __version__, AUTHOR = __author__))

		mesg.pack()

	def buttonbox(self):
		pass

	def destroy(self):
		super().destroy()

class MainApp():
	def __init__(self, *args, **kwargs):
		'''Init values, variables, go through startup routine, then show main window.'''

		self.root = tk.Tk()
		self.root.withdraw()

		self.root.bind("<<MultiframeSelect>>", self.__updatedemowindow)
		self.root.bind("<<MultiframeRightclick>>", self.__popupmenu)

		def safestop():#NOTE:without this, the root.destroy method will produce an error on closing, due to some dark magic regarding after commands in self.setstatusbar.
			try: self.root.destroy() #Safe destroy probably better/cleaner than self.root.quit()
			except tk.TclError: pass

		self.root.protocol("WM_DELETE_WINDOW", safestop)

		self.root.wm_title("Demomgr v "+str(__version__))

		self.after_handler = self.root.after(0, lambda: True) #See self.setstatusbar

		if os.path.exists(os.path.join(os.getcwd(), _DEF["iconname"])):
			self.root.iconbitmap(_DEF["iconname"])

		self.workingdir = os.getcwd()
		self.cfgpath = os.path.join(self.workingdir, os.path.join(_DEF["cfgfolder"], _DEF["cfgname"]))
		self.curdir = ""
		self.bookmarkdata = []

		self.spinboxvar = tk.StringVar() 					#spbxv

		self.mainframe = tk.Frame(self.root, padx=5, pady=3)
		self.mainframe.pack(expand = 1, fill = tk.BOTH, side=tk.TOP, anchor = tk.NW)
			#Start execution
		startupres = self.__startup()
		if startupres["res"] == -1:
			tk_msg.showerror("Demomgr - Error","The following error occurred during startup: " + startupres["msg"])
			sys.exit()
		elif startupres["res"] == 1:
			d = FirstRunDialog(self.mainframe)
			if not d.result:
				sys.exit()
			self.cfg["firstrun"] = False
			self.writecfg(self.cfg)

		#set up UI
		self.cfg = self.getcfg()
		self.__setupgui()
		self.spinboxvar.trace("w", self.spinboxsel) 		#spbxv
		if os.path.exists(self.cfg["lastpath"]):
			self.spinboxvar.set(self.cfg["lastpath"])
		elif self.cfg["demopaths"]: 						#spbxv
			self.spinboxvar.set(self.cfg["demopaths"][0])	#spbxv; This will call self.spinboxsel -> self.reloadgui, so the frames are filled.
		self.root.deiconify()#end startup; show UI

	def __startup(self):
		'''Will go through a startup routine, then return a value whether startup was successful, this is first launch etc.'''
		try:
			self.cfg = self.getcfg()
			if self.cfg["firstrun"]:
				return {"res":1, "msg":"Firstlaunch"}
		except FileNotFoundError:
			try:
				os.makedirs(_DEF["cfgfolder"])
				handle = open(self.cfgpath, "w")
				handle.write(json.dumps(_DEF["defaultcfg"], indent = 4))
				handle.close()
				self.cfg = _DEF["defaultcfg"]
			except BaseException as _exception:
				return {"res":-1, "msg":str(_exception)}
			return {"res":1, "msg":"Firstlaunch"}
		except json.decoder.JSONDecodeError:
			return {"res":-1,"msg":"Config Corrupted, please delete ~/{}/{}".format(_DEF["cfgfolder"] ,_DEF["cfgname"])}
		return {"res":0, "msg":"Success."}

	def __setupgui(self):
		'''Sets up UI inside of the self.mainframe widget'''
		self.filterentry_var = tk.StringVar()

		widgetframe0 = tk.Frame(self.mainframe)
		widgetframe1 = tk.Frame(self.mainframe)
		widgetframe2 = tk.Frame(self.mainframe)
		widgetframe3 = tk.Frame(self.mainframe) #Buttons here interact with the currently selected demo
		self.listboxframe = tk.Frame(self.mainframe)
		demoinfframe = tk.Frame(self.mainframe, padx=5, pady=5)
		self.statusbar = tk.Frame(self.mainframe)

		self.listbox = mfl.Multiframe(self.listboxframe, columns=4, names=["Filename","Bookmarks?","Date created","Filesize"], sort = 2, sorters=[True,False,True,True], widths = [None, 26, 16, 10], formatters = [None, None, formatdate, convertunit])

		self.pathsel_spinbox = ttk.Combobox(widgetframe0, state = "readonly")
		self.pathsel_spinbox.config(values = tuple(self.cfg["demopaths"]))
		self.pathsel_spinbox.config(textvariable = self.spinboxvar)

		rempathbtn = tk.Button(widgetframe0, text = "Remove demo path", command = self.rempath)
		addpathbtn = tk.Button(widgetframe0, text = "Add demo path...", command = self.addpath)
		settingsbtn = tk.Button(widgetframe0, text = "Settings...", command = self.opensettings)
		abouthelpbtn = tk.Button(widgetframe0, text = "About/Help...", command = self.showabout)

		self.demoinfbox = tk_scr.ScrolledText(demoinfframe, wrap = tk.WORD, state=tk.DISABLED, width = 40)
		self.demoinflabel = tk.Label(demoinfframe, text=_DEF["demlabeldefault"])

		filterlabel = tk.Label(widgetframe1, text="Filter demos: ")
		filterentry = tk.Entry(widgetframe1, textvariable=self.filterentry_var)
		filterbtn = tk.Button(widgetframe1, text="Apply Filter", command = self.__filter)
		clearfilterbtn = tk.Button(widgetframe1, text="Clear filter", command = self.reloadgui)

		cleanupbtn = tk.Button(widgetframe2, text="Cleanup...", command = self.__cleanup)

		playdemobtn = tk.Button(widgetframe3, text="Play selected demo...", command = self.__playdem)
		deldemobtn = tk.Button(widgetframe3, text="Delete selected demo...", command = self.__deldem)

		self.statusbarlabel = ttk.Label(self.statusbar, text="Ready.")

		# self.dem = tk.PhotoImage(file = "bloll.png")
		# self.demlbl = tk.Label(self.mainframe, image=self.dem)
		# self.demlbl.photo = self.dem
		# self.demlbl.pack(expand=1, fill = tk.BOTH)
		# self.demlbl.bind("<Button-1>", self.startwooh)

		#pack
		self.statusbarlabel.pack(anchor=tk.W)
		self.statusbar.pack(fill=tk.X, expand=0, side=tk.BOTTOM)

		#widgetframe0
		self.pathsel_spinbox.pack(side=tk.LEFT, fill = tk.X, expand = 1)
		rempathbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		addpathbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		tk.Label(widgetframe0, text="", width=3).pack(side=tk.LEFT) #Placeholder
		settingsbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		tk.Label(widgetframe0, text="", width=3).pack(side=tk.LEFT) #Placeholder
		abouthelpbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)

		widgetframe0.pack(anchor = tk.N, fill = tk.X, pady = 5, padx = 3)

		#widgetframe1
		filterlabel.pack(side = tk.LEFT, fill = tk.X, expand=0)
		filterentry.pack(side = tk.LEFT, fill = tk.X, expand=1)
		filterbtn.pack(side = tk.LEFT, fill = tk.X, expand=0)
		clearfilterbtn.pack(side = tk.LEFT, fill = tk.X, expand=0)

		widgetframe1.pack(anchor = tk.N, fill = tk.X, pady = 5)

		#widgetframe2
		cleanupbtn.pack(side = tk.LEFT, fill = tk.X, expand=0)

		widgetframe2.pack(anchor = tk.N, fill = tk.X, pady = 5)

		#widgetframe3
		playdemobtn.pack(side = tk.LEFT, fill = tk.X, expand=0)
		tk.Label(widgetframe3, text="", width=3).pack(side=tk.LEFT) #Placeholder
		deldemobtn.pack(side = tk.LEFT, fill = tk.X, expand=0)
		widgetframe3.pack(anchor = tk.N, fill = tk.X, pady = 5)

		self.listbox.pack(fill=tk.BOTH, expand=1)
		self.listboxframe.pack(fill=tk.BOTH, expand = 1, side = tk.LEFT)

		self.demoinflabel.pack(fill=tk.BOTH, expand = 0, anchor= tk.W)
		self.demoinfbox.pack(fill=tk.BOTH, expand = 1)
		demoinfframe.pack(fill=tk.BOTH, expand = 1)

	def __cleanup(self):
		'''Opens dialog offering demo deletion'''
		if self.curdir == "":
			return
		try:
			files = [i for i in os.listdir(self.curdir) if os.path.splitext(i)[1] == ".dem" and (os.path.isfile(os.path.join(self.curdir, i)))]
		except BaseException:
			return
		dialog_ = DeleteDemos(self.mainframe, **{"cfg":self.cfg, "curdir":self.curdir, "bookmarkdata":self.bookmarkdata, "files":files, "dates":[os.stat(os.path.join(self.curdir, i)).st_mtime for i in files], "filesizes":[os.stat(os.path.join(self.curdir, i)).st_size for i in files] } )
		if dialog_.result_["state"] == 1:
			self.reloadgui()

	def __playdem(self):
		'''Opens dialog which confirms tf2 launch'''
		index = self.listbox.getindex()
		if index == None:
			self.setstatusbar("Please select a demo file.",1500)
			return
		filename = self.listbox.getcell(0, index)
		path = os.path.join(self.curdir, filename)
		if os.path.splitext(path)[1] != ".dem":
			return
		dialog_ = LaunchTF2(self.mainframe, {"demopath":path ,"steamdir":self.cfg["steampath"]} )
		if "steampath" in dialog_.result_:
			if dialog_.result_["steampath"] != self.cfg["steampath"]:
				self.cfg["steampath"] = dialog_.result_["steampath"]
				self.writecfg(self.cfg)
				self.cfg = self.getcfg()

	def __deldem(self):
		"""Deletes the currently selected demo"""
		index = self.listbox.getindex()
		if index == None:
			self.setstatusbar("Please select a demo file.",1500)
			return
		filename = self.listbox.getcell(0, index)
		_dialog = Deleter(self.root, {"cfg":self.cfg, "files":[filename] ,"selected": [True], "demodir":self.curdir, "keepeventsfile": False, "deluselessjson":False} )
		if _dialog.result_["state"] == 1:
			self.reloadgui()

	def __updatedemowindow(self, _):
		'''Renew contents of demo information window'''
		index = self.listbox.getindex()
		if index == None:
			return
		if not self.cfg["previewdemos"]:
			self.demoinflabel.config(text="Preview window")
			self.demoinfbox.config(state=tk.NORMAL)
			self.demoinfbox.delete("0.0", tk.END)
			self.demoinfbox.insert(tk.END, "(Preview disabled)")
			self.demoinfbox.config(state=tk.DISABLED)
			return
		try:
			demname = self.listbox.getcell(0, index)	#Get headerinf
			outdict = demheaderreader(os.path.join(self.curdir, demname))
			deminfo = "\n".join([str(k) + " : " + str(outdict[k]) for k in outdict])
			del outdict #End headerinf
			entry = None	#Get bookmarks
			for i in self.bookmarkdata:
				if i[0] == demname:
					entry = i
					break
			if entry == None:
				demmarks = "\n\nNo bookmark information found."
			else:
				demmarks = "\n\n"
				for i in entry[1]:
					demmarks += (str(i[0]) + " streak at " + str(i[1]) +"\n")
				demmarks += "\n"
				for i in entry[2]:
					demmarks += ("\"" + str(i[0]) + "\" bookmark at " + str(i[1]) +"\n")#End bookmarks
		except BaseException:
			demname = "?"
			deminfo = "Error reading demo; file is likely corrupted :("
			demmarks = "\n\nNo bookmark information found."
		self.demoinflabel.config(text="Info for " + demname)
		self.demoinfbox.config(state=tk.NORMAL)
		self.demoinfbox.delete("0.0", tk.END)
		self.demoinfbox.insert(tk.END, deminfo)
		if demmarks:
			self.demoinfbox.insert(tk.END, demmarks)
		self.demoinfbox.config(state=tk.DISABLED)

	def __popupmenu(self, event):
		'''Opens a popup menu at mouse pos'''
		clickedlist = self.listbox.getrowindex()
		clickx, clicky = self.listbox.getlastclick()
		listboxx, listboxy = self.listboxframe.winfo_rootx(), self.listboxframe.winfo_rooty()
		#get coords to create the menu on
		menu = tk.Menu(self.mainframe, tearoff = 0)
		menu.add_command(label = "Play", command = self.__playdem)
		menu.add_command(label = "Delete", command = self.__deldem)#construct menu
		menu.post(self.listbox.frames[clickedlist][0].winfo_rootx() + clickx, self.listbox.frames[clickedlist][0].winfo_rooty() + clicky + 20) #20 is label height. I hope that won't change.

	def setstatusbar(self, data, timeout=None):
		'''Set statusbar text to data (str)'''
		self.statusbarlabel.after_cancel(self.after_handler)
		self.statusbarlabel.config(text=str(data))
		self.statusbarlabel.update()
		if timeout:
			self.after_handler = self.statusbarlabel.after(timeout, lambda: self.setstatusbar(_DEF["statusbardefault"]) )

	def reloadgui(self):
		'''Reload UI elements that need it'''
		self.listbox.setdata(self.fetchdata(), "column")
		self.listbox.format()
		self.__updatedemowindow(None)

	def fetchdata(self):
		'''Get data from all the demos in current folder; return in format that can be directly put into listbox'''
		if self.curdir == "":
			return ((),(),(),())
		self.setstatusbar("Reading demo information from " + self.curdir)
		starttime = time.time()
		try:
			files = [i for i in os.listdir(self.curdir) if (os.path.splitext(i)[1] == ".dem") and (os.path.isfile(os.path.join(self.curdir, i)))]
		except FileNotFoundError:
			self.setstatusbar("ERROR: Current directory \"" + self.curdir + "\" does not exist.")
			return ((),(),(),())
		datescreated = [os.path.getmtime(os.path.join(self.curdir, i)) for i in files]
		sizes = [os.path.getsize(os.path.join(self.curdir, i)) for i in files]
		datamode = self.cfg["datagrabmode"]
		if datamode == 0:
			data = (files, ["" for i in files], datescreated, sizes)
			self.setstatusbar("Bookmark information disabled.", 2000)
			return data
		elif datamode == 1: #_events.txt
			try:
				h = open(os.path.join(self.curdir, _DEF["eventfile"]))
			except FileNotFoundError:
				self.setstatusbar("\"" + _DEF["eventfile"] +"\" has not been found.",1500)
				return ((files, ["" for i in files], datescreated, sizes))
			self.bookmarkdata = readevents(h, self.cfg["evtblocksz"])
			h.close()
		elif datamode == 2: #.json
			jsonfiles = [i for i in os.listdir(self.curdir) if os.path.splitext(i)[1] == ".json" and os.path.exists(os.path.join(self.curdir, os.path.splitext(i)[0] + ".dem"))]
			worklist = []
			for i, j in enumerate(jsonfiles):
				worklist.append([os.path.splitext(j)[0] + ".dem", [], []])
				h = open(os.path.join(self.curdir, j))
				rawdata = json.load(h)["events"] #{"name":"Killstreak/Bookmark","value":"int/Name","tick":"int"}
				h.close()
				for k in rawdata:
					if k["name"] == "Killstreak":
						worklist[i][1].append((int(k["value"]),int(k["tick"])))
					elif k["name"] == "Bookmark":
						worklist[i][2].append((k["value"],int(k["tick"])))

				killstreaks = worklist[i][1]
				streakpeaks = [] #convert to streakpeaks
				if killstreaks == []:
					pass
				else:
					killstreaks.append((-1,-1))
					prv = (-1, -1)
					for l in killstreaks:
						if l[0]<=prv[0]:
							streakpeaks.append(prv)
						prv = l
				worklist[i][1] = streakpeaks

			self.bookmarkdata = worklist

		listout = formatbookmarkdata(files, self.bookmarkdata) #format the bookmarkdata into something that can be directly fed into listbox

		data = ( files, listout, datescreated, sizes )
		self.setstatusbar("Processed data from " + str( len(files) ) + " files in " + str(round(time.time() - starttime, 4)) + " seconds.", 3000)
		return data

	def __filter(self):
		'''Filters the listbox according to conditions in self.filterentry_var'''
		try:
			raw = self.filterentry_var.get() #Get and handle input
			#Sanitize
			raw = escapeinput(raw)#Protect from escapes/injections on the eval() level
			raw = raw.split(",")
			raw = [i.strip() for i in raw]
			params = [ [i.split(":")[0], [i.split(_DEF["filterkeysep"])[1].split(_DEF["filterparamsep"]), False] ] for i in raw]
			del raw
			for i, j in enumerate(params):
				if j[0][0] == _DEF["filterneg"]:
					params[i][0] = j[0][len(_DEF["filterneg"]):]
					params[i][1][1] = True
			conddict = dict(params)
			del params
		except BaseException:
			self.setstatusbar("Invalid filter parameter format",3000)
			return
		starttime = time.time()

		self.setstatusbar("Constructing filters...")
		filters = []
		try:
			for k in conddict:
				isneg = conddict[k][1]
				filters.append(eval("lambda x: {}{}{}".format(	"not (" * isneg,
																" or ".join(_DEF["filterdict"][k][0].format( _DEF["filterdict"][k][1]( i ) ) for i in conddict[k][0]),
																")" * isneg) 
									)  )#Construct lambdas for the user-entered conditions
		except KeyError:
			self.setstatusbar("Invalid filtering key: \"" + str(k) + "\" ; please check your input.",5000)
			return
		except ValueError:
			self.setstatusbar("Invalid filtering parameter: \""+ conddict[k] +"\" ; please check your input.",5000)
			return

		FILES = self.fetchdata()[0] #Function will modify self.bookmarkdata
		asg_bmd = assignbookmarkdata(FILES, self.bookmarkdata)
		filteredlist = []

		for i, j in enumerate(FILES): #Filter
			curdemook = True
			curdataset = {"name":j, "killstreaks":asg_bmd[i][1], "bookmarks":asg_bmd[i][2], "header": HeaderFetcher(os.path.join(self.curdir, j)), "filedata": FileStatFetcher(os.path.join(self.curdir, j))}
			#The Fetcher classes prevent unneccessary drive access when the user i.E. only filters by name
			for l in filters:
				if not l(curdataset):
					curdemook = False
					break
			if curdemook:
				filteredlist.append((curdataset["name"], str(len(curdataset["bookmarks"])) + " Bookmarks; "+ str(len(curdataset["killstreaks"])) + " Killstreaks.", curdataset["filedata"]["modtime"], curdataset["filedata"]["filesize"]))
		del filters

		self.listbox.setdata(filteredlist, "row")
		self.listbox.format()
		self.setstatusbar("Filtered {} demos in {} seconds.".format( str(len(FILES)), str(round(time.time() - starttime, 3)) ), 3000)

	def spinboxsel(self, *args):
		'''Observer callback to self.spinboxvar; is called whenever self.spinboxvar (so the combobox) is updated. Also implicitly called from self.rempath'''
		selpath = self.spinboxvar.get()
		if not selpath == self.curdir:
			if os.path.exists(selpath) and self.cfg["lastpath"] != selpath: #Update lastpath entry
				localcfg = 	self.cfg#Other functions continue to inform user that directory does not exist.
				localcfg["lastpath"] = selpath
				self.writecfg(localcfg)
				self.cfg = self.getcfg()
			self.curdir = selpath
			self.reloadgui()

	def showabout(self): #TODO: Help/About window
		dialog_ = AboutHelp(self.mainframe)

	def opensettings(self):
		'''Opens settings, acts based on results'''
		dialog_ = Settings(self.mainframe, self.getcfg())
		if dialog_.result:
			localcfg = self.cfg
			localcfg.update(dialog_.result)
			self.writecfg(localcfg)
			self.cfg = self.getcfg()
			self.reloadgui()

	def addpath(self):
		'''Adds a demo folder path and writes to config after validating'''
		dirpath = tk_fid.askdirectory(initialdir = "C:\\", title = "Select the folder containing your demos.")
		if dirpath == "":
			return
		localcfg = self.cfg
		localcfg["demopaths"].append(dirpath)
		self.writecfg(localcfg)
		self.cfg = self.getcfg()
		self.spinboxvar.set(dirpath)
		self.pathsel_spinbox.config(values = tuple(self.cfg["demopaths"]))
		self.reloadgui()

	def rempath(self):
		localcfg = self.cfg
		if len(localcfg["demopaths"]) == 0:
			return
		popindex = localcfg["demopaths"].index(self.curdir)
		localcfg["demopaths"].pop(popindex)
		if len(localcfg["demopaths"]) > 0:
			self.spinboxvar.set(localcfg["demopaths"][(popindex -1) % len(localcfg["demopaths"])])
		else:
			self.spinboxvar.set("")
		self.pathsel_spinbox.config(values = tuple(localcfg["demopaths"]))
		self.writecfg(self.cfg)
		self.cfg = self.getcfg()

	def writecfg(self, data):
		'''Writes config specified in data to self.cfgpath'''
		handle = open(self.cfgpath, "w")
		handle.write(json.dumps(data, indent=4))#NOTE:Unnecessary, maybe remove eventually.
		handle.close()

	def getcfg(self):
		'''Gets config from self.cfgpath and returns it'''
		localcfg = _DEF["defaultcfg"]
		with open(self.cfgpath, "r") as handle:
			localcfg.update(json.load(handle))
		return localcfg

if __name__ == "__main__":
	mainapp = MainApp() #TODO: log potential errors to .demomgr/err.log
	mainapp.root.mainloop()
