"""Contains the ThreadReadFolder class."""

import os
import json
import time

from demomgr.demo_info import parse_events, parse_json
from demomgr.helpers import assign_demo_info
from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import constants as CNST

class ThreadReadFolder(_StoppableBaseThread):
	"""
	Thread to read a directory containing demos and return a list of names,
	creation dates, demo information and filesizes.
	"""

	def __init__(self, queue_out, targetdir, cfg):
		"""
		Thread requires an output queue and the following args:
			targetdir <Str>: Full path to the directory to be read out
			cfg <Dict>: Program configuration
		"""
		self.targetdir = targetdir
		self.cfg = cfg

		super().__init__(None, queue_out)

	def __stop(self, statmesg, result, exitcode, demo_amount = 0):
		"""
		Outputs end signals to self.queue_out.
		If the first arg is None, the Statusbar tuple will not be output.
		"""
		if statmesg is not None:
			self.queue_out_put(THREADSIG.INFO_STATUSBAR, statmesg)

		self.queue_out_put(THREADSIG.RESULT_DEMO_AMOUNT, demo_amount)
		self.queue_out_put(THREADSIG.RESULT_DEMODATA, result)
		self.queue_out_put(exitcode)

	def run(self):
		"""
		Get data from all the demos in current folder;
		return it in a format that can be directly fed into listbox.
		"""
		if self.targetdir is None:
			self.__stop(None, None, THREADSIG.FAILURE, 0)
			return
		self.queue_out_put(
			THREADSIG.INFO_STATUSBAR,
			(f"Reading demo information from {self.targetdir} ...", None),
		)
		starttime = time.time()

		try:
			files = [
				i for i in os.listdir(self.targetdir)
				if os.path.splitext(i)[1] == ".dem" and
					os.path.isfile(os.path.join(self.targetdir, i))
			]
			datescreated = [os.path.getmtime(os.path.join(self.targetdir, i)) for i in files]
			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return
			sizes = [os.path.getsize(os.path.join(self.targetdir, i)) for i in files]
			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return
		except FileNotFoundError:
			self.__stop(
				(f"ERROR: Current directory {self.targetdir!r} does not exist.", None),
				{},
				THREADSIG.FAILURE,
			)
			return
		except (OSError, PermissionError) as error:
			self.__stop((f"ERROR reading directory: {error}.", None), {}, THREADSIG.FAILURE)
			return

		# Grab demo information (returned through col_demo_info)
		datamode = self.cfg.data_grab_mode
		if datamode == 0: #Disabled
			self.__stop(
				("Demo information disabled.", 3000),
				{
					"col_filename": files, "col_ks": [None] * len(files),
					"col_bm": [None] * len(files), "col_ctime": datescreated,
					"col_filesize": sizes,
				},
				THREADSIG.SUCCESS,
			)
			return

		elif datamode == 1: #_events.txt
			try:
				with open(os.path.join(self.targetdir, CNST.EVENT_FILE), "r") as h:
					logchunk_list = parse_events(h, self.cfg.events_blocksize)
			except Exception as exc:
				self.__stop(
					(
						f"{CNST.EVENT_FILE!r} has not been found, can not be opened or "
							f"is malformed.",
						5000,
					),
					{
						"col_filename": files, "col_ks": [None] * len(files),
						"col_bm": [None] * len(files), "col_ctime": datescreated,
						"col_filesize": sizes,
					},
					THREADSIG.FAILURE,
				)
				return

		elif datamode == 2: #.json
			try: # Get json files
				jsonfiles = [
					i for i in os.listdir(self.targetdir) if
					os.path.splitext(i)[1] == ".json" and
					os.path.exists(os.path.join(self.targetdir, os.path.splitext(i)[0] + ".dem"))
				]
			except (OSError, FileNotFoundError, PermissionError) as error:
				self.__stop(
					(f"Error getting .json files: {error}", 5000),
					{
						"col_filename": files, "col_ks": [None] * len(files),
						"col_bm": [None] * len(files), "col_ctime": datescreated,
						"col_filesize": sizes
					},
					THREADSIG.FAILURE,
				)
				return

			logchunk_list = []
			for json_file in jsonfiles:
				if self.stoprequest.is_set():
					self.queue_out_put(THREADSIG.ABORTED)
					return
				try: # Attempt to open the json file
					file_stem = os.path.splitext(json_file)[0]
					with open(os.path.join(self.targetdir, json_file)) as h:
						logchunk_list.append(parse_json(h,  file_stem + ".dem"))
				except (OSError, PermissionError, FileNotFoundError) as error:
					continue
				except (json.decoder.JSONDecodeError, KeyError, ValueError) as error:
					continue

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		# Parallelize, order of _events.txt uncertain; json likely retrieved in bad order.
		logchunk_list = assign_demo_info(files, logchunk_list)
		# Create final demo info lists
		killstreaks = [None] * len(logchunk_list)
		bookmarks = [None] * len(logchunk_list)
		for i, chunk in enumerate(logchunk_list):
			if chunk is None:
				continue
			killstreaks[i] = chunk.killstreaks
			bookmarks[i] = chunk.bookmarks

		self.__stop(
			(
				f"Processed data from {len(files)} files in "
				f"{round(time.time() - starttime, 4)} seconds.",
				3000
			),
			{
				"col_filename": files, "col_ks": killstreaks, "col_bm": bookmarks,
				"col_ctime": datescreated, "col_filesize": sizes
			},
			THREADSIG.SUCCESS,
			len(files),
		)
		return
