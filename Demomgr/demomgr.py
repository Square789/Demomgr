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
import threading
import queue
import webbrowser

import multiframe_list as mfl
import handle_events as handle_ev

__version__ = "0.2"
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
		"defaultcfg_types": {"demopaths":list, "lastpath":str, "firstrun": bool, "__comment":str, "datagrabmode":int, "previewdemos":bool, "steampath":str, "evtblocksz":int},
		"eventbackupfolder":"_eventbackup",
		"WELCOME":"Hi and Thank You for using DemoManager!\n\nA config file has been created in a folder next to the script.\n\nThis script is able to delete files if you tell it to.\nI in no way guarantee that this script is safe or 100% reliable and will not take any responsibility for lost data, damaged drives and/or destroyed hopes and dreams.\nThis program is licensed via the MIT Licence, by clicking the accept button below you confirm that you have read and accepted the license.",
		"eventfile":"_events.txt",
		"dateformat":"%d.%m.%Y  %H:%M:%S",
		"eventfile_filenameformat":" \\(\".+\" at",#regex
		"eventfile_bookmark":"Bookmark",
		"eventfile_killstreak":"Killstreak",
		"eventfile_ticklogsep":" at \\d+\\)",  # regex
		"eventfile_argident":" [a-zA-Z0-9]+ \\(",  # regex
		"demlabeldefault":"No demo selected.",
		"statusbardefault":"Ready.",
		"tf2exepath":"steamapps/common/team fortress 2/hl2.exe",
		"tf2headpath":"steamapps/common/team fortress 2/tf/",
		"tf2launchargs":["-steam", "-game", "tf"],
		"steamconfigpath1":"userdata/",
		"steamconfigpath2":"config/localconfig.vdf",
		"launchoptionskeys":("[\"UserLocalConfigStore\"][\"Software\"][\"Valve\"][\"Steam\"][\"Apps\"][\"440\"][\"LaunchOptions\"]",
							"[\"UserLocalConfigStore\"][\"Software\"][\"valve\"][\"Steam\"][\"Apps\"][\"440\"][\"LaunchOptions\"]",
							"[\"UserLocalConfigStore\"][\"Software\"][\"Valve\"][\"Steam\"][\"apps\"][\"440\"][\"LaunchOptions\"]",
							"[\"UserLocalConfigStore\"][\"Software\"][\"valve\"][\"Steam\"][\"apps\"][\"440\"][\"LaunchOptions\"]",),
		"errlogfile":"err.log",
		"filterdict":	{	"name":				("\"{}\" in x[\"name\"]", str),
							"bookmark_contains":("\"{}\" in \"\".join((i[0] for i in x[\"bookmarks\"]))", str),
							"map_name":			("\"{}\" in x[\"header\"][\"map_name\"]", str),
							"hostname":			("\"{}\" in x[\"header\"][\"hostname\"]", str),
							"clientid":			("\"{}\" in x[\"header\"][\"clientid\"]", str),
							"killstreak_min":	("len(x[\"killstreaks\"]) >= {}", int),
							"killstreak_max":	("len(x[\"killstreaks\"]) <= {}", int),
							"bookmark_min":		("len(x[\"bookmarks\"]) >= {}", int),
							"bookmark_max":		("len(x[\"bookmarks\"]) <= {}", int),
							"beststreak_min":	("max((i[0] for i in x[\"killstreaks\"]), default=0) >= {}", int),
							"beststreak_max":	("max((i[0] for i in x[\"killstreaks\"]), default=99999) <= {}", int),
							"moddate_min":		("x[\"filedata\"][\"modtime\"] >= {}", int),
							"moddate_max":		("x[\"filedata\"][\"modtime\"] <= {}", int),
							"filesize_min":		("x[\"filedata\"][\"filesize\"] >= {}", int),
							"filesize_max":		("x[\"filedata\"][\"filesize\"] <= {}", int),
						},
		# [0] will be passed through eval(), prefixed with "lambda x: "; {} replaced by [1] called with ESCAPED user input as parameter
		# -> eval("lambda x:\"" + str("koth_") + "\" in x[\"name\"]") -> lambda x: "koth_" in x["name"]
		"filterneg":"!",
		"filterkeysep":":",
		"filterparamsep":"*",
		"filterparamsep_regex":r"(.*?)((?<!\\)\*|$)",  # regex; NOTE: Evil.
		"filtercondsep_regex":r"(.*?)((?<!\\),|$)",
		"GUI_UPDATE_WAIT":20, # Setting this to lower values might lock the UI, use with care.
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

def readbinStr(handle, leng = 260):
	'''Reads file handle by leng bytes and attempts to decode to utf-8'''
	rawbin = handle.read(leng)
	bin = rawbin.strip(b"\x00")
	return bin.decode("utf-8")

def readbinInt(handle, leng = 4):
	rawbin = handle.read(leng)
	return struct.unpack("i",rawbin)[0]

def readbinFlt(handle):
	rawbin = handle.read(4)
	return struct.unpack("f",rawbin)[0]

def readdemoheader(path): #Code happily duplicated from https://developer.valvesoftware.com/wiki/DEM_Format
	'''Reads the header information of a demo.'''
	demhdr = {	"dem_prot":3,
				"net_prot":24,
				"hostname":"",
				"clientid":"",
				"map_name":"",
				"game_dir":"",
				"playtime":0,
				"tick_num":0,
				"framenum":0,
				"tickrate":0,}
	
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
	'''Extracts the argument(killstreak number or bookmark name) from a logchunk'''
	regres = re.search(_DEF["eventfile_argident"], logchunk)
	return regres[0][1:len(regres[0]) - 2]

def _convertlogchunks(logchunk):
	'''Converts each _events.txt logchunk to a tuple: (filename, [(Streak: killstreakpeaks), (tick), ...], [(Bookmark: bookmarkname), (tick), ...])'''
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

	for i in loglines:
		if i == "": #Line empty, likely last line.
			continue
		tick = i[- (len(re.search(_DEF["eventfile_ticklogsep"], i)[0]) - 5) -1: -1]#Unreadable but it gets the tick number
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
	streakpeaks = getstreakpeaks(killstreaks)
	return (filename, streakpeaks, bookmarks) #there he is

def getstreakpeaks(killstreaks): #Convert killstreaks to their peaks exclusively (1,2,3,4,5,6,1,2,1,2,3,4) -> (6,2,4)
	streakpeaks = []
	if killstreaks:
		localkillstreaks = killstreaks.copy()
		localkillstreaks.append((-1, -1))
		prv = (-1, -1)
		for i in localkillstreaks:
			if i[0] <= prv[0]:
				streakpeaks.append(prv)
			prv = i
	return streakpeaks

def readevents(handle, blocksz):
	'''This function reads an events.txt file as it's written by the source engine,
	returns (filename, ( (killstreakpeak, tick)... ), ( (bookmarkname, tick)... ) ).
	May raise errors.
	'''
	reader = handle_ev.EventReader(handle, blocksz=blocksz)
	out = []
	for chk in reader:
		out.append(_convertlogchunks(chk.content))
	reader.destroy()
	return out

def assignbookmarkdata(files, bookmarkdata):
	'''Takes a list of files and the bookmarkdata; returns a list that contains the parallel bookmarkdata; ("", [], []) if no match found.'''
	assignedlogs = [("", [], []) for i in range(len(files))]
	for i in bookmarkdata:
		for j in range(len(files)):
			if i[0] == files[j]:
				assignedlogs[j] = i
	return assignedlogs

def formatbookmarkdata(filelist, bookmarkdata):
	'''Converts bookmarkdata into a list of strings: "X Bookmarks, Y Killstreaks". needs filelist to assign bookmarkdata to '''
	assignedlogs = assignbookmarkdata(filelist, bookmarkdata)
	listout = ["" for i in assignedlogs]
	for i in range(len(assignedlogs)): #convert the correctly assigned logs ("", [], []) into information displaying strings
		if assignedlogs[i] != ("", [], []):
			listout[i] = str(len(assignedlogs[i][2])) + " Bookmarks; " + str(len(assignedlogs[i][1])) + " Killstreaks."
		else:
			listout[i] = "None"
	return listout

def escapeinput(raw):
	"""Adds escape char (\) in front of all occurrences of \ and " """
	out = []
	for i in raw:
		if i in ("\"", "\\"):
			out.append("\\")
		out.append(i)
	return "".join(out)

def _parsefilters(filterinp): #used in Thread_Filter and DeleteDemos.__applycond
	'''Takes input: <key1>:<val1>*<val2>, <key2>:<val1>*<val2>, ..., converts it to lambdas using _DEF["filterdict"]. Returns optional message on failure.
	Output: filters<list of lambdas>, success<bool>, <Exception or None>, Error information<Str>'''
	try:
		#Sanitize
		raw = escapeinput(filterinp)#Protect from escapes/injections on the eval() level
		#print(re.findall(_DEF["filtercondsep_regex"], raw, re.M)) #TODO: REWRITE THE ENTIRE PARSER, IT'S A MESS AND WE'RE TOO FAR IN
		raw = raw.split(",")
		raw = [i.strip() for i in raw]
		params = [ [i.split(_DEF["filterkeysep"])[0], [ [j[0] for j in re.findall(_DEF["filterparamsep_regex"], i.split(_DEF["filterkeysep"])[1])[:-1] ], False] ] for i in raw]
		#For each pair of key and parameters as string: create a list where [0] is the key and [1] is a list where: [[param1, param2, ...], <boolean>]. The boolean will be changed further down and indicates negation of the command the key stands for.
		del raw
		for i, j in enumerate(params):
			if "" in j[1][0] or not j[1][0]: # Raise Exception for empty parameters
				raise ValueError("Empty parameter!")
			for k, l in enumerate(j[1][0]):	#NOTE: unescape asterisks the regex ignores, this is probably quite illegal
				params[i][1][0][k] = l.replace("\\" + _DEF["filterparamsep"], _DEF["filterparamsep"])
		for i, j in enumerate(params):
			if j[0][0] == _DEF["filterneg"]:				#if key starts with !
				params[i][0] = j[0][len(_DEF["filterneg"]):]#shorten key
				params[i][1][1] = True						#set "isNegated" bool to true
		conddict = dict(params) # conddict looks as follows: {<filter key>:[[<str| filter param1>, <str| filter param2>, ...], <bool| isNegated>], ...}
		del params
	except Exception as exc:
		return [], False, exc, "Invalid filter parameter format: {}".format(exc.args[0])
	filters = []
	try:
		for k in conddict:
			isneg = conddict[k][1]
			filters.append(eval("lambda x: {}{}{}".format( "not (" * isneg, " or ".join(_DEF["filterdict"][k][0].format( _DEF["filterdict"][k][1]( i ) ) for i in conddict[k][0]), ")" * isneg) )  )#Construct lambdas for the user-entered conditions
	except KeyError as exc:
		return [], False, exc, "Invalid filtering key: \"{}\" ; please check your input.".format(str(k))
	except ValueError as exc:
		return [], False, exc, "Invalid filtering parameter: \"{}\"; please check your input.".format(conddict[k][0][i]) # i should be whatever's in the horror list generator above
	return filters, True, None, ""

class HeaderFetcher: #used in MainApp.__filter and DeleteDemos.__applycond
	'''Only read a header when the class is accessed.'''
	def __init__(self, filepath):
		self.filepath = filepath
		self.header = None

	def __getitem__(self, key):
		if self.header == None:
			try:
				self.header = readdemoheader(self.filepath)
			except Exception:
				self.header = {"dem_prot":3, "net_prot":24, "hostname":"", "clientid":"", "map_name":"", "game_dir":"", "playtime":0, "tick_num":0, "framenum":0, "tickrate":0} #Fallback header so corrupted demos don't crash the filter
		return self.header[key]

class FileStatFetcher: #used in MainApp.__filter and DeleteDemos.__applycond
	'''Only read a file's size and moddate when the class is accessed.'''
	def __init__(self, filepath):
		self.filepath = filepath
		self.data = None

	def __getitem__(self, key):
		if self.data == None:
			statres = os.stat(self.filepath)
			self.data = {"filesize":statres.st_size, "modtime":statres.st_mtime}
		return self.data[key]

class _StoppableBaseThread(threading.Thread):
	''' This thread has a killflag (stoprequest <threading.Event>),
		and expects a queue_in and queue_out attribute in the constructor. It also takes args and kwargs.
		It can be stopped by calling its join method, however has to regularly check for the stopflag in the run method.
		The stopflag can be ignored by passing a third arg that is evaluated to True to the join() method.
		!!! Override this thread's run() method, start by calling start() !!! '''
	def __init__(self, queue_inp, queue_out, *args, **kwargs):
		super().__init__()
		self.queue_inp = queue_inp
		self.queue_out = queue_out
		self.args = args
		self.kwargs = kwargs
		self.stoprequest = threading.Event()

	def join(self, timeout=None, dontstop=False):
		if not dontstop:
			self.stoprequest.set()
		super().join(timeout)

class Thread_Filter(_StoppableBaseThread):
	'''Thread takes no queue_inp, but queue_out and args[0] as a dict with the following keys:
		filterstring <Str>:Raw user input from the entry field
		curdir <Str>: Absolute path to current directory
		cfg <Dict>: Program configuration as in .demomgr/config.cfg'''

	def run(self):
		self.options = self.args[0].copy()
		filterstring = self.options["filterstring"]
		curdir = self.options["curdir"]
		cfg = self.options["cfg"]
		starttime = time.time()

		self.queue_out.put(  ("SetStatusbar", ("Filtering demos; Parsing filter...", ) )  )
		filterres = _parsefilters(filterstring)
		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) ); return

		if not filterres[1]:
			self.queue_out.put(  ("SetStatusbar", (filterres[3], 4000) )  )
			self.queue_out.put( ("Finish", 0) ); return
		else:
			filters = filterres[0]
		del filterres

		self.queue_out.put(  ("SetStatusbar", ("Filtering demos; Reading information...", ) )  )
		bookmarkdata = None
		files = None
		self.datafetcherqueue = queue.Queue()
		self.datafetcherthread = Thread_ReadFolder(None, self.datafetcherqueue, {"curdir":curdir, "cfg":cfg, })
		self.datafetcherthread.start()
		self.datafetcherthread.join(None, 1) # NOTE: Severe wait time?
		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) ); return

		while True:
			try:
				queueobj = self.datafetcherqueue.get_nowait()
				if queueobj[0] == "Result":
					files = queueobj[1][0]
				elif queueobj[0] == "Bookmarkdata":
					bookmarkdata = queueobj[1]
				elif queueobj[0] == "Finish":
					break
			except queue.Empty:
				break
		del self.datafetcherqueue
		if bookmarkdata == None:
			bookmarkdata = ()
		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) ); return

		self.queue_out.put( ("SetStatusbar", ("Filtering demos; Assigning bookmarkdata...", ) ) )
		asg_bmd = assignbookmarkdata(files, bookmarkdata)
		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) ); return

		filteredlist = []
		file_amnt = len(files)
		for i, j in enumerate(files): #Filter
			self.queue_out.put(  ("SetStatusbar", ("Filtering demos; {} / {}".format(i + 1, file_amnt), ) )  )
			curdataset = {"name":j, "killstreaks":asg_bmd[i][1], "bookmarks":asg_bmd[i][2], "header": HeaderFetcher(os.path.join(curdir, j)), "filedata": FileStatFetcher(os.path.join(curdir, j))}
			#The Fetcher classes prevent unneccessary drive access when the user i.E. only filters by name
			for l in filters:
				if not l(curdataset):
					break
			else:
				filteredlist.append((curdataset["name"], str(len(curdataset["bookmarks"])) + " Bookmarks; "+ str(len(curdataset["killstreaks"])) + " Killstreaks.", curdataset["filedata"]["modtime"], curdataset["filedata"]["filesize"]))
			if self.stoprequest.isSet():
				self.queue_out.put( ("Finish", 2) ); return
		del filters
		self.queue_out.put( ("Result", filteredlist) )
		self.queue_out.put(  ("SetStatusbar", ("Filtered {} demos in {} seconds.".format(file_amnt, str(round(time.time() - starttime, 3)) ), 3000) )  )
		self.queue_out.put( ("Finish", 1) )

class Thread_ReadFolder(_StoppableBaseThread):
	'''Thread takes no queue_inp, but queue_out and as args[0] a dict with the following keys:
		curdir <Str>: Full path to the directory to be read out
		cfg <Dict>: Program configuration as in .demomgr/config.cfg'''

	def __stop(self, statmesg, result, exitcode):
		'''Outputs end signals to self.queue_out, every arg will be output
		as [1] in a tuple where [0] is - in that order - "SetStatusbar",
		"Result", "Finish". If the first arg is None, the "SetStatusbar"
		tuple will not be output.'''
		if statmesg != None:
			self.queue_out.put( ("SetStatusbar", statmesg ) )
		self.queue_out.put( ("Result", result) )
		self.queue_out.put( ("Finish", exitcode) )
	
	def run(self):
		'''Get data from all the demos in current folder; return in format that can be directly put into listbox'''
		self.options = self.args[0].copy()
		if self.options["curdir"] == "":
			self.__stop(None, ((), (), (), ()), 0); return
		self.queue_out.put( ("SetStatusbar", ("Reading demo information from {} ...".format(self.options["curdir"]), None) ) )
		starttime = time.time()

		try:
			files = [i for i in os.listdir(self.options["curdir"]) if (os.path.splitext(i)[1] == ".dem") and (os.path.isfile(os.path.join(self.options["curdir"], i)))]
			datescreated = [os.path.getmtime(os.path.join(self.options["curdir"], i)) for i in files]
			if self.stoprequest.isSet():
				self.queue_out.put( ("Finish", 2) ); return
			sizes = [os.path.getsize(os.path.join(self.options["curdir"], i)) for i in files]
			if self.stoprequest.isSet():
				self.queue_out.put( ("Finish", 2) ); return
		except FileNotFoundError:
			self.__stop( ("ERROR: Current directory \"{}\" does not exist.".format(self.options["curdir"]), None), ((), (), (), ()), 0); return
		except (OSError, PermissionError) as error:
			self.__stop( ("ERROR reading directory: {}.".format(str(error)), None), ((), (), (), ()), 0); return

		# Grab bookmarkdata
		datamode = self.options["cfg"]["datagrabmode"]
		if datamode == 0: #Disabled
			self.__stop( ("Bookmark information disabled.", 2000), (files, ["" for i in files], datescreated, sizes), 1); return
		elif datamode == 1: #_events.txt
			handleopen = False
			try:
				h = open(os.path.join(self.options["curdir"], _DEF["eventfile"]), "r")
				handleopen = True
				bookmarklist = readevents(h, self.options["cfg"]["evtblocksz"]) #TODO: ADD ERROR TYPE IN handle_events, then make this better!
				h.close()
				self.queue_out.put( ("Bookmarkdata", bookmarklist ) )
			except Exception:
				if handleopen: h.close()
				self.__stop( ("\"{}\" has not been found, can not be opened or is malformed.".format(_DEF["eventfile"]), 5000), (files, ["" for i in files], datescreated, sizes), 0); return	
		elif datamode == 2: #.json
			try:
				jsonfiles = [i for i in os.listdir(self.options["curdir"]) if os.path.splitext(i)[1] == ".json" and os.path.exists(os.path.join(self.options["curdir"], os.path.splitext(i)[0] + ".dem"))]
			except (OSError, FileNotFoundError, PermissionError) as error:
				self.__stop( ("Error getting .json files: {}".format(str(error)), 5000), (files, ["" for i in files], datescreated, sizes), 0); return
			bookmarklist = []
			for i, j in enumerate(jsonfiles):
				bookmarklist.append([os.path.splitext(j)[0] + ".dem", [], [], ])	
				if self.stoprequest.isSet():
					self.queue_out.put( ("Finish", 2) ); return
				try:
					h = open(os.path.join(self.options["curdir"], j))
				except (OSError, PermissionError, FileNotFoundError) as error:
					bookmarklist[i] = ("", (), ())
					continue
				try:
					curjson = json.load(h)["events"] #{"name":"Killstreak/Bookmark","value":"int/Name","tick":"int"}
				except json.Decoder.JSONDecodeError as error:
					bookmarklist[i] = ("", (), ())
					h.close()
					continue
				h.close()

				for k in curjson:
					try:
						if k["name"] == "Killstreak":
							bookmarklist[i][1].append((int(k["value"]), int(k["tick"])))
						elif k["name"] == "Bookmark":
							bookmarklist[i][2].append((k["value"], int(k["tick"])))
					except (ValueError, TypeError):
						break
				else: # When loop completes normally
					bookmarklist[i][1] = getstreakpeaks(bookmarklist[i][1])
					continue
				bookmarklist[i] = ("", (), ()) # Loop completes abnormally, bad JSON
			self.queue_out.put( ("Bookmarkdata", bookmarklist) )

		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) ); return

		listout = formatbookmarkdata(files, bookmarklist) #format the bookmarkdata into readable strings ("1 Killstreaks, 2 Bookmarks")

		data = ( files, listout, datescreated, sizes )
		self.__stop( ("Processed data from {} files in {} seconds.".format( len(files), round(time.time() - starttime, 4) ), 3000), data, 1); return

class Thread_Deleter(_StoppableBaseThread):
	'''Thread takes no queue_inp, but an additional dict with the following keys:
		keepeventsfile <Bool>: Whether to create a backup of _events.txt
		demodir <Str>: Absolute directory to delete demos in.
		files <List[Str]>: List of all files in demodir.
		selected <List[Bool]>: List of bools of same length as files.
		filestodel <List[Str]>: Simple file names of the files to be removed; [j for i, j in enumerate(files) if selected[i]]
		cfg <Dict>: Program configuration as in .demomgr/config.cfg #NOTE: ONLY evtblocksz is being retrieved from this, maybe simplify in future
		eventfileupdate <Str; "passive"|"selectivemove">: eventfile update mode.
	'''
	def run(self):
		self.options = self.args[0].copy()
		evtpath = os.path.join(self.options["demodir"], _DEF["eventfile"])
		del self.args
		if self.options["keepeventsfile"]: #---Backup _events file
			try:
				if os.path.exists(evtpath): #This will fail when demodir is blocked
					backupfolder = os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"])
					if not os.path.exists(backupfolder):
						os.makedirs(backupfolder)
					i = 0
					while True:
						if os.path.exists( os.path.join(backupfolder, os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt" )  ): #enumerate files: _events0.txt; _events1.txt; _events2.txt ...
							i += 1
						else:
							break
					self.queue_out.put( ( "ConsoleInfo", "\nCreating eventfile backup at " + os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"], (os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt") ) + " .\n"  ) )
					shutil.copy2( os.path.join(self.options["demodir"], _DEF["eventfile"]), os.path.join(os.getcwd(), _DEF["cfgfolder"], _DEF["eventbackupfolder"], (os.path.splitext(_DEF["eventfile"])[0] + str(i) + ".txt") )  )
				else:
					self.queue_out.put( ( "ConsoleInfo", "\nEventfile does not exist; can not create backup.\n") )
			except Exception as error:
				self.queue_out.put( ("ConsoleInfo", "\nError while copying eventfile: {}.\n".format(str(error))) )
		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) )
			return
		errorsencountered = 0 #---Delete files
		deletedfiles = 0
		starttime = time.time()
	#-----------Deletion loop-----------#
		for i in self.options["filestodel"]:
			if self.stoprequest.isSet():
				self.queue_out.put( ("Finish", 2) ); return
			try:
				os.remove( os.path.join(self.options["demodir"], i))
				deletedfiles += 1
				self.queue_out.put( ("ConsoleInfo", "\nDeleted {} .".format(i) ) )
			except Exception as error:
				errorsencountered += 1
				self.queue_out.put( ("ConsoleInfo", "\nError deleting \"{}\": {} .".format(i, str(error)) ) )
	#-----------------------------------#
		self.queue_out.put( ("ConsoleInfo", "\n\nUpdating " + _DEF["eventfile"] + "..." ) ) #---Update eventfile; NOTE: NO CHECK FOR STOPREQUEST IN HERE; WILL ONLY ADD COMPLEXITY DUE TO HAVING TO CLOSE OPEN RESOURCES.
		if os.path.exists(evtpath):
			tmpevtpath = os.path.join(self.options["demodir"], "." + _DEF["eventfile"])
			readeropen = False
			writeropen = False
			try:
				reader = handle_ev.EventReader(evtpath, blocksz = self.options["cfg"]["evtblocksz"])
				readeropen = True
				writer = handle_ev.EventWriter(tmpevtpath, clearfile = True)
				writeropen = True

				if self.options["eventfileupdate"] == "passive":
					while True: #NOTE: Could update those to be for loops, but I dont wanna break this
						outchunk = next(reader)
						regres = re.search(_DEF["eventfile_filenameformat"], outchunk.content)
						if regres: curchunkname = regres[0][3:-4] + ".dem"
						else: curchunkname = ""
						if not curchunkname in self.options["filestodel"]:#create a new list of okay files or basically waste twice the time going through all the .json files?
							writer.writechunk(outchunk)
						if outchunk.message["last"]: break

				elif self.options["eventfileupdate"] == "selectivemove":#Requires to have entire dir/actual files present in self.files;
					okayfiles = set([j for i, j in enumerate(self.options["files"]) if not self.options["selected"][i]])
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
				self.queue_out.put( ("ConsoleInfo", " Done!") )
			except (OSError, PermissionError) as error:
				self.queue_out.put( ("ConsoleInfo", "\n<!!!>\nError updating eventfile:\n{}\n<!!!>".format(str(error))) )
				if readeropen: reader.destroy()
				if writeropen: writer.destroy()
		else:
			self.queue_out.put( ("ConsoleInfo", " Event file not found, skipping.") )
		self.queue_out.put( ("ConsoleInfo", "\n\n==[Done]==\nTime taken: {} seconds\nFiles deleted: {}\nErrors encountered: {}\n==========".format( round(time.time() - starttime, 3), deletedfiles, errorsencountered)) )
		self.queue_out.put( ("Finish", 1) )

class Thread_MarkDemo(_StoppableBaseThread):
	pass

class _BaseDialog(Dialog):
	'''Helper base class that overrides some methods from the tk.simpledialog.Dialog class.'''
	def __init__(self, parent, title = None):
		super().__init__(parent, title)

	def body(self, master): pass
	def buttonbox(self): pass
	def validate(self): pass
	def apply(self): pass
	def ok(self, _): pass

class FirstRunDialog(_BaseDialog):
	def __init__(self, parent = None):
		if not parent:
			parent = tk._default_root
		super().__init__(parent, "Welcome!")

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

class LaunchTF2(_BaseDialog):
	def __init__(self, parent, options):
		'''Args: parent tkinter window, options dict with:
		demopath (Absolute file path to the demo to be played), steamdir'''

		self.result_ = {}

		self.parent = parent

		self.demopath = options["demopath"]
		self.steamdir = tk.StringVar()
		self.steamdir.set(options["steamdir"])

		self.errstates = [False, False, False, False, False] #0:Bad config, 1: Steamdir on bad drive, 2: VDF missing, 3:Demo outside /tf/, 4:No launchoptions

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
		self.steamdirentry = ttk.Entry(steamdirframe, state="readonly", textvariable = self.steamdir)
		self.steamdirbtn = tk.Button(steamdirframe, command=self.askfordir, text="Select Steam install path")
		self.error_steamdir_invalid = tk.Label(steamdirframe, fg="#AA0000", text="Getting steam users failed! Please select the root folder called \"Steam\".\nEventually check for permission conflicts.")
		self.warning_steamdir_mislocated = tk.Label(steamdirframe, fg="#AA0000", text="The queried demo and the Steam directory are on seperate drives.")

		userselectframe = tk.LabelFrame(master, text="Select user profile if needed", padx = 10, pady=8)
		self.info_launchoptions_not_found = tk.Label(userselectframe, fg = "#222222", text="Launch configuration not found, it likely does not exist.")
		self.userselectspinbox = tk.Spinbox(userselectframe, textvariable = self.userselectvar, values=self.getusers(), state="readonly")#Once changed, observer callback will be triggered by self.userselectvar

		launchoptionsframe = tk.LabelFrame(master, text="Launch options:", padx = 10, pady=8)
		launchoptwidgetframe = tk.Frame(launchoptionsframe, bd=4, relief = tk.RAISED, padx = 5, pady = 4)
		self.warning_vdfmodule = tk.Label(launchoptwidgetframe, fg="#AA0000", text="Please install the vdf module in order to launch TF2 with your default settings. (Run cmd in admin mode; type \"python -m pip install vdf\")")#WARNLBL
		self.launchlabel1 = tk.Label(launchoptwidgetframe, text="[...]/hl2.exe -steam -game tf")
		self.launchoptionsentry = ttk.Entry(launchoptwidgetframe, textvariable=self.launchoptionsvar)
		pluslabel = tk.Label(launchoptwidgetframe, text="+")
		self.launchlabelentry = ttk.Entry(launchoptwidgetframe, state="readonly", textvariable = self.playdemoarg)

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
			with open(os.path.join( self.steamdir.get(), _DEF["steamconfigpath1"], self.userselectvar.get(), _DEF["steamconfigpath2"]) ) as h:
				launchopt = vdf.load(h)
			for i in _DEF["launchoptionskeys"]:
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
		except (KeyError, FileNotFoundError, OSError, PermissionError, SyntaxError): #SyntaxError raised by vdf module
			self.errstates[4] = True
			return ""

	def askfordir(self): #Triggered by user clicking on the Dir choosing btn
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steamdir.set(sel)
		self.userselectspinbox.config(values = self.getusers())
		try:
			self.userselectvar.set(self.getusers()[0])
		except Exception:
			self.userselectvar.set("") # will trigger self.userchange
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
				self.result_ = {"success":True, "steampath":self.steamdir.get()}
			except FileNotFoundError:
				self.result_ = {"success":False, "steampath":self.steamdir.get()}
				tk_msg.showerror("Demomgr - Error", "hl2 executable not found.", parent = self)
			except (OSError, PermissionError) as error:
				self.result_ = {"success":False, "steampath":self.steamdir.get()}
				tk_msg.showerror("Demomgr - Error", "Could not access hl2.exe :\n{}".format(str(error)), parent = self)
		self.destroy()

class DeleteDemos(_BaseDialog):
	def __init__(self, parent, options):
		'''Args: parent tkinter window, options dict with:
		bookmarkdata, files, dates, filesizes, curdir, cfg'''
		self.master = parent

		self.bookmarkdata = options["bookmarkdata"]
		self.files = options["files"]
		self.dates = options["dates"]
		self.filesizes = options["filesizes"]
		self.curdir = options["curdir"]
		self.cfg = options["cfg"]

		self.bookmarkdata = assignbookmarkdata(self.files, self.bookmarkdata)

		self.symbollambda = lambda x: " X" if x else ""

		self.keepevents_var = tk.BooleanVar()
		self.deluselessjson_var = tk.BooleanVar()
		self.selall_var = tk.BooleanVar()
		self.filterbox_var = tk.StringVar()

		self.selected = [False for _ in self.files]

		self.result_ = {"state":0}

		super().__init__(parent, "Delete...")

	def body(self, master):
		'''UI'''
		master.bind("<<MultiframeSelect>>", self.__procentry)

		okbutton = tk.Button(master, text = "Delete", command = lambda: self.done(1) )
		cancelbutton = tk.Button(master, text= "Cancel", command = lambda: self.done(0) )

		self.listbox = mfl.Multiframe(master, columns = 5, names= ["","Name","Date created","Info","Filesize"], sort = 0, formatters = [None, None, formatdate, None, convertunit], widths = [2, None, 18, 25, 15])
		self.listbox.setdata(([self.symbollambda(i) for i in self.selected], self.files, self.dates, formatbookmarkdata(self.files, self.bookmarkdata), self.filesizes) , mfl.COLUMN)
		self.listbox.format()

		self.demoinflabel = tk.Label(master, text="", justify=tk.LEFT, anchor=tk.W, font = ("Consolas", 8) )

		self.listbox.frames[0][2].pack_propagate(False) #looks weird, is sloppy, will probably lead to problems at some point. change parent to master if problems occur and comment out this line
		selall_checkbtn = ttk.Checkbutton(self.listbox.frames[0][2], variable=self.selall_var, text="", command = self.selall) # ''

		optframe = tk.LabelFrame(master, text="Options...", pady=3, padx=8)
		keepevents_checkbtn = ttk.Checkbutton(optframe, variable = self.keepevents_var, text = "Make backup of " + _DEF["eventfile"])
		deljson_checkbtn = ttk.Checkbutton(optframe, variable = self.deluselessjson_var, text = "Delete orphaned json files")

		condframe = tk.LabelFrame(master, text="Demo selector / Filterer", pady=3, padx=8)
		self.filterbox = ttk.Entry(condframe, textvariable = self.filterbox_var) #
		self.applybtn = tk.Button(condframe, text="Apply filter", command = self.__applycond)

		self.applybtn.pack(side=tk.RIGHT)
		tk.Label(condframe).pack(side=tk.RIGHT)
		self.filterbox.pack(side=tk.RIGHT, fill=tk.X, expand=1)
		condframe.pack(fill=tk.BOTH)

		deljson_checkbtn.pack(side=tk.LEFT)
		keepevents_checkbtn.pack(side=tk.LEFT)
		optframe.pack(fill=tk.BOTH)

		selall_checkbtn.pack(side=tk.LEFT, anchor=tk.W)

		self.listbox.pack(side=tk.TOP,fill=tk.BOTH, expand=1)

		self.demoinflabel.pack(side=tk.TOP, fill = tk.BOTH, expand = 0, anchor = tk.W)

		okbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)
		cancelbutton.pack(side=tk.LEFT, fill=tk.X,expand=1)

	def __procentry(self, event):
		index = self.listbox.getselectedcell()[1]

		if self.cfg["previewdemos"]:
			try:
				hdr = readdemoheader(os.path.join(self.curdir, self.listbox.getcell(1,index)) )
			except Exception:
				hdr = {	"dem_prot":3, "net_prot":24, "hostname":"", "clientid":"", "map_name":"", "game_dir":"", "playtime":0, "tick_num":0, "framenum":0, "tickrate":0}
			self.demoinflabel.config(text="Hostname: {}| ClientID: {}| Map name: {}".format(hdr["hostname"], hdr["clientid"], hdr["map_name"]) )
		
		if self.listbox.getselectedcell()[0] != 0: return
		if index == None: return
		self.selected[index] = not self.selected[index]
		if False in self.selected:
			self.selall_var.set(0)
		else:
			self.selall_var.set(1)
		self.listbox.setcell(0, index, self.symbollambda(self.selected[index]))

	def __setitem(self, index, value, lazyui = False): #value: bool
		self.selected[index] = value
		if not lazyui:
			if False in self.selected: #~ laggy
				self.selall_var.set(0)
			else:
				self.selall_var.set(1)
			self.listbox.setcolumn(0, [self.symbollambda(i) for i in self.selected])#do not refresh ui. this is done while looping over the elements, then a final refresh is performed.

	def __applycond(self): #NOTE: Improve overall handling of bookmarks?
		'''Apply user-entered condition to the files.'''
		filterparseres = _parsefilters(self.filterbox_var.get())
		if not filterparseres[1]:#TODO: Add error messages
			return
		else:
			filters = filterparseres[0]
		for i, j in enumerate(self.files):
			curfile = {"name":j, "killstreaks":self.bookmarkdata[i][1], "bookmarks":self.bookmarkdata[i][2], "header": HeaderFetcher(os.path.join(self.curdir, j)), "filedata": FileStatFetcher(os.path.join(self.curdir, j))}
			curdemook = True
			for f in filters:
				if not f(curfile):
					curdemook = False
					break
			if curdemook:
				self.__setitem(i, True, True)
			else:
				self.__setitem(i, False, True)
		if len(self.selected) != 0: #set select all checkbox
			self.__setitem(0, self.selected[0], False)

	def selall(self):
		if False in self.selected:
			self.selected = [True for i in self.files]
		else:
			self.selected = [False for i in self.files]
		self.listbox.setcolumn(0, [self.symbollambda(i) for i in self.selected])

	def done(self, param):
		if param:
			dialog_ = Deleter(self.master, {"cfg":self.cfg,"files":self.files, "demodir":self.curdir, "selected":self.selected, "keepeventsfile":self.keepevents_var.get(), "deluselessjson":self.deluselessjson_var.get(), "eventfileupdate":"selectivemove"} )
			if dialog_.result_["state"] != 0:
				self.result_["state"] = 1
				self.destroy()
		else:
			self.destroy()

class Deleter(_BaseDialog):
	def __init__(self, parent, options):
		'''Args: parent tkinter window, options dict with:
		demodir, files, selected, keepeventsfile, deluselessjson, cfg, (eventfileupdate)
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

		self.startmsg = "This operation will delete the following file(s):\n\n" + "\n".join(self.filestodel)

		try: #Try block should only catch from the os.listdir call
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

		self._Delthread = threading.Thread() #Dummy thread in case self.cancel is called through window manager
		self.after_handler = None
		self.queue_out = queue.Queue()

		self.result_ = {"state":0} #exit state. set to 1 if successful

		super().__init__(parent, "Delete...")

	def body(self, master):
		'''UI'''
		self.okbutton = tk.Button(master, text = "Delete!", command = lambda: self.confirm(1) )
		self.cancelbutton = tk.Button(master, text= "Cancel", command = self.destroy )
		self.closebutton = tk.Button(master, text="Close", command = self.destroy )
		self.canceloperationbutton = tk.Button(master, text = "Abort", command = self.__stopoperation)
		textframe = tk.Frame(master, pady = 5, padx = 5)

		self.textbox = tk.Text(textframe, wrap = tk.NONE, width = 40, height = 20)
		self.vbar = ttk.Scrollbar(textframe, orient = tk.VERTICAL, command = self.textbox.yview)
		self.vbar.pack(side = tk.RIGHT, fill = tk.Y, expand = 0)
		self.hbar = ttk.Scrollbar(textframe, orient = tk.HORIZONTAL, command = self.textbox.xview)
		self.hbar.pack(side = tk.BOTTOM, anchor = tk.S, fill = tk.X, expand = 0)
		self.textbox.config( **{"xscrollcommand" : self.hbar.set, "yscrollcommand" : self.vbar.set} )
		self.textbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

		self.textbox.delete("0.0", tk.END)
		self.textbox.insert(tk.END, self.startmsg)
		self.textbox.config(state=tk.DISABLED)

		self.textbox.pack(fill = tk.BOTH, expand = 1)
		textframe.pack(fill = tk.BOTH, expand = 1)

		self.okbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)
		self.cancelbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)

	def confirm(self, param):
		if param == 1:
			self.okbutton.pack_forget()
			self.cancelbutton.pack_forget()
			self.canceloperationbutton.pack(side=tk.LEFT, fill=tk.X, expand=1)
			self.__startthread()

	def __stopoperation(self):
		if self._Delthread.isAlive():
			self._Delthread.join()

	def __startthread(self):
		self._Delthread = Thread_Deleter(None, self.queue_out, {	"keepeventsfile":	self.keepeventsfile,
																	"demodir":			self.demodir,
																	"files":			self.files,
																	"selected":			self.selected,
																	"filestodel":		self.filestodel,
																	"cfg":				self.cfg,
																	"eventfileupdate":	self.eventfileupdate})
		self._Delthread.start()
		self.after_handler = self.after(0, self.__after_callback)

	def __after_callback(self):
		'''Gets stuff from self.queue_out that the thread is supposed to write to, then acts based on that.'''
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
			self.after_handler = self.after(_DEF["GUI_UPDATE_WAIT"], self.__after_callback)
			return
		else: #THREAD DONE
			self.after_cancel(self.after_handler)
			self.result_["state"] = finished[1]
			self.canceloperationbutton.pack_forget()
			self.closebutton.pack(side=tk.LEFT, fill=tk.X, expand=1)

	def appendtextbox(self, _inp):
		self.textbox.config(state = tk.NORMAL)
		self.textbox.insert(tk.END, str(_inp) )
		self.textbox.yview_moveto(1.0)
		self.textbox.update()
		self.textbox.config(state = tk.DISABLED)

	def cancel(self):
		self.__stopoperation()
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

		self.datagrabbtns = ( (_DEF["eventfile"], 1), (".json files", 2), ("None", 0) )
		self.blockszvals = dict( [ (convertunit(i,"B") , i) for i in [2**pw for pw in range(12, 28)]] )

		super().__init__( parent, "Settings")

	def body(self, master):
		'''UI'''
		datagrab_labelframe = tk.LabelFrame(master, text="Get bookmark information via...", padx=8, pady=8)
		for i, j in self.datagrabbtns:
			b = ttk.Radiobutton(datagrab_labelframe, variable = self.datagrabmode_var, text = i, value = j)
			b.pack()

		preview_labelframe = tk.LabelFrame(master, text="Display", padx=8, pady=8)
		ttk.Checkbutton(preview_labelframe, variable = self.preview_var, text="Preview demos?").pack()

		steampath_labelframe = tk.LabelFrame(master, text="Steam path", padx=8, pady=8)
		self.steampathentry = ttk.Entry(steampath_labelframe, state = "readonly", textvariable = self.steampath_var)
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

"""class AboutHelp(_BaseDialog):#TODO: Finish this
	def __init__(self, parent):
		self.parent = parent
		super().__init__(parent, "DemoMgr - About / Help")

	def body(self, master):
		githublnk = tk.Label(master, text="See the README.md on github", fg="blue", cursor="hand2")
		githublnk.bind("<Button-1> <ButtonRelease-1>", lambda e: webbrowser.open("http://www.github.com/Square789/Demomgr/master/README.md"))

		mesg = tk.Message(master, text="Demomgr Version {VER}, created by {AUTHOR}.".format(VER = __version__, AUTHOR = __author__))

		githublnk.pack()
		mesg.pack()"""

class BookmarkSetter(_BaseDialog): #TODO: Work on this.
	def __init__(self, parent, options):
		'''Args: parent tkinter window, options dict with:

		targetdemo: Full path to the demo that should be marked.'''
		self.targetdemo = options["targetdemo"]
		
		self.jsonmark_var = tk.BooleanVar()
		self.eventsmark_var = tk.BooleanVar()
		super().__init__(parent, "Insert bookmark...")

	def body(self, parent):
		def numchecker(inp):
			try:
				int(inp)
				return True
			except ValueError:
				return False

		marksel_labelframe = tk.LabelFrame(parent, text = "Mark demo in:")
		jsonsel_checkbox = ttk.Checkbutton(marksel_labelframe, text = "json file", variable = self.jsonmark_var)
		eventssel_checkbox = ttk.Checkbutton(marksel_labelframe, text = "_events file", variable = self.eventsmark_var)

		tickinp_frame = tk.Frame(marksel_labelframe)
		tk.Label(tickinp_frame, text = "Mark at: ").pack(side = tk.LEFT)
		regid = parent.register(numchecker)
		tick_entry = tk.Entry(tickinp_frame, validate = "key", validatecommand = (regid, "%S"))

		markbtn = tk.Button(parent, text = "Mark!")
		cancelbtn = tk.Button(parent, text = "Cancel", command = self.cancel)

		jsonsel_checkbox.pack()
		eventssel_checkbox.pack()
		marksel_labelframe.pack(expand = 1, fill = tk.BOTH)

		tick_entry.pack(side = tk.LEFT)
		tickinp_frame.pack()

		markbtn.pack(fill = tk.X, side = tk.LEFT)
		cancelbtn.pack(fill = tk.X, side = tk.LEFT)

	def __mark(self):#NOTE: Probably multithread, idk it's not like this'll take eons
		markJson, markEvts = self.jsonmark_var.get(), self.eventsmark_var.get()
		if markJson:
			pass
		if markEvts:
			pass

		self.cancel()

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
		msg = (	"The configuration file could not be " + ("read from" * ifread + "written to" * self.mode) +
				", meaning it was " + ("either corrupted, deleted, " * ifread) + "made inaccessible" + (" or has bad values" * ifread) +
				".\nDemomgr can not continue but you can select from the options below.\n\nRetry: Try performing the" +
				" action again\nReplace: Write the default config to the config path, then retry.\nQuit: Quit Demomgr" +
				"\n\n{}: {}".format(self.error.__class__.__name__, str(self.error))
			)
		slickframe = tk.Frame(parent, relief = tk.GROOVE, border = 5)
		msg_label = tk.Label(slickframe, font = ("TkDefaultFont", 10), wrap = 400, text = msg)
		self.inf_updating = tk.Label(slickframe, font = ("TkDefaultFont", 10), wrap = 400, text = "Attempting to rewrite default config...")
		self.err_rewrite_fail = tk.Label(slickframe, font = ("TkDefaultFont", 10), wrap = 400)
		retrybtn = tk.Button(parent, text = "Retry", command = self.__retry)
		replbtn = tk.Button(parent, text = "Replace", command = self.__replacecfg)
		quitbtn = tk.Button(parent, text = "Quit", command = self.__quit)

		slickframe.pack(expand = 1, fill = tk.BOTH)
		msg_label.pack(side = tk.TOP, expand = 1, fill = tk.BOTH)
		retrybtn.pack(fill = tk.X, side = tk.LEFT, expand = 1)
		replbtn.pack(fill = tk.X, side = tk.LEFT, expand = 1)
		quitbtn.pack(fill = tk.X, side = tk.LEFT, expand = 1)

	def cancel(self):
		self.__quit()

	def __retry(self):
		self.result_ = 0
		self.destroy()

	def __replacecfg(self):
		cfgtowrite = _DEF["defaultcfg"]
		try:
			self.err_rewrite_fail.pack_forget()
			self.inf_updating.pack(side = tk.TOP, expand = 1, fill = tk.BOTH)
			os.makedirs(_DEF["cfgfolder"], exist_ok = True)
			handle = open(self.cfgpath, "w")
			handle.write(json.dumps(cfgtowrite, indent = 4))
			handle.close()
			self.cfg = _DEF["defaultcfg"]
		except Exception as exception:
			self.inf_updating.pack_forget()
			self.err_rewrite_fail.config(text = "Rewrite failed: {}".format( str(exception) )  )
			self.err_rewrite_fail.pack(side = tk.TOP, expand = 1, fill = tk.BOTH)
			return
		self.result_ = 1
		self.destroy()

	def __quit(self):
		self.result_ = 2
		self.destroy()

class MainApp():
	def __init__(self):
		'''Init values, variables, go through startup routine, then show main window.'''

		self.root = tk.Tk()
		self.root.withdraw()

		self.root.bind("<<MultiframeSelect>>", self.__updatedemowindow)
		self.root.bind("<<MultiframeRightclick>>", self.__popupmenu)

		self.root.wm_title("Demomgr v" + __version__ + " by " + __author__)

		if os.path.exists(os.path.join(os.getcwd(), _DEF["iconname"])):
			self.root.iconbitmap(_DEF["iconname"])

		self.demooperations = ( ("Play", " selected demo...", self.__playdem), ("Delete", " selected demo...", self.__deldem) )#, ("Insert bookmark", " into selected demo...", self.__insertbookmark) )
		#NOTE: The tuple above has to be in here instead of in _DEF because of the reference to local "private" class methods

		self.workingdir = os.getcwd()
		self.cfgpath = os.path.join(self.workingdir, os.path.join(_DEF["cfgfolder"], _DEF["cfgname"]))
		self.curdir = "" # NOTE: This path should not be in self.cfg["demopaths"] at any time!
		self.bookmarkdata = []

		self.after_handlers = {"statusbar":self.root.after(0, lambda: True), "datafetcher":self.root.after(0, lambda: True), "filter":self.root.after(0, lambda: True), } # Used to access output queues filled by threads
		self.threads = {"datafetcher":threading.Thread(target = lambda: True), "filterer":threading.Thread(target = lambda: True), } # Dummy threads
		self.queues = {"datafetcher": queue.Queue(), "filter": queue.Queue(), } # Thread output queues

		self.spinboxvar = tk.StringVar() 					#spbxv

		self.mainframe = tk.Frame(self.root, padx = 5, pady = 3)
		self.mainframe.pack(expand = 1, fill = tk.BOTH, side = tk.TOP, anchor = tk.NW)

		self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

		# Startup routine
		# NOTE : Merge into __init__(), i don't know why this even is a seperate method.
		startupres = self.__startup()
		if startupres["res"] == -1:
			tk_msg.showerror("Demomgr - Error", "The following error occurred during startup: " + startupres["msg"])
			sys.exit()
		elif startupres["res"] == 1:
			d = FirstRunDialog(self.mainframe)
			if not d.result: # Is either None; 1 or 0
				self.quit_app()
				sys.exit()
			self.cfg["firstrun"] = False
			self.writecfg(self.cfg)

		#set up UI
		self.cfg = self.getcfg()
		self.__setupgui()
		self.spinboxvar.trace("w", self.__spinboxsel) 		#spbxv
		if os.path.exists(self.cfg["lastpath"]):
			self.spinboxvar.set(self.cfg["lastpath"]) 		#spbxv
		elif self.cfg["demopaths"]:
			self.spinboxvar.set(self.cfg["demopaths"][0])	#spbxv; This will call self.__spinboxsel -> self.reloadgui, so the frames are filled.
		self.root.deiconify() #end startup; show UI

	def __startup(self):
		'''Will go through a startup routine, then return a value whether startup was successful, this is first launch etc.'''
		if os.path.exists(self.cfgpath):
			self.cfg = self.getcfg()
			if self.cfg["firstrun"]:
				return {"res":1, "msg":"Firstlaunch"}
		else:
			try:
				os.makedirs(_DEF["cfgfolder"], exist_ok = True)
				self.writecfg(_DEF["defaultcfg"])
				self.cfg = _DEF["defaultcfg"]
			except Exception as exception:
				return {"res":-1, "msg":str(exception)}
			return {"res":1, "msg":"Firstlaunch"}
		return {"res":0, "msg":"Success."}

	def __setupgui(self):
		'''Sets up UI inside of the self.mainframe widget'''
		self.filterentry_var = tk.StringVar()

		widgetframe0 = tk.Frame(self.mainframe) #Directory Selection, Settings/About #NOTE: Resquash into tkinter.Menu ?
		widgetframe1 = tk.Frame(self.mainframe) #Filtering
		widgetframe2 = tk.Frame(self.mainframe) #General utilites
		widgetframe3 = tk.Frame(self.mainframe) #Buttons here interact with the currently selected demo
		self.listboxframe = tk.Frame(self.mainframe)
		demoinfframe = tk.Frame(self.mainframe, padx=5, pady=5)
		self.statusbar = tk.Frame(self.mainframe)

		self.listbox = mfl.Multiframe(self.listboxframe, columns=4, names=["Filename", "Bookmarks?", "Date created", "Filesize"], sort = 2, sorters=[True, False, True, True], widths = [None, 26, 16, 10], formatters = [None, None, formatdate, convertunit])

		#self.emptyfoldernot = tk.Label(self.listboxframe, text = "This folder is empty.")#TODO: Add fancy info label

		self.pathsel_spinbox = ttk.Combobox(widgetframe0, state = "readonly")
		self.pathsel_spinbox.config(values = tuple(self.cfg["demopaths"]))
		self.pathsel_spinbox.config(textvariable = self.spinboxvar)

		rempathbtn = tk.Button(widgetframe0, text = "Remove demo path", command = self.__rempath)
		addpathbtn = tk.Button(widgetframe0, text = "Add demo path...", command = self.addpath)
		settingsbtn = tk.Button(widgetframe0, text = "Settings...", command = self.__opensettings)
		#abouthelpbtn = tk.Button(widgetframe0, text = "About/Help...", command = self.__showabout)

		self.demoinfbox = tk_scr.ScrolledText(demoinfframe, wrap = tk.WORD, state=tk.DISABLED, width = 40)
		self.demoinflabel = tk.Label(demoinfframe, text=_DEF["demlabeldefault"])

		filterlabel = tk.Label(widgetframe1, text="Filter demos: ")
		filterentry = ttk.Entry(widgetframe1, textvariable=self.filterentry_var)
		self.filterbtn = tk.Button(widgetframe1, text="Apply Filter", command = self.__filter)
		self.resetfilterbtn = tk.Button(widgetframe1, text="Clear Filter / Refresh", command = self.reloadgui)

		cleanupbtn = tk.Button(widgetframe2, text="Cleanup...", command = self.__cleanup)
		
		demoopbuttons = [tk.Button(widgetframe3, text = i[0] + i[1], command = i[2] ) for i in self.demooperations]

		self.statusbarlabel = ttk.Label(self.statusbar, text="Ready.")

		#pack
		self.statusbarlabel.pack(anchor=tk.W)
		self.statusbar.pack(fill=tk.X, expand=0, side=tk.BOTTOM)

		#widgetframe0
		self.pathsel_spinbox.pack(side=tk.LEFT, fill = tk.X, expand = 1)
		rempathbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		addpathbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		tk.Label(widgetframe0, text="", width=3).pack(side=tk.LEFT) #Placeholder
		settingsbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)
		#tk.Label(widgetframe0, text="", width=3).pack(side=tk.LEFT) #Placeholder
		#abouthelpbtn.pack(side=tk.LEFT, fill = tk.X, expand = 0)

		widgetframe0.pack(anchor = tk.N, fill = tk.X, pady = 5, padx = 3)

		#widgetframe1
		filterlabel.pack(side = tk.LEFT, fill = tk.X, expand=0)
		filterentry.pack(side = tk.LEFT, fill = tk.X, expand=1)
		self.filterbtn.pack(side = tk.LEFT, fill = tk.X, expand=0)
		self.resetfilterbtn.pack(side = tk.LEFT, fill = tk.X, expand=0)

		widgetframe1.pack(anchor = tk.N, fill = tk.X, pady = 5)

		#widgetframe2
		cleanupbtn.pack(side = tk.LEFT, fill = tk.X, expand=0)

		widgetframe2.pack(anchor = tk.N, fill = tk.X, pady = 5)

		#widgetframe3
		for i in demoopbuttons:
			i.pack(side = tk.LEFT, fill = tk.X, expand=0)
			tk.Label(widgetframe3, text="", width=3).pack(side=tk.LEFT) #Placeholder

		widgetframe3.pack(anchor = tk.N, fill = tk.X, pady = 5)

		self.listbox.pack(fill=tk.BOTH, expand=1)
		#place
		#self.emptyfoldernot.place(relx = .2, rely = .2)
		#pack
		self.listboxframe.pack(fill=tk.BOTH, expand = 1, side = tk.LEFT)

		self.demoinflabel.pack(fill=tk.BOTH, expand = 0, anchor= tk.W)
		self.demoinfbox.pack(fill=tk.BOTH, expand = 1)
		demoinfframe.pack(fill=tk.BOTH, expand = 1)

	def quit_app(self): #NOTE:without this, the root.destroy method will produce an error on closing, due to some dark magic regarding after commands in self.setstatusbar.
		for k in self.threads:
			if self.threads[k].isAlive():
				self.threads[k].join()
		try: self.root.destroy() # Safe destroy probably better/cleaner than self.root.quit()
		except tk.TclError: pass

	def __cleanup(self):
		'''Opens dialog offering demo deletion'''
		if self.curdir == "":
			return
		try:
			files = self.listbox.getcolumn(0)
			dates = self.listbox.getshadowdata(mfl.COLUMN)[2]
			filesizes = self.listbox.getshadowdata(mfl.COLUMN)[3]
			#[i for i in os.listdir(self.curdir) if os.path.splitext(i)[1] == ".dem" and (os.path.isfile(os.path.join(self.curdir, i)))]
		except Exception:
			return
		dialog_ = DeleteDemos(self.mainframe, {"cfg":self.cfg, "curdir":self.curdir, "bookmarkdata":self.bookmarkdata, "files":files, "dates":dates, "filesizes":filesizes } )
		if dialog_.result_["state"] == 1:
			self.reloadgui()

	def __opensettings(self):
		'''Opens settings, acts based on results'''
		dialog_ = Settings(self.mainframe, self.getcfg())
		if dialog_.result:
			localcfg = self.cfg
			localcfg.update(dialog_.result)
			self.writecfg(localcfg)
			self.cfg = self.getcfg()
			self.reloadgui()

	def __playdem(self):
		'''Opens dialog which confirms tf2 launch'''
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.", 1500)
			return
		filename = self.listbox.getcell(0, index)
		path = os.path.join(self.curdir, filename)
		if os.path.splitext(path)[1] != ".dem":
			return
		dialog = LaunchTF2(self.mainframe, {"demopath":path, "steamdir":self.cfg["steampath"]} )
		if "steampath" in dialog.result_:
			if dialog.result_["steampath"] != self.cfg["steampath"]:
				self.cfg["steampath"] = dialog.result_["steampath"]
				self.writecfg(self.cfg)
				self.cfg = self.getcfg()

	"""def __showabout(self):
		dialog_ = AboutHelp(self.mainframe)"""

	def __deldem(self):
		"""Deletes the currently selected demo"""
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.",1500)
			return
		filename = self.listbox.getcell(0, index)
		dialog = Deleter(self.root, {"cfg":self.cfg, "files":[filename], "selected": [True], "demodir":self.curdir, "keepeventsfile": False, "deluselessjson":False} )
		if dialog.result_["state"] != 0:
			self.reloadgui()

	def __insertbookmark(self):
		index = self.listbox.getselectedcell()[1]
		if index == None:
			self.setstatusbar("Please select a demo file.",1500)
			return
		filename = self.listbox.getcell(0, index)
		path = os.path.join(self.curdir, filename)
		dialog_ = BookmarkSetter(self.root, {"targetdemo":path})

	def __updatedemowindow(self, _):
		'''Renew contents of demo information window'''
		index = self.listbox.getselectedcell()[1]
		if _ == None:
			self.demoinflabel.config(text="Preview window")
			self.demoinfbox.config(state=tk.NORMAL)
			self.demoinfbox.delete("0.0", tk.END)
			self.demoinfbox.insert(tk.END, "")
			self.demoinfbox.config(state=tk.DISABLED)
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
			outdict = readdemoheader(os.path.join(self.curdir, demname))
			deminfo = "\n".join([str(k) + " : " + str(outdict[k]) for k in outdict])
			del outdict #End headerinf
			entry = None#Get bookmarks
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
		except Exception:
			#demname = "?"
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
		clickedlist = self.listbox.getselectedcell()[0]
		clickx, clicky = self.listbox.getlastclick()
		listboxx, listboxy = self.listboxframe.winfo_rootx(), self.listboxframe.winfo_rooty()
		#get coords to create the menu on
		menu = tk.Menu(self.mainframe, tearoff = 0)
		for i in self.demooperations:
			menu.add_command(label = i[0] + "...", command = i[2])#construct menu
		menu.post(self.listbox.frames[clickedlist][0].winfo_rootx() + clickx, self.listbox.frames[clickedlist][0].winfo_rooty() + clicky + 20) #20 is label height. I hope that won't change.

	def reloadgui(self):
		'''Should be called after a directory change or to re-fetch a directory's contents.'''
		self.root.after_cancel(self.after_handlers["datafetcher"])
		self.listbox.clear()
		for k in self.threads:
			if self.threads[k].isAlive():
				self.threads[k].join()
		for k in self.queues:
			self.queues[k].queue.clear()
		self.threads["datafetcher"] = Thread_ReadFolder(None, self.queues["datafetcher"], {"curdir":self.curdir, "cfg":self.cfg.copy(), })
		self.threads["datafetcher"].start()
		self.after_handlers["datafetcher"] = self.root.after(0, self.__after_callback_fetchdata)
		self.__updatedemowindow(None)

	def __after_callback_fetchdata(self):
		finished = False
		while True:
			try:
				queueobj = self.queues["datafetcher"].get_nowait()
				if queueobj[0] == "SetStatusbar":
					self.setstatusbar(*queueobj[1]) #Note the asterisk
				elif queueobj[0] == "Finish":
					finished = True
				elif queueobj[0] == "Result":
					self.listbox.setdata(queueobj[1], "column")
					self.listbox.format()
				elif queueobj[0] == "Bookmarkdata":
					self.bookmarkdata = queueobj[1]
			except queue.Empty:
				break
		if not finished:
			self.after_handlers["datafetcher"] = self.root.after(_DEF["GUI_UPDATE_WAIT"], self.__after_callback_fetchdata)
		else:
			self.root.after_cancel(self.after_handlers["datafetcher"])

	def __filter(self):
		self.filterbtn.config(text = "Stop Filtering", command = lambda: self.__stopfilter(True) )
		self.resetfilterbtn.config(state = tk.DISABLED)
		self.threads["filterer"] = Thread_Filter(None, self.queues["filter"], {"filterstring":self.filterentry_var.get(), "curdir":self.curdir, "cfg":self.cfg.copy(), } )
		self.threads["filterer"].start()
		self.after_handlers["filter"] = self.root.after(0, self.__after_callback_filter)
		
	def __stopfilter(self, called_by_user = False):
		self.threads["filterer"].join()
		self.queues["filter"].queue.clear()
		self.root.after_cancel(self.after_handlers["filter"])
		if called_by_user:
			self.setstatusbar("", 0) #TODO: Fix this issue where when the thread is stopped via button, statusbar does not get changed.
		self.resetfilterbtn.config(state = tk.NORMAL)
		self.filterbtn.config(text = "Apply Filter", command = self.__filter)
		self.__updatedemowindow(None)

	def __after_callback_filter(self):
		finished = False
		while True:
			try:
				queueobj = self.queues["filter"].get_nowait()
				if queueobj[0] == "Finish":
					finished = True
				elif queueobj[0] == "SetStatusbar":
					self.setstatusbar(*queueobj[1])
				elif queueobj[0] == "Result":
					self.listbox.setdata(queueobj[1], "row")
					self.listbox.format()
			except queue.Empty:
				break
		if not finished:
			self.after_handlers["filter"] = self.root.after(_DEF["GUI_UPDATE_WAIT"], self.__after_callback_filter)
		else:
			self.__stopfilter()

	def __spinboxsel(self, *_):
		'''Observer callback to self.spinboxvar; is called whenever self.spinboxvar (so the combobox) is updated. Also triggered by self.__rempath'''
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
		'''Set statusbar text to data (str)'''
		self.statusbarlabel.after_cancel(self.after_handlers["statusbar"])
		self.statusbarlabel.config(text = str(data))
		self.statusbarlabel.update()
		if timeout != None:
			self.after_handlers["statusbar"] = self.statusbarlabel.after(timeout, lambda: self.setstatusbar(_DEF["statusbardefault"]) )
			#NOTE: This causes some issues with the commands that are registered internally within tkinter

	def addpath(self):
		'''Adds a demo folder path and writes to config after validating'''
		dirpath = tk_fid.askdirectory(initialdir = "C:\\", title = "Select the folder containing your demos.")
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

	def __rempath(self):
		localcfg = self.cfg
		if len(localcfg["demopaths"]) == 0:
			return
		popindex = localcfg["demopaths"].index(self.curdir)
		localcfg["demopaths"].pop(popindex)
		self.writecfg(self.cfg)
		self.cfg = self.getcfg()
		if len(localcfg["demopaths"]) > 0:
			self.spinboxvar.set(localcfg["demopaths"][(popindex -1) % len(localcfg["demopaths"])])
		else:
			self.spinboxvar.set("")
		self.pathsel_spinbox.config(values = tuple(localcfg["demopaths"]))

	def writecfg(self, data):
		'''Writes config dict specified in data to self.cfgpath, converted to JSON.
		On write error, calls the CfgError dialog, blocking until the issue is fixed.'''
		write_ok = False
		while not write_ok:
			handleexists = False
			try:
				handle = open(self.cfgpath, "w")
				handleexists = True
				handle.write(json.dumps(data, indent=4)) #NOTE:Indent unnecessary, remove eventually.
				if handleexists:
					handle.close()
				write_ok = True
			except Exception as error:
				if handleexists:
					handle.close()
				dialog = CfgError(self.mainframe, self.cfgpath, error, 1)
				if dialog.result_ == 0: # Retry
					pass
				elif dialog.result_ == 1: # Config replaced by dialog
					pass
				elif dialog.result_ == 2: # Quit
					self.quit_app()
					sys.exit()

	def getcfg(self):
		'''Gets config from self.cfgpath and returns it. On error, blocks until
		program is closed, config is replaced or fixed.'''
		localcfg = _DEF["defaultcfg"].copy()
		cfg_ok = False
		while not cfg_ok:
			handleexists = False
			try:
				cfghandle = open(self.cfgpath, "r")
				handleexists = True
				localcfg.update(json.load(cfghandle))
				#TODO: REFURBISH, demopaths is hardcoded badly.
				for k in _DEF["defaultcfg_types"]:
					if k == "demopaths":
						if not all( (isinstance(i, str) for i in localcfg[k]) ):
							raise ValueError("Bad config type: Non-String type in demopaths")
						if "" in localcfg[k]:
							raise ValueError("Unallowed directory: \"\" in demopaths")
					if not _DEF["defaultcfg_types"][k] == type(localcfg[k]):
						raise ValueError( "Bad config type: {} is not of type \"{}\"".format(localcfg[k].__repr__(), _DEF["defaultcfg_types"][k].__name__) )
				cfg_ok = True
			except (json.decoder.JSONDecodeError, FileNotFoundError, ValueError, OSError) as error:
				if handleexists:
					cfghandle.close()
				dialog = CfgError(self.mainframe, self.cfgpath, error, 0)
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

if __name__ == "__main__":
	mainapp = MainApp() #TODO: log potential errors to .demomgr/err.log
	mainapp.root.mainloop()
