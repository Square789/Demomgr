'''Threads used for keeping the interface responsive.'''

# Code needs massive rewriting and looks horrible

import threading
import queue
import shutil

import os
import time
import re
import json

from _helpers import (FileStatFetcher, HeaderFetcher,
assignbookmarkdata, getstreakpeaks, formatbookmarkdata, readevents)

from _filterlogic import filterstr_to_lambdas

import handle_events as handle_ev
import _constants as _DEF

class _StoppableBaseThread(threading.Thread):
	''' This thread has a killflag (stoprequest <threading.Event>),
		and expects a queue_in and queue_out attribute in the constructor.
		It also takes args and kwargs. The stopflag can be set by calling the
		thread's join() method, however regularly has to be checked for in
		the run method.
		The stopflag can be ignored by passing a third arg that is evaluated
		to True to the join() method.
		Override this thread's run() method, start by calling start() !'''
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

class ThreadDeleter(_StoppableBaseThread):
	'''Thread takes no queue_inp, but an additional dict with the following keys:
		keepeventsfile <Bool>: Whether to create a backup of _events.txt
		demodir <Str>: Absolute directory to delete demos in.
		files <List[Str]>: List of all files in demodir.
		selected <List[Bool]>: List of bools of same length as files.
		filestodel <List[Str]>: Simple file names of the files to be removed;
		[j for i, j in enumerate(files) if selected[i]];
		cfg <Dict>: Program configuration as in .demomgr/config.cfg
		eventfileupdate <Str; "passive"|"selectivemove">: eventfile update mode.
	'''
	def run(self):
		self.options = self.args[0].copy()
		evtpath = os.path.join(self.options["demodir"], _DEF.EVENT_FILE)
		del self.args
		if self.options["keepeventsfile"]: #---Backup _events file
			try:
				if os.path.exists(evtpath): #This will fail when demodir is blocked
					backupfolder = os.path.join(os.getcwd(), _DEF.CFG_FOLDER, _DEF.EVENT_BACKUP_FOLDER)
					if not os.path.exists(backupfolder):
						os.makedirs(backupfolder)
					i = 0
					while True:
						if os.path.exists( os.path.join(backupfolder, os.path.splitext(_DEF.EVENT_FILE)[0] + str(i) + ".txt" )  ): #enumerate files: _events0.txt; _events1.txt; _events2.txt ...
							i += 1
						else:
							break
					self.queue_out.put( ( "ConsoleInfo", "\nCreating eventfile backup at " + os.path.join(os.getcwd(), _DEF.CFG_FOLDER, _DEF.EVENT_BACKUP_FOLDER, (os.path.splitext(_DEF.EVENT_FILE)[0] + str(i) + ".txt") ) + " .\n"  ) )
					shutil.copy2( os.path.join(self.options["demodir"], _DEF.EVENT_FILE), os.path.join(os.getcwd(), _DEF.CFG_FOLDER, _DEF.EVENT_BACKUP_FOLDER, (os.path.splitext(_DEF.EVENT_FILE)[0] + str(i) + ".txt") )  )
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
		self.queue_out.put( ("ConsoleInfo", "\n\nUpdating " + _DEF.EVENT_FILE + "..." ) ) #---Update eventfile; NOTE: NO CHECK FOR STOPREQUEST IN HERE; WILL ONLY ADD COMPLEXITY DUE TO HAVING TO CLOSE OPEN RESOURCES.
		if os.path.exists(evtpath):
			tmpevtpath = os.path.join(self.options["demodir"], "." + _DEF.EVENT_FILE)
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
						regres = re.search(_DEF.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						if regres: curchunkname = regres[0] + ".dem"
						else: curchunkname = ""
						if not curchunkname in self.options["filestodel"]:#create a new list of okay files or basically waste twice the time going through all the .json files?
							writer.writechunk(outchunk)
						if outchunk.message["last"]: break

				elif self.options["eventfileupdate"] == "selectivemove":#Requires to have entire dir/actual files present in self.files;
					okayfiles = set([j for i, j in enumerate(self.options["files"]) if not self.options["selected"][i]])
					while True:
						chunkexists = False
						outchunk = next(reader)
						regres = re.search(_DEF.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						if regres: curchunkname = regres[0] + ".dem"
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

class ThreadFilter(_StoppableBaseThread):
	'''Thread takes no queue_inp, but queue_out and args[0] as a dict with the following keys:
		filterstring <Str>:Raw user input from the entry field
		curdir <Str>: Absolute path to current directory
		cfg <Dict>: Program configuration as in .demomgr/config.cfg
	'''
	def run(self):
		self.options = self.args[0].copy()
		filterstring = self.options["filterstring"]
		curdir = self.options["curdir"]
		cfg = self.options["cfg"]
		starttime = time.time()

		self.queue_out.put(  ("SetStatusbar", ("Filtering demos; Parsing filter...", ) )  )
		try:
			filters = filterstr_to_lambdas(filterstring)
		except Exception as error:
			self.queue_out.put(  ("SetStatusbar",
				("Error parsing filter request: " + str(error), 4000) )  )
			self.queue_out.put( ("Finish", 0) ); return

		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) ); return

		self.queue_out.put(  ("SetStatusbar", ("Filtering demos; Reading information...", ) )  )
		bookmarkdata = None
		files = None
		self.datafetcherqueue = queue.Queue()
		self.datafetcherthread = ThreadReadFolder(None, self.datafetcherqueue, {"curdir":curdir, "cfg":cfg, })
		self.datafetcherthread.start()
		self.datafetcherthread.join(None, 1) # NOTE: Severe wait time?
		if self.stoprequest.isSet():
			self.queue_out.put( ("Finish", 2) ); return

		while True:
			try:
				queueobj = self.datafetcherqueue.get_nowait()
				if queueobj[0] == "Result":
					files = queueobj[1]["col_filename"]
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

		filteredlist = {"col_filename":[], "col_bookmark":[], "col_ctime":[], "col_filesize":[], }
		file_amnt = len(files)
		for i, j in enumerate(files): #Filter
			self.queue_out.put(  ("SetStatusbar", ("Filtering demos; {} / {}".format(i + 1, file_amnt), ) )  )
			curdataset = {"name":j, "killstreaks":asg_bmd[i][1], "bookmarks":asg_bmd[i][2], "header": HeaderFetcher(os.path.join(curdir, j)), "filedata": FileStatFetcher(os.path.join(curdir, j))}
			#The Fetcher classes prevent unneccessary drive access when the user i.E. only filters by name
			for l in filters:
				if not l(curdataset):
					break
			else:
				filteredlist["col_filename"].append(curdataset["name"])
				if len(curdataset["bookmarks"]) + len(curdataset["killstreaks"]) == 0:
					filteredlist["col_bookmark"].append("None")
				else:
					filteredlist["col_bookmark"].append("{} Bookmarks;"
						" {} Killstreaks".format(
						str(len(curdataset["bookmarks"])),
						str(len(curdataset["killstreaks"]))))
				filteredlist["col_ctime"   ].append(curdataset["filedata"]["modtime"])
				filteredlist["col_filesize"].append(curdataset["filedata"]["filesize"])
			if self.stoprequest.isSet():
				self.queue_out.put( ("Finish", 2) ); return
		del filters
		self.queue_out.put( ("Result", filteredlist) )
		self.queue_out.put(  ("SetStatusbar", ("Filtered {} demos in {} seconds.".format(file_amnt, str(round(time.time() - starttime, 3)) ), 3000) )  )
		self.queue_out.put( ("Finish", 1) )

class ThreadReadFolder(_StoppableBaseThread):
	'''Thread takes no queue_inp, but queue_out and as args[0] a dict with the
	following keys:
	curdir <Str>: Full path to the directory to be read out
	cfg <Dict>: Program configuration as in .demomgr/config.cfg
	'''
	def __stop(self, statmesg, result, exitcode):
		'''Outputs end signals to self.queue_out, every arg will be output
		as [1] in a tuple where [0] is - in that order - "SetStatusbar",
		"Result", "Finish". If the first arg is None, the "SetStatusbar"
		tuple will not be output.
		'''
		if statmesg is not None:
			self.queue_out.put( ("SetStatusbar", statmesg ) )
		self.queue_out.put( ("Result", result) )
		self.queue_out.put( ("Finish", exitcode) )
	
	def run(self):
		'''Get data from all the demos in current folder; return in format that can be directly put into listbox'''
		self.options = self.args[0].copy()
		if self.options["curdir"] == "":
			self.__stop(None, {}, 0); return
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
			self.__stop( ("ERROR: Current directory \"{}\" does not exist.".format(self.options["curdir"]), None), {}, 0); return
		except (OSError, PermissionError) as error:
			self.__stop( ("ERROR reading directory: {}.".format(str(error)), None), {}, 0); return

		# Grab bookmarkdata
		datamode = self.options["cfg"]["datagrabmode"]
		if datamode == 0: #Disabled
			self.queue_out.put( ("Bookmarkdata", (("", (), ()) for _ in files) ) )
			self.__stop( ("Bookmark information disabled.", 2000), 
				{"col_filename":files, "col_bookmark":["" for _ in files],
				"col_ctime":datescreated, "col_filesize":sizes}, 1)
			return
		elif datamode == 1: #_events.txt
			handleopen = False
			try:
				h = open(os.path.join(self.options["curdir"], _DEF.EVENT_FILE), "r")
				handleopen = True
				bookmarklist = readevents(h, self.options["cfg"]["evtblocksz"])
				#TODO: ADD ERROR TYPE IN handle_events, then make this better!
				h.close()
				self.queue_out.put( ("Bookmarkdata", bookmarklist ) )
			except Exception:
				if handleopen: h.close()
				self.__stop( ("\"{}\" has not been found, can not be opened or is malformed.".format(_DEF.EVENT_FILE), 5000),
					{"col_filename":files, "col_bookmark":["" for i in files],
					"col_ctime":datescreated, "col_filesize":sizes}, 0)
				return
		elif datamode == 2: #.json
			try:
				jsonfiles = [i for i in os.listdir(self.options["curdir"]) if os.path.splitext(i)[1] == ".json" and os.path.exists(os.path.join(self.options["curdir"], os.path.splitext(i)[0] + ".dem"))]
			except (OSError, FileNotFoundError, PermissionError) as error:
				self.__stop( ("Error getting .json files: {}".format(str(error)), 5000),
					{"col_filename":files, "col_bookmark":["" for i in files],
					"col_ctime":datescreated, "col_filesize":sizes}, 0)
				return
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

		data = {"col_filename":files, "col_bookmark":listout, "col_ctime":datescreated, "col_filesize":sizes}
		self.__stop( ("Processed data from {} files in {} seconds.".format( len(files), round(time.time() - starttime, 4) ), 3000), data, 1); return
