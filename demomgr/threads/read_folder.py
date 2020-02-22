'''Contains the ThreadReadFolder class.'''

import os
import queue
import json
import time

from demomgr.constants import THREADSIG
from demomgr.helpers import (assignbookmarkdata, getstreakpeaks)
from demomgr.logchunk_parser import read_events, Logchunk
from demomgr.threads._base import _StoppableBaseThread
from demomgr import constants as CNST

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
		"""
		Outputs end signals to self.queue_out.
		If the first arg is None, the Statusbar tuple will not be output.
		"""
		if statmesg is not None:
			self.queue_out_put(THREADSIG.INFO_STATUSBAR, statmesg)
		self.queue_out_put(THREADSIG.RESULT_DEMODATA, result)
		self.queue_out_put(exitcode)

	def run(self):
		'''
		Get data from all the demos in current folder;
		return it in a format that can be directly fed into listbox.
		'''
		if self.options["targetdir"] == "":
			self.__stop(None, {}, THREADSIG.FAILURE); return
		self.queue_out_put(THREADSIG.INFO_STATUSBAR,
			("Reading demo information from {} ...".format(self.options["targetdir"]), None))
		starttime = time.time()

		try:
			files = [i for i in os.listdir(self.options["targetdir"]) if (os.path.splitext(i)[1] == ".dem")
				and (os.path.isfile(os.path.join(self.options["targetdir"], i)))]
			datescreated = [os.path.getmtime(os.path.join(self.options["targetdir"], i)) for i in files]
			if self.stoprequest.isSet():
				self.queue_out_put(THREADSIG.ABORTED); return
			sizes = [os.path.getsize(os.path.join(self.options["targetdir"], i)) for i in files]
			if self.stoprequest.isSet():
				self.queue_out_put(THREADSIG.ABORTED); return
		except FileNotFoundError:
			self.__stop(
				("ERROR: Current directory \"{}\" does not exist.".format(
					self.options["targetdir"]), None),
				{}, THREADSIG.FAILURE)
			return
		except (OSError, PermissionError) as error:
			self.__stop(("ERROR reading directory: {}.".format(str(error)), None),
				{}, THREADSIG.FAILURE)
			return

		# Grab bookmarkdata (returned through col_bookmark)
		datamode = self.options["cfg"]["datagrabmode"]
		if datamode == 0: #Disabled
			self.__stop(
				("Bookmark information disabled.", 3000),
				{"col_filename": files, "col_bookmark": [None for _ in files],
					"col_ctime": datescreated, "col_filesize": sizes},
				THREADSIG.SUCCESS)
			return
		elif datamode == 1: #_events.txt
			handleopen = False
			try:
				with open(os.path.join(self.options["targetdir"], CNST.EVENT_FILE), "r") as h:
					logchunk_list = read_events(h, self.options["cfg"]["evtblocksz"])
			except Exception as exc:
				self.__stop(
					("\"{}\" has not been found, can not be opened or is malformed.".format(
						CNST.EVENT_FILE), 5000),
					{"col_filename": files, "col_bookmark": [None for _ in files],
						"col_ctime": datescreated, "col_filesize": sizes}, THREADSIG.FAILURE)
				return
		elif datamode == 2: #.json
			try: # Get json files
				jsonfiles = [i for i in os.listdir(self.options["targetdir"]) if os.path.splitext(i)[1] == ".json"]
				jsonfiles = [i for i in jsonfiles if os.path.exists(os.path.join(self.options["targetdir"], os.path.splitext(i)[0] + ".dem"))]
			except (OSError, FileNotFoundError, PermissionError) as error:
				self.__stop(
					("Error getting .json files: {}".format(str(error)), 5000),
					{"col_filename": files, "col_bookmark": [None for _ in files],
						"col_ctime": datescreated, "col_filesize": sizes},
					THREADSIG.FAILURE)
				return

			logchunk_list = []
			for json_file in jsonfiles:
				cur_ks = []
				cur_bm = []
				if self.stoprequest.isSet():
					self.queue_out_put(THREADSIG.ABORTED); return
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
			self.queue_out_put(THREADSIG.ABORTED)
			return

		listout = assignbookmarkdata(files, logchunk_list) #PARALLELIZE BOOKMARKDATA WITH FILES
		listout = [((i.killstreaks, i.bookmarks) if i is not None else None) for i in listout] # Reduce to just the relevant data

		self.__stop(
			("Processed data from {} files in {} seconds.".format(
				len(files), round(time.time() - starttime, 4)
			), 3000),
			{"col_filename": files, "col_bookmark": listout,
				"col_ctime": datescreated, "col_filesize": sizes},
			THREADSIG.SUCCESS)
		return
