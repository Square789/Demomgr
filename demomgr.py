#!/usr/bin/env python3
#Demomgr
#Created by Square789 (c) 2018 - 2019
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
sys.path.append(os.getcwd())
try:
	import multiframe_list as mfl
except ModuleNotFoundError:
	tk_msg.showerror("demomgr - Error","Please place the \"multiframe_list.py\"-file next to the script.")
	quit()

__version__ = 0.1
__author__ = "Square789"

_DEF = {	"cfgfolder":".demomgr",
			"cfgname":"config.cfg",
			"iconname":"demmgr.ico",
			"defaultcfg":	{	"demopaths":[],
								"firstrun":True,
								"__comment":"By messing with the firstrun parameter you acknowledge that you've read the Terms of use.",
								"datagrabmode":0,
								"previewdemos":True,
								"steampath":"",
								"evtblocksz":65536
							},
			"eventbackupfolder":"_eventbackup",
			"WELCOME":"Hi and Thank You for using DemoManager!\n\nA config file has been created in a folder next to the script.\n\nThis script is able to delete files if you tell it to.\nI in no way guarantee that this script is safe or 100% reliable and will not take any responsibility for lost data, damaged drives and/or destroyed hopes and dreams. If something goes wrong, data recovery tools are a thing.",
			"eventfile":"_events.txt",#If this name should for whatever reason change at some point, change this variable
			"dateformat":"%d.%m.%Y  %H:%M:%S",
			"eventfile_filenameformat":" \\(\".+\" at",#regex
			"eventfile_bookmark":"Bookmark",
			"eventfile_killstreak":"Killstreak",
			"eventfile_ticklogsep":" at \\d+\\)",#regex
			"eventfile_argident":" [a-zA-Z0-9]+ \\(",#regex
			"eventfile_readsize":65536,
			"eventreadlimit":1000,
			"demlabeldefault":"No demo selected.",
			"statusbardefault":"Ready.",
			"tf2exepath":"steamapps/common/team fortress 2/hl2.exe",
			"tf2headpath":"steamapps/common/team fortress 2/tf/",
			"steamconfigpath1":"userdata/",
			"steamconfigpath2":"config/localconfig.vdf",
			"launchoptionskey":"[\"UserLocalConfigStore\"][\"Software\"][\"Valve\"][\"Steam\"][\"Apps\"][\"440\"][\"LaunchOptions\"]"
		}	#Values. Is important. No changerooni.

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

	return demhdr

def extracttick(ticklog):
	'''Takes the parentheses and stuff out ("XXXXXX" at 00000) and extracts that delicious tick number.'''
	regres = re.search(_DEF["eventfile_ticklogsep"], ticklog)
	#whatever is fed in is likely correct, so no validation
	numlen = (len(regres[0]) - 5)
	tick = ticklog[-numlen - 1:-1]
	return tick

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
		return None
	if filenamesearch:
		filename = filenamesearch[0][3:-4] + ".dem"
	else:
		return None

	#if the code reached this point, file name is present

	killstreaks = []
	bookmarks = []

	for i in loglines: #for each line in the feed
		if i == "": #Line empty, likely last line.
			continue
		tick = extracttick(i)#Get the tick.
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
	#streakpeaks now contains the top values of recorded killstreaks.
	# print("===FILENAME===")
	# print(filename)
	# print("  STREAKTOPS")
	# print(streakpeaks)
	# print("  BOOKMARKS")
	# print(bookmarks)
	# print("==============\n")
	return (filename, streakpeaks, bookmarks) #there he is

def readevents(handle, blocksz):
	'''This function reads an events.txt file as it's written by the source engine, returns (filename, ( (killstreakpeak, tick)... ), ( (bookmarkname, tick)... ) )'''
	lastchunk = ""
	out = []
	raw = "_"
	done = False
	fail = True
	ii = 0
	while True:
		raw = lastchunk + handle.read(blocksz)
		if ((len(raw)) < blocksz):
			done = True
			fail = False
		logchunks = raw.split(">\n")
		lastchunk = logchunks.pop(-1)
		if len(lastchunk) == blocksz:
			continue
		handle.seek(handle.tell() - len(lastchunk))
		for i in logchunks:
			out.append(convertlogchunks(i))
		if done:
			break
		lastchunk = ""
	if not fail:
		out.append(convertlogchunks(lastchunk))
	return out, fail

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

class FirstRunDialog(Dialog):
	def __init__(self, parent = None):
		if not parent:
			parent = tk._default_root
		Dialog.__init__(self, parent, "Welcome!")

	def destroy(self):
		Dialog.destroy(self)

	def body(self, master):
		self.txtbox = tk_scr.ScrolledText(master, wrap = tk.WORD)
		self.txtbox.insert(tk.END,_DEF["WELCOME"])
		self.txtbox.config(state = tk.DISABLED)

		self.txtbox.pack(expand=0, fill = tk.X)

		self.btconfirm = tk.Button(master, text = "I am okay with that and I accept.", command = lambda: self.done(1))
		self.btcancel = tk.Button(master, text="Cancel!", command = lambda: self.done(0))

		self.btconfirm.pack(side = tk.LEFT, anchor = tk.W, expand=1, fill = tk.X)
		self.btcancel.pack(side = tk.LEFT, anchor = tk.E, expand=1, fill = tk.X)

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		self.result = param
		self.destroy()

	def buttonbox(self):
		pass#Override buttonbox thing, I'll make my own damn buttons!

class LaunchTF2(Dialog):
	def __init__(self, parent, demopath, steamdir = ""):

		self.results = {}

		self.demopath = demopath
		self.steamdir = tk.StringVar()
		self.steamdir.set(steamdir)

		try:
			self.shortdemopath = os.path.relpath(self.demopath, os.path.join(steamdir,_DEF["tf2headpath"]))
		except ValueError:
			tk_msg.showwarning("demoMgr - Error", "Steam directory not on same drive as target directory.")
			return
			
		self.playdemoarg = tk.StringVar()
		self.playdemoarg.set("+playdemo " + self.shortdemopath)

		self.userselectvar = tk.StringVar()
		self.userselectvar.set(self.getusers()[0])

		self.launchoptionsvar = tk.StringVar()

		Dialog.__init__(self, parent, "Play demo / Launch TF2...")

	def body(self, master):
		'''Ugly UI setup'''
		self.steamdirframe= tk.LabelFrame(master, text="Steam install path", padx = 10, pady=8)
		self.steamdirentry = tk.Entry(self.steamdirframe, state="readonly", textvariable = self.steamdir)
		self.steamdirbtn = tk.Button(self.steamdirframe, command=self.askfordir, text="Select Steam install path")

		self.userselectframe = tk.LabelFrame(master, text="Select user profile if needed", padx = 10, pady=8)
		self.userselectspinbox = tk.Spinbox(self.userselectframe, textvariable = self.userselectvar, values=self.getusers(), state="readonly")#Once changed, observer callback will be triggered by self.userselectvar

		self.launchoptionsframe = tk.LabelFrame(master, text="Launch options:", padx = 10, pady=8)
		self.launchoptionswarning = tk.Label(self.launchoptionsframe, fg="#AA0000", text="Please install the vdf module in order to launch TF2 with your default settings. (Run cmd in admin mode; type \"python -m pip install vdf\")")
		self.launchlabel1 = tk.Label(self.launchoptionsframe, text="[...]/hl2.exe -steam -game tf")
		self.launchoptionsentry = tk.Entry(self.launchoptionsframe, textvariable=self.launchoptionsvar)
		self.launchlabelentry = tk.Entry(self.launchoptionsframe, state="readonly", textvariable = self.playdemoarg)

		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)

		#pack start
		self.steamdirentry.pack(fill=tk.BOTH,expand=1)
		self.steamdirbtn.pack(fill=tk.BOTH,expand=1)
		self.steamdirframe.pack(fill=tk.BOTH, expand=1)

		self.userselectspinbox.pack(fill=tk.BOTH,expand=1)
		self.userselectframe.pack(fill=tk.BOTH, expand=1)

		self.launchoptionswarning.pack(side=tk.TOP,expand=0)
		self.launchoptionswarning.pack()
		self.launchlabel1.pack(side=tk.LEFT,fill=tk.Y,expand=0)
		self.launchoptionsentry.pack(side=tk.LEFT,fill=tk.BOTH,expand=1)
		self.launchlabelentry.pack(side=tk.LEFT,fill=tk.BOTH,expand=0)
		self.launchoptionsframe.pack(fill=tk.BOTH,expand=1)

		self.btconfirm = tk.Button(master, text = "Launch!", command = lambda: self.done(1))
		self.btcancel = tk.Button(master, text="Cancel", command = lambda: self.done(0))

		self.btconfirm.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)
		self.btcancel.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)
		self.userchange()

		self.userselectvar.trace("w", self.userchange)#If applied before, method would be triggered and UI elements would be accessed that do not exist yet.

	def getusers(self):
		'''Executed once by body()'''
		toget = os.path.join(self.steamdir.get(), _DEF["steamconfigpath1"])
		if not os.path.exists(toget):
			tk_msg.showerror("DemoMgr - Error","Steam directory malformed / does not exist.")
			self.destroy()
		return os.listdir(toget)

	def getlaunchoptions(self):
		try:
			import vdf
			h = open(os.path.join(os.path.join(os.path.join(self.steamdir.get(), _DEF["steamconfigpath1"]), self.userselectvar.get()), _DEF["steamconfigpath2"]) )
			launchopt = vdf.load(h)
			h.close()
			launchopt = eval("launchopt" + _DEF["launchoptionskey"])
			self.launchoptionswarning.config(text="")
			return launchopt
		except ModuleNotFoundError:
			self.launchoptionswarning.config(text="Please install the vdf (Valve Data Format) module in order to launch TF2 with your default settings. (Run cmd in admin mode; run \"python -m pip install vdf\")")
			return ""
		except FileNotFoundError:
			return ""

	def userchange(self, *_):#Triggered by User selection spinbox -> self.userselectvar
		launchopt = self.getlaunchoptions()
		self.launchoptionsentry.delete(0, tk.END)
		self.launchoptionsentry.insert(tk.END, launchopt)

	def askfordir(self):
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steamdir.set(sel)
		self.steamdirentry.config(state=tk.ACTIVE)
		self.steamdirentry.set(self.steamdir.get())
		self.steamdirentry.config(state="readonly")
		self.shortdemopath = os.path.relpath(self.demopath, os.path.join(self.steamdir.get(),_DEF["tf2headpath"]))
		self.playdemoarg.set("+playdemo " + self.shortdemopath)
		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)

	def done(self, param):
		if param:
			executable = os.path.join(self.steamdir.get(), _DEF["tf2exepath"])
			launchopt = self.launchoptionsentry.get()
			launchopt = launchopt.split(" ")
			launchoptions = [executable, "-steam", "-game", "tf"] + launchopt
			launchoptions.append("+playdemo")
			launchoptions.append(self.shortdemopath)
			subprocess.Popen(launchoptions) #Launch tf2; -steam param may cause conflicts when steam is not open but what do I know?
			self.results = {"steampath":self.steamdir.get()}
		self.destroy()

	def buttonbox(self):
		pass

	def destroy(self):
		Dialog.destroy(self)

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

		self.combobox_var = tk.StringVar()

		self.selected = [False for i in self.files]

		self.CND = {#"Map name": -1,
					"Date before":{"id":0, "cond":None},
					"Date after":{"id":1, "cond":None},
					"No killstreak above":{"id":2, "cond":None},
					"Less than <> killstreaks":{"id":3, "cond":None},
					"Less than <> bookmarks":{"id":4, "cond":None},
					"Filesize below":{"id":5, "cond":None},
					"Filesize above":{"id":6, "cond":None} #condition dict
					}
		
		Dialog.__init__(self, parent, "Delete...")

	def body(self, master):
		'''UI'''
		master.bind("<<MultiframeSelect>>", self.procitem) #on select, process item selected.

		okbutton = tk.Button(master, text = "Delete", command = lambda: self.done(1) )
		cancelbutton = tk.Button(master, text= "Cancel", command = lambda: self.done(0) )

		self.listbox = mfl.Multiframe(master, columns = 5, names= ["","Name","Date created","Info","Filesize"], sort = 0, formatters = [None, None, formatdate, None, convertunit], widths = [2, None, 18, 25, 15])
		self.listbox.setdata( ([self.o(i) for i in self.selected], self.files, self.dates, formatbookmarkdata(self.files, self.bookmarkdata), self.filesizes) , mfl.COLUMN)
		self.listbox.format()

		self.demoinfbox = tk.Label(master, justify = tk.LEFT)

		self.listbox.frames[0][2].pack_propagate(False) #looks weird, is sloppy, will probably lead to problems at some point. change parent to master if problems occur and comment out this line
		self.selall_checkbtn = ttk.Checkbutton(self.listbox.frames[0][2], variable=self.selall_var, text="", command = self.selall) # ''

		self.optframe = tk.LabelFrame(master, text="Options...", pady=3, padx=8)
		self.keepevents_checkbtn = ttk.Checkbutton(self.optframe, variable = self.keepevents_var, text = "Make backup of " + _DEF["eventfile"])
		self.deljson_checkbtn = ttk.Checkbutton(self.optframe, variable = self.deluselessjson_var, text = "Delete orphaned json files")

		self.condframe = tk.LabelFrame(master, text="Demo selector [Incomplete feature]", pady=3, padx=8)
		self.condbox = ttk.Combobox(self.condframe, state = "readonly", values = [i for i in self.CND]) #CND keys are values.
		self.condbox.set(next(iter(self.CND)))#dunno what this does, stole it from stackoverflow, seems to work.
		self.condvalbox = tk.Entry(self.condframe) #
		self.applybtn = tk.Button(self.condframe, text="Apply selection", command = self.applycond)
		selifnobookmarks_checkbox = ttk.Checkbutton(self.condframe, text="Select when no information on condition is found", variable = self.selifnobookmarkdata_var)

		selifnobookmarks_checkbox.pack(anchor = tk.SW, side=tk.BOTTOM)
		self.applybtn.pack(side=tk.RIGHT)
		tk.Label(self.condframe).pack(side=tk.RIGHT)
		self.condvalbox.pack(side=tk.RIGHT, fill=tk.X, expand=1)
		tk.Label(self.condframe).pack(side=tk.RIGHT)
		self.condbox.pack(side=tk.RIGHT, fill=tk.X, expand=1)
		self.condframe.pack(fill=tk.BOTH)

		self.deljson_checkbtn.pack(side=tk.LEFT)
		self.keepevents_checkbtn.pack(side=tk.LEFT)
		self.optframe.pack(fill=tk.BOTH)

		self.selall_checkbtn.pack(side=tk.LEFT, anchor=tk.W)

		self.listbox.pack(side=tk.TOP,fill=tk.BOTH, expand=1)

		self.demoinfbox.pack(side=tk.BOTTOM, fill = tk.BOTH, expand = 0)

		okbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)
		cancelbutton.pack(side=tk.LEFT, fill=tk.X,expand=1)

	def buttonbox(self):
		pass

	def destroy(self):
		Dialog.destroy(self)

	def procitem(self, event):
		index = self.listbox.getindex()
		if self.listbox.getrowindex() != 0: return
		if index == None: return
		self.selected[index] = not self.selected[index]
		if False in self.selected:
			self.selall_var.set(0)
		else:
			self.selall_var.set(1)
		self.listbox.setcell(0, index, self.o(self.selected[index]))

	def setitem(self, index, value, ignorecheckbox = False): #value: bool
		self.selected[index] = value
		if not ignorecheckbox:
			if False in self.selected: #~ laggy
				self.selall_var.set(0)
			else:
				self.selall_var.set(1)
		self.listbox.setcell(0, index, self.o(self.selected[index]))

	def o(self, _in):
		return " " if not _in else " X"

	def applycond(self):
		'''Apply user-entered condition to the files. True spaghetti code.'''
		conditionname = self.condbox.get()
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
					self.setitem(i, True, True)
				else:
					self.setitem(i, False, True)

		elif conditionid == 1: #Date after
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			for i, j in enumerate(self.files):
				if self.dates[i] > conditionvalue:
					self.setitem(i, True, True)
				else:
					self.setitem(i, False, True)

		elif conditionid == 2: #No killstreak above condval
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			assigneddata = assignbookmarkdata(self.files, self.bookmarkdata)
			for i, j in enumerate(self.files):
				if assigneddata[i][0] == "":
					self.setitem(i, bool(selifnoinfo), True)
					continue
				for k in assigneddata[i][1]:
					if k[0] >= conditionvalue:
						self.setitem(i, True, True)
						break
				else:
					self.setitem(i, False, True)

		elif conditionid == 3: #Less than condval killstreaks
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			assigneddata = assignbookmarkdata(self.files, self.bookmarkdata)
			for i, j in enumerate(self.files):
				if assigneddata[i][0] == "":
					self.setitem(i, bool(selifnoinfo), True)
					continue
				if len(assigneddata[i][1]) < conditionvalue:
					self.setitem(i, True, True)
				else:
					self.setitem(i, False, True)

		elif conditionid == 4: #Less than condval bookmarks
			conditionvalue = int(conditionvalue)
			selifnoinfo = self.selifnobookmarkdata_var.get()
			assigneddata = assignbookmarkdata(self.files, self.bookmarkdata)
			for i, j in enumerate(self.files):
				if assigneddata[i][0] == "":
					self.setitem(i, bool(selifnoinfo), True)
					continue
				if len(assigneddata[i][2]) < conditionvalue:
					self.setitem(i, True, True)
				else:
					self.setitem(i, False, True)

		elif conditionid == 5: # Filesize less than condval
			conditionvalue = int(conditionvalue)
			for i, j in enumerate(self.files):
				if self.filesizes[i] < conditionvalue:
					self.setitem(i, True, True)
				else:
					self.setitem(i, False, True)

		elif conditionid == 6: #Filesize more than condval
			conditionvalue = int(conditionvalue)
			for i, j in enumerate(self.files):
				if self.filesizes[i] > conditionvalue:
					self.setitem(i, True, True)
				else:
					self.setitem(i, False, True)

		if len(self.selected) != 0: #set select all checkbox
			self.setitem(0, self.selected[0], False)

	def getheaders(self, path): #Soon (TM); this function isn't called anywhere.
		result = []
		files = [i for i in os.listdir(path) if os.path.splitext(i)[1] == ".dem"]
		for i in files:
			result.append( (i, demheaderreader(i) ) )
		return result

	def selall(self):
		if False in self.selected:
			self.selected = [True for i in self.files]
		else:
			self.selected = [False for i in self.files]
		self.listbox.setcolumn(0, [self.o(i) for i in self.selected])

	def done(self, param):
		if param:
			dialog_ = Deleter(self.master, {"files":self.files, "demodir":self.curdir, "selected":self.selected, "keepeventsfile":self.keepevents_var.get(), "deluselessjson":self.deluselessjson_var.get(), "eventfileupdate":"selectivemove"} )
			if dialog_.result_["state"] == 1:
				self.destroy()
		else:
			self.destroy()

class Deleter(Dialog):
	def __init__(self, parent, options = {}):
		self.master = parent
		self.options = options
		self.demodir = self.options["demodir"]
		self.files = self.options["files"]
		self.selected = self.options["selected"]
		self.keepeventsfile = self.options["keepeventsfile"]
		self.deluselessjson = self.options["deluselessjson"]
		if "eventfileupdate" in self.options:
			self.eventfileupdate = self.options["eventfileupdate"]
		else:
			self.eventfileupdate = "passive"

		del self.options #Is ths good practice? Probably not.

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

		Dialog.__init__(self, parent, "Delete...")

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
		self.textbox.insert(tk.END, "This operation will delete the following files:\n\n" + "\n".join(self.filestodel))
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

	def delete(self):
		if self.keepeventsfile: #---Backup _events file
			backupfolder = os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"])
			if not os.path.exists( backupfolder ):
				os.makedirs( backupfolder )
			i = 0
			while True:
				if os.path.exists( os.path.join(backupfolder, os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt" )  ): #enumerate files: _events0.txt; _events1.txt; _events2.txt ...
					i += 1
					continue
				else:
					break
			self.appendtextbox("\n\nCreating eventfile backup at " + os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"], (os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt") ) + " ...\n"  )
			shutil.copy2( os.path.join(self.demodir, _DEF["eventfile"]), os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"], (os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt") )  )
	#-----------Deletion loop-----------#
		for i in self.filestodel:#---Delete files
			os.remove( os.path.join(self.demodir, i))
			self.appendtextbox("\nDeleted " + os.path.join(self.demodir, i) )
	#-----------------------------------#

		self.appendtextbox("\n\nUpdating " + _DEF["eventfile"] + "..." )
		with open( os.path.join(self.demodir, _DEF["eventfile"]), "r") as eventhandle:#---Shorten eventfile
			rawevent = eventhandle.read()
		rawevent = rawevent.split(">\n")
		evtnames = []
		for i, j in enumerate(rawevent): #get names of each logchunk
			regres = re.search(_DEF["eventfile_filenameformat"], j)
			if regres:
				evtnames.append(regres[0][3:-4] + ".dem")
			else:
				evtnames.append(None)
		newevent = rawevent
		for i in evtnames:
			print(i)
		for i,j in enumerate(self.selected):
			print(j, self.files[i])
		if self.eventfileupdate == "selectivemove": #This update mechanism requires self.files to include every file in the directory. It'll start out with newevent as an empty list and then only move elements that are not deleted to newevent. This will clear up "neglected" event files containing logchunks whose demos do not exist anymore.
			newevent = []
			for i, j in enumerate(self.selected): #only transfer logchunks to newevent whose files are still present
				if not j:
					if self.files[i] in evtnames:
						newevent.append( rawevent[evtnames.index( self.files[i] ) ] )
		elif self.eventfileupdate == "passive": #This update mechanism work differently: Only logchunks that are deleted will be removed from list, that is all
			for i, j in enumerate(self.selected):
				if j:
					newevent.pop(evtnames.index(self.files[i]))
		newevent = ">\n".join(newevent)
		eventhandle = open( os.path.join(self.demodir, _DEF["eventfile"]), "w")
		eventhandle.write(newevent)
		eventhandle.close()
		print(newevent)

		self.appendtextbox(" Done!")

		self.result_["state"] = 1

	def destroy(self):
		Dialog.destroy(self)

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
		self.evtblocksz_var = tk.StringVar()
		self.evtblocksz_var.set(cfg["evtblocksz"])

		self.datagrabbtns = ( (_DEF["eventfile"], 1), (".json files", 2), ("None", 0) )


		Dialog.__init__(self, parent, "Settings")

	def destroy(self):
		Dialog.destroy(self)

	def body(self, master):
		'''UI'''
		self.datagrab_labelframe = tk.LabelFrame(master, text="Get bookmark information via...", padx=8, pady=8)
		for i, j in self.datagrabbtns:
			b = ttk.Radiobutton(self.datagrab_labelframe, variable = self.datagrabmode_var, text = i, value = j)
			b.pack()

		self.preview_labelframe = tk.LabelFrame(master, text="Display", padx=8, pady=8)
		ttk.Checkbutton(self.preview_labelframe, variable = self.preview_var, text="Preview demos?").pack()

		self.steampath_labelframe = tk.LabelFrame(master, text="Steam path", padx=8, pady=8)
		self.steampathentry = tk.Entry(self.steampath_labelframe, state = "readonly", textvariable = self.steampath_var)
		tk.Button(self.steampath_labelframe, text = "Change...", command = self.choosesteampath).pack(side=tk.RIGHT, fill=tk.X, expand=0)

		self.eventread_labelframe = tk.LabelFrame(master, text="Read _events.txt in chunks of size...", padx=8, pady=8)
		self.blockszselector = ttk.Combobox(self.eventread_labelframe, state = "readonly", textvariable = self.evtblocksz_var, values = [2**i for i in range(12, 28)])

		self.preview_labelframe.pack(expand=1, fill = tk.BOTH)

		self.steampathentry.pack(side=tk.LEFT, expand=1, fill=tk.X)
		self.steampath_labelframe.pack(expand=1, fill = tk.BOTH)

		self.datagrab_labelframe.pack(expand=1, fill = tk.BOTH)

		self.blockszselector.pack(expand=1, fill = tk.BOTH)
		self.eventread_labelframe.pack(expand=1, fill = tk.BOTH)

		self.btconfirm = tk.Button(master, text = "Ok", command = lambda: self.done(1))
		self.btcancel = tk.Button(master, text="Cancel", command = lambda: self.done(0))

		self.btconfirm.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)
		self.btcancel.pack(side=tk.LEFT, expand =1, fill = tk.X, anchor = tk.S)

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		if param:
			self.result = {	"datagrabmode":self.datagrabmode_var.get(),
							"previewdemos":self.preview_var.get(),
							"steampath":self.steampath_var.get(),
							"evtblocksz":int(self.evtblocksz_var.get())
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

class Mainapp():
	def __init__(self, *args, **kwargs):#A bunch of functions nest and then request index values from self.listbox, which is probably very bad but who even reads this
		'''Init values, variables, go through startup routine, then show main window.'''

		if not "values" in kwargs:
			return

		self.root = tk.Tk()
		self.root.withdraw()

		self.root.bind("<<MultiframeSelect>>", self.__updatedemowindow)
		self.root.bind("<<MultiframeRightclick>>", self.__popupmenu)

		self.root.wm_title("DemoMgr v "+str(__version__))

		self.values = kwargs["values"]

		if os.path.exists(os.path.join(os.getcwd(), self.values["iconname"])):
			self.root.iconbitmap(self.values["iconname"])

		self.workingdir = os.getcwd()
		self.cfgpath = os.path.join(self.workingdir, os.path.join(self.values["cfgfolder"], self.values["cfgname"]))
		self.curdir = ""
		self.bookmarkdata = []

		self.spinboxvar = tk.StringVar() 					#spbxv

		self.mainframe = tk.Frame(self.root, padx=5, pady=3)
		self.mainframe.pack(expand = 1, fill = tk.BOTH, side=tk.TOP, anchor = tk.NW)
			#Start execution
		startupres = self.startup()
		if startupres["res"] == -1:
			tk_msg.showerror("demomgr - Error","The following error occurred during startup: " + startupres["msg"])
		elif startupres["res"] == 1:
			d = FirstRunDialog(self.mainframe)
			if not d.result:
				quit()
			self.cfg["firstrun"] = False
			self.writecfg(self.cfg)

		#set up UI
		self.cfg = self.getcfg()
		self.__setupgui()
		self.spinboxvar.trace("w", self.spinboxsel) 		#spbxv
		if self.cfg["demopaths"]: 							#spbxv
			self.spinboxvar.set(self.cfg["demopaths"][0])	#spbxv; This will call self.reloadgui, so the frames are filled.
		self.root.deiconify()#end startup; show UI

	def startup(self):
		'''Will go through a startup routine, then return a value whether startup was successful, this is first launch etc.'''
		try:
			self.cfg = self.getcfg()
			if self.cfg["firstrun"]:
				return {"res":1, "msg":"Firstlaunch"}
		except FileNotFoundError:
			try:
				os.makedirs(self.values["cfgfolder"])
				handle = open(self.cfgpath, "w")
				handle.write(json.dumps(self.values["defaultcfg"], indent = 4))
				handle.close()
				self.cfg = self.values["defaultcfg"]
			except BaseException as _exception:
				return {"res":-1, "msg":str(_exception)}
			return {"res":1, "msg":"Firstlaunch"}
		return {"res":0, "msg":"Success."}

	def __setupgui(self):
		'''Sets up UI inside of the self.mainframe widget'''
		self.widgetframe1 = tk.Frame(self.mainframe)
		self.widgetframe2 = tk.Frame(self.mainframe)
		self.listboxframe = tk.Frame(self.mainframe)
		self.demoinfframe = tk.Frame(self.mainframe, padx=5, pady=5)
		self.statusbar = tk.Frame(self.mainframe)

		self.listbox = mfl.Multiframe(self.listboxframe, columns=4, names=["Filename","Bookmarks?","Date created","Filesize"], sort = 2, sorters=[True,False,True,True], widths = [None, 26, 16, 10], formatters = [None, None, formatdate, convertunit])

		self.pathsel_spinbox = ttk.Combobox(self.widgetframe1, state = "readonly")
		self.pathsel_spinbox.config(values = tuple(self.cfg["demopaths"]))
		self.pathsel_spinbox.config(textvariable = self.spinboxvar)

		self.rempathbtn = tk.Button(self.widgetframe1, text = "Remove demo path", command = self.rempath)
		self.addpathbtn = tk.Button(self.widgetframe1, text = "Add demo path...", command = self.addpath)
		self.settingsbtn = tk.Button(self.widgetframe1, text = "Settings...", command = self.opensettings)

		self.demoinfbox = tk_scr.ScrolledText(self.demoinfframe, wrap = tk.WORD, state=tk.DISABLED, width = 40)
		self.demoinflabel = tk.Label(self.demoinfframe, text=self.values["demlabeldefault"])

		self.playdemobtn = tk.Button(self.widgetframe2, text="Play demo...", command = self.__playdem)
		self.deldemobtn = tk.Button(self.widgetframe2, text="Cleanup...", command = self.__deldem)

		self.statusbarlabel = ttk.Label(self.statusbar, text="Ready.")

		# self.dem = tk.PhotoImage(file = "bloll.png")
		# self.demlbl = tk.Label(self.mainframe, image=self.dem)
		# self.demlbl.photo = self.dem
		# self.demlbl.pack(expand=1, fill = tk.BOTH)
		# self.demlbl.bind("<Button-1>", self.startwooh)

		#pack
		self.statusbarlabel.pack(anchor= tk.W)
		self.statusbar.pack(fill=tk.X, expand=0, side=tk.BOTTOM)

		#widgetframe1
		self.pathsel_spinbox.pack(side=tk.LEFT, fill = tk.X, expand = 1)
		self.rempathbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		self.addpathbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		tk.Label(self.widgetframe1, text="", width=3).pack(side=tk.LEFT) #Placeholder
		self.settingsbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)

		self.widgetframe1.pack(anchor = tk.N, fill = tk.X)

		#widgetframe2
		self.playdemobtn.pack(side = tk.LEFT, fill = tk.X, expand=0)
		tk.Label(self.widgetframe2, text="", width=3).pack(side=tk.LEFT) #Placeholder
		self.deldemobtn.pack(side = tk.LEFT, fill = tk.X, expand=0)

		self.widgetframe2.pack(anchor = tk.N, fill = tk.X)

		self.listbox.pack(fill=tk.BOTH, expand=1)
		self.listboxframe.pack(fill=tk.BOTH, expand = 1, side = tk.LEFT)

		self.demoinflabel.pack(fill=tk.BOTH, expand = 0, anchor= tk.W)
		self.demoinfbox.pack(fill=tk.BOTH, expand = 1)
		self.demoinfframe.pack(fill=tk.BOTH, expand = 1)


	# def startwooh(self, w):
		# threading.Thread(target=self.wooh).start()

	# def wooh(self):
		# import winsound
		# winsound.PlaySound("wooh.wav", winsound.SND_FILENAME)

	def __deldem(self):
		'''Opens dialog offering demo deletion'''
		if self.curdir == "":
			return
		files = [i for i in os.listdir(self.curdir) if os.path.splitext(i)[1] == ".dem" and (os.path.isfile(os.path.join(self.curdir, i)))]
		dialog_ = DeleteDemos(self.mainframe, **{"cfg":self.cfg, "curdir":self.curdir, "bookmarkdata":self.bookmarkdata, "files":files, "dates":[os.stat(os.path.join(self.curdir, i)).st_mtime for i in files], "filesizes":[os.stat(os.path.join(self.curdir, i)).st_size for i in files] } )

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
		dialog_ = LaunchTF2(self.mainframe, path ,self.cfg["steampath"])
		if "steampath" in dialog_.results:
			if dialog_.results["steampath"] != self.cfg["steampath"]:
				self.cfg["steampath"] = dialog_.results["steampath"]
				self.writecfg(self.cfg)
				self.cfg = self.getcfg()

	def __updatedemowindow(self, event):
		'''Renew contents of demo window'''
		if not self.cfg["previewdemos"]:
			self.demoinflabel.config(text="Preview window")
			self.demoinfbox.config(state=tk.NORMAL)
			self.demoinfbox.delete("0.0", tk.END)
			self.demoinfbox.insert(tk.END, "(Preview disabled)")
			self.demoinfbox.config(state=tk.DISABLED)
			return
		try:
			demname, deminfo = self.__readdemohdr()
			demmarks = self.__readbookmarks()[1]
			if demname == None:
				demname = "?"
			if deminfo == None:
				deminfo = "Information could not be retrieved :("
			if demmarks == None:
				demmarks = "\n\nNo bookmark information found."
		except:
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
		listboxdim = self.listbox.getdimensions()
		listboxx, listboxy = self.listboxframe.winfo_x(), self.listboxframe.winfo_y()
		rootx, rooty = self.mainframe.winfo_rootx(), self.mainframe.winfo_rooty() #oh lord that's a lotta positions
		#get coords to create the menu on

		menu = tk.Menu(self.mainframe, tearoff = 0)
		menu.add_command(label = "Play", command = self.__playdem)
		menu.add_command(label = "Delete", command = self.__popupmenu_del)
		i = 0
		offsetx = 0
		while i != clickedlist:
			offsetx += listboxdim[i][0]
			i += 1
		menu.post(rootx + listboxx + offsetx + clickx, rooty + listboxy + clicky + 20) #20 is label height. I hope that won't change.

	def __popupmenu_del(self):
		index = self.listbox.getindex()
		filename = self.listbox.getcell(0, index)
		_dialog = Deleter(self.root, {"files":[filename] ,"selected": [True], "demodir":self.curdir, "keepeventsfile": False, "deluselessjson":False} )
		if _dialog.result_["state"] == 1:
			self.reloadgui()

	def setstatusbar(self, data, timeout=None):
		'''Set statusbar text to data (str)'''
		self.statusbarlabel.config(text=str(data))
		if timeout:
			self.statusbarlabel.after(timeout, lambda:self.setstatusbar(self.values["statusbardefault"]))

	def reloadgui(self):
		'''Reload UI elements that need it'''
		self.listbox.setdata(self.fetchdata(), "column")
		self.listbox.format()
		self.__updatedemowindow(None)

	def __readdemohdr(self):
		'''Reads demoheader based on current user selection'''
		if self.listbox.getindex() == None:
			return None, None
		filename = self.listbox.getrows(self.listbox.getindex())[0][0]
		path = os.path.join(self.curdir, filename)
		if not os.path.splitext(path)[1] == ".dem":
			return None, None
		outdict = demheaderreader(path)
		formatout = [str(k) + " : " + str(outdict[k]) for k in outdict]
		formatout = "\n".join(formatout)
		return filename, formatout

	def __readbookmarks(self):
		'''Returns the bookmarks and killstreaks for the currently selected entry.'''
		index = self.listbox.getindex()
		selname = self.listbox.getcell(0, index)
		if index == None:
			return None, None
		if not os.path.splitext(os.path.join(self.curdir, selname))[1] == ".dem":
			return None, None
		filenames = [i[0] for i in self.bookmarkdata]
		try:
			entry = self.bookmarkdata[filenames.index(selname)]
		except ValueError:
			return None, None
		if entry != ("",[],[]):
			msgstr = "\n\n"
			for i in entry[1]:
				msgstr += (str(i[0]) + " streak at " + str(i[1]) +"\n")
			msgstr += "\n"
			for i in entry[2]:
				msgstr += ("\"" + str(i[0]) + "\" bookmark at " + str(i[1]) +"\n")
			return entry[0], msgstr

	def fetchdata(self):
		'''Get data from all the demos in current folder; return in format that can be directly put into listbox'''
		readfailed = False
		if self.curdir == "":
			return ((),(),(),())
		self.setstatusbar("Reading demo information from " + self.curdir)
		starttime = time.time()
		files = [i for i in os.listdir(self.curdir) if (os.path.splitext(i)[1] == ".dem") and (os.path.isfile(os.path.join(self.curdir, i)))]
		datescreated = [os.stat(os.path.join(self.curdir, i)).st_mtime for i in files]
		sizes = [os.stat(os.path.join(self.curdir, i)).st_size for i in files]
		datamode = self.cfg["datagrabmode"]
		if datamode == 0:
			data = (files, ["" for i in files], datescreated, sizes)
			return data
		elif datamode == 1: #_events.txt
			try:
				h = open(os.path.join(self.curdir, self.values["eventfile"]))
			except FileNotFoundError:
				self.setstatusbar("\"" + self.values["eventfile"] +"\" has not been found.",1500)
				return ((files, ["" for i in files], datescreated, sizes))
			self.bookmarkdata, readfailed = readevents(h, self.values["eventfile_readsize"])
			h.close()
			#end
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
		self.setstatusbar("Processed data from " + str( len(files) ) + " files in " + str(round(time.time() - starttime, 4)) + " seconds." + (" However, an error occured; data may be unreliable."*readfailed), (1500 + (3000*readfailed) ) )
		return data

	def spinboxsel(self, *args):
		'''Observer callback to self.spinboxvar; is called whenever self.spinboxvar (so the combobox) is updated. Also implicitly called from self.rempath'''
		if not self.spinboxvar.get() == self.curdir:
			self.curdir = self.spinboxvar.get()
			self.reloadgui()

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
		handle.write(json.dumps(data, indent= 4))
		handle.close()

	def getcfg(self):
		'''Gets config from self.cfgpath and returns it'''
		localcfg = self.values["defaultcfg"]
		handle = open(self.cfgpath, "r")
		localcfg.update(json.load(handle))#in case i add a new key or so
		handle.close()
		return localcfg

if __name__ == "__main__":
	mainapp = Mainapp(values = _DEF)
	mainapp.root.mainloop()