"""Contains the ThreadMarkDemo class."""

import os
import queue
import json
import time
import re
from datetime import datetime

from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import constants as CNST
from demomgr import handle_events as handle_ev

RE_DEM_NAME = re.compile(r'\[\d{4}/\d\d/\d\d \d\d:\d\d\] (?:Killstreak|Bookmark)'
	' .* \("([^"]*)" at \d*\)$')
RE_TICK = re.compile(r'\[\d{4}/\d\d/\d\d \d\d:\d\d\] (?:Killstreak|Bookmark)'
	' .* \("[^"]*" at (\d*)\)')
RE_LOGLINE_IS_BOOKMARK = re.compile(
	r"\[\d\d\d\d/\d\d/\d\d \d\d:\d\d\] Bookmark ")

class ThreadMarkDemo(_StoppableBaseThread):
	"""
	Thread for modifying the bookmarks of a demo.
	"""
	def __init__(self, queue_out, mark_json, mark_events, bookmarks, targetdemo):
		"""
		Thread takes an output queue and as the following args:
			mark_json <Bool>: Whether the .json file should be modified
			mark_events <Bool>: Whether the _events.txt file should be modified
			bookmarks <Tuple>: Bookmarks in the standard bookmark format.
			targetdemo <Str>: Absolute path to the demo to be marked.
		"""
		self.mark_json = mark_json
		self.mark_events = mark_events
		self.bookmarks = bookmarks
		self.targetdemo = targetdemo

		super().__init__(None, queue_out)

	def run(self):
		if self.mark_json:
			try:
				self.__mark_json()
				self.queue_out_put(THREADSIG.INFO_CONSOLE,
					"Successfully modified json file.")
			except (OSError, PermissionError) as err: # File problems
				self.queue_out_put(THREADSIG.INFO_CONSOLE, str(err))
			except json.decoder.JSONDecodeError as err: # Json malformed
				self.queue_out_put(THREADSIG.INFO_CONSOLE, str(err))
			except (KeyError, IndexError, TypeError) as err: # Json garbage
				self.queue_out_put(THREADSIG.INFO_CONSOLE, str(err))

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		if self.mark_events:
			try:
				self.__mark_events()
				if self.stoprequest.is_set(): # Method may return due to user abort
					self.queue_out_put(THREADSIG.ABORTED)
					return
				self.queue_out_put(THREADSIG.INFO_CONSOLE, f"Successfully modified {CNST.EVENT_FILE}")
			except (PermissionError, OSError) as err:
				self.queue_out_put(THREADSIG.INFO_CONSOLE, str(err))
			except (TypeError, ValueError) as err:
				self.queue_out_put(THREADSIG.INFO_CONSOLE, str(err)) # Something is wrong with _events.txt
			except InterruptedError:
				self.queue_out_put(THREADSIG.ABORTED)
				return

		self.queue_out_put(THREADSIG.SUCCESS)

	def __mark_json(self):
		formatted_bookmarks = []
		for i in self.bookmarks:
			formatted_bookmarks.append({
				"name": CNST.EVENTFILE_BOOKMARK,
				"value": i[0],
				"tick": int(i[1]),
			})

		full_json = os.path.splitext(self.targetdemo)[0] + ".json"
		json_data = {"events":[]}
		if os.path.exists(full_json): # If json exists:
			with open(full_json, "r") as handle: # Load it
				json_data = json.load(handle)
		else:
			self.queue_out_put(THREADSIG.INFO_CONSOLE,
				"JSON file not found; Creating new.")
		json_data["events"] = [i for i in json_data["events"]
			if not i["name"] == CNST.EVENTFILE_BOOKMARK]
		json_data["events"].extend(formatted_bookmarks)
		json_data["events"] = sorted(json_data["events"],
			key = lambda elem: elem["tick"])
		if not json_data["events"]:
			self.queue_out_put(THREADSIG.INFO_CONSOLE,
				"JSON is empty, not writing/deleting file.")
			if os.path.exists(full_json):
				os.remove(full_json)
		else:
			with open(full_json, "w") as handle:
				handle.write(json.dumps(json_data, indent = 4))

	def __mark_events(self):
		demo_name = os.path.splitext(os.path.basename(self.targetdemo))[0]
		demo_dir = os.path.dirname(self.targetdemo)
		
		formatted_bookmarks = []
		curtime = datetime.now().strftime("%Y/%m/%d %H:%M")
		for i in self.bookmarks:
			formatted_bookmarks.append('[{}] Bookmark {} ("{}" at {})'.format(
				curtime, i[0], demo_name, i[1]))

		evtpath = os.path.join(demo_dir, CNST.EVENT_FILE)
		if not os.path.exists(evtpath):
			self.queue_out_put(THREADSIG.INFO_CONSOLE,
				f"{CNST.EVENT_FILE} does not exist, creating empty.")
			open(evtpath, "w").close()

		tmpevtpath = os.path.join(demo_dir, "." + CNST.EVENT_FILE)
		with handle_ev.EventReader(evtpath) as event_reader, \
				handle_ev.EventWriter(tmpevtpath,
				clearfile = True, empty_ok = True) as event_writer:
			chunkfound = False
			for chk in event_reader:
				if self.stoprequest.is_set():
					self.queue_out_put(THREADSIG.ABORTED)
					raise InterruptedError()
				regres = RE_DEM_NAME.search(chk.content)
				towrite = chk.content
				if regres is not None:
					if regres[1] == demo_name: #T'is the chk you're looking for
						chunkfound = True
						towrite = towrite.split("\n")
						towrite = [i for i in towrite if not
							RE_LOGLINE_IS_BOOKMARK.search(i)]
						towrite.extend(formatted_bookmarks)
						towrite = sorted(towrite, key = lambda elem:
							int(RE_TICK.search(elem)[1]))
						towrite = "\n".join(towrite)
				event_writer.writechunk(towrite)
			if not chunkfound:
				formatted_bookmarks = sorted(formatted_bookmarks,
					key = lambda elem: int(RE_TICK.search(elem)[1]))
				event_writer.writechunk("\n".join(formatted_bookmarks))
		os.remove(evtpath)
		os.rename(tmpevtpath, evtpath)
