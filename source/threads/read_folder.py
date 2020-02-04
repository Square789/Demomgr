'''Contains the ThreadReadFolder class.'''

import os
import queue
import json
import time

from source.threads._base import _StoppableBaseThread
from source.helpers import (assignbookmarkdata, getstreakpeaks)
from source.logchunk_parser import read_events, Logchunk
from source import constants as CNST

class ThreadReadFolder(_StoppableBaseThread):
	"""
	Thread to read a directory containing demos and return a list of names,
	creation dates, bookmarkdata and filesizes.
	"""

	def __init__(self, queue_out, targetdir, cfg, *args, **kwargs):
		"""
		Thread requires an output queue and the following kwargs:
		targetdir <Str>: Full path to the directory to be read out
		cfg <Dict>: Program configuration as in .demomgr/config.cfg
		"""
		self.options = {"targetdir": targetdir, "cfg": cfg}

		super().__init__(None, queue_out, *args, **kwargs)

	def __stop(self, statmesg, result, exitcode):
		'''Outputs end signals to self.queue_out, every arg will be output
		as [1] in a tuple where [0] is - in that order - "SetStatusbar",
		"Result", "Finish". If the first arg is None, the "SetStatusbar"
		tuple will not be output.
		'''
		if statmesg is not None:
			self.queue_out.put(("SetStatusbar", statmesg))
		self.queue_out.put(("Result", result))
		self.queue_out.put(("Finish", exitcode))

	def run(self):
		'''Get data from all the demos in current folder; return in format that can be directly put into listbox'''
		if self.options["targetdir"] == "":
			self.__stop(None, {}, 0); return
		self.queue_out.put(("SetStatusbar", ("Reading demo information from {} ...".format(self.options["targetdir"]), None)))
		starttime = time.time()

		try:
			files = [i for i in os.listdir(self.options["targetdir"]) if (os.path.splitext(i)[1] == ".dem")
				and (os.path.isfile(os.path.join(self.options["targetdir"], i)))]
			datescreated = [os.path.getmtime(os.path.join(self.options["targetdir"], i)) for i in files]
			if self.stoprequest.isSet():
				self.queue_out.put(("Finish", 2)); return
			sizes = [os.path.getsize(os.path.join(self.options["targetdir"], i)) for i in files]
			if self.stoprequest.isSet():
				self.queue_out.put(("Finish", 2)); return
		except FileNotFoundError:
			self.__stop(("ERROR: Current directory \"{}\" does not exist.".format(self.options["targetdir"]), None), {}, 0); return
		except (OSError, PermissionError) as error:
			self.__stop(("ERROR reading directory: {}.".format(str(error)), None), {}, 0); return

		# Grab bookmarkdata (returned through col_bookmark)
		datamode = self.options["cfg"]["datagrabmode"]
		if datamode == 0: #Disabled
			self.__stop(
				("Bookmark information disabled.", 2000),
				{"col_filename": files, "col_bookmark": [None for _ in files],
					"col_ctime": datescreated, "col_filesize": sizes},
				1); return
		elif datamode == 1: #_events.txt
			handleopen = False
			try:
				h = open(os.path.join(self.options["targetdir"], CNST.EVENT_FILE), "r")
				handleopen = True
				bookmarklist = read_events(h, self.options["cfg"]["evtblocksz"])
				h.close()
			except Exception as exc:
				if handleopen: h.close()
				self.__stop(
					("\"{}\" has not been found, can not be opened or is malformed.".format(CNST.EVENT_FILE), 5000),
					{"col_filename":files, "col_bookmark":[None for _ in files],
						"col_ctime":datescreated, "col_filesize":sizes},
					0); return
		elif datamode == 2: #.json
			try: # Get json files
				jsonfiles = [i for i in os.listdir(self.options["targetdir"]) if os.path.splitext(i)[1] == ".json"]
				jsonfiles = [i for i in jsonfiles if os.path.exists(os.path.join(self.options["targetdir"], os.path.splitext(i)[0] + ".dem"))]
			except (OSError, FileNotFoundError, PermissionError) as error:
				self.__stop(
					("Error getting .json files: {}".format(str(error)), 5000),
					{"col_filename": files, "col_bookmark": [None for _ in files],
						"col_ctime": datescreated, "col_filesize": sizes},
					0); return

			logchunk_list = []
			for json_file in jsonfiles:
				cur_ks = []
				cur_bm = []
				if self.stoprequest.isSet():
					self.queue_out.put(("Finish", 2)); return
				try: # Attempt to open the json file
					h = open(os.path.join(self.options["targetdir"], json_file))
				except (OSError, PermissionError, FileNotFoundError) as error:
					logchunk_list.append(Logchunk("", (), ()))
					continue
				try: # Attempt to parse the json
					curjson = json.load(h)
				except json.decoder.JSONDecodeError as error:
					logchunk_list.append(Logchunk("", (), ()))
					h.close()
					continue
				h.close() # JSON now loaded and present in curjson.

				for k in curjson["events"]: # {"name":"Killstreak/Bookmark","value":"int/Name","tick":"int"}
					try:
						if k["name"] == "Killstreak":
							cur_ks.append((int(k["value"]), int(k["tick"])))
						elif k["name"] == "Bookmark":
							cur_bm.append((k["value"], int(k["tick"])))
					except (ValueError, TypeError, KeyError):
						cur_ks = []
						cur_bm = []
						break
				else: # When loop completes normally
					cur_ks = getstreakpeaks(cur_ks)
				logchunk_list.append(Logchunk(
					os.path.splitext(json_file)[0] + ".dem", cur_ks, cur_bm
				))

		if self.stoprequest.isSet():
			self.queue_out.put(("Finish", 2)); return

		listout = assignbookmarkdata(files, logchunk_list) #PARALLELIZE BOOKMARKDATA WITH FILES
		listout = [((i.killstreaks, i.bookmarks) if i is not None else None) for i in listout] # Reduce to just the relevant data

		self.__stop(
			("Processed data from {} files in {} seconds.".format(len(files), round(time.time() - starttime, 4)), 3000),
			{"col_filename":files, "col_bookmark":listout, "col_ctime":datescreated, "col_filesize":sizes},
			1); return
