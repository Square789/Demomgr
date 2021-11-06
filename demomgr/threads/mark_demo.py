"""Contains the ThreadMarkDemo class."""

import os
import json
import re
from datetime import datetime

from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import constants as CNST
from demomgr.handle_events import EventReader, EventWriter

RE_DEM_NAME = re.compile(
	r'\[\d{4}/\d\d/\d\d \d\d:\d\d\] (?:Killstreak|Bookmark) .* \("([^"]*)" at \d*\)$'
)
RE_TICK = re.compile(
	r'\[\d{4}/\d\d/\d\d \d\d:\d\d\] (?:Killstreak|Bookmark) .* \("[^"]*" at (\d*)\)'
)
RE_LOGLINE_IS_BOOKMARK = re.compile(r"\[\d\d\d\d/\d\d/\d\d \d\d:\d\d\] Bookmark ")

class ThreadMarkDemo(_StoppableBaseThread):
	"""
	Thread for modifying the bookmarks of a demo.

	Sent to the output queue:
		BOOKMARK_CONTAINER_UPDATE_START(1) at the start of a bookmark
				container update process.
			- Container type as an int.

		BOOKMARK_CONTAINER_UPDATE_SUCCESS(2) when a bookmark container
				is updated.
			- Container type as an int.
			- Boolean indicating whether the container now exists or not.

		BOOKMARK_CONTAINER_UPDATE_FAILURE(2) when a bookmark container
				update fails. Its existence state should be
				unchanged.
			- Container type as an int.
			- Error that occurred.

		INFO_CONSOLE(1) for thread information # TODO: remove (issue #31)
			- Text to be drawn whereever.
	"""
	def __init__(self, queue_out, mark_json, mark_events, bookmarks, targetdemo, evtblocksz):
		"""
		Thread takes an output queue and as the following args:
			mark_json <Bool>: Whether the .json file should be modified
			mark_events <Bool>: Whether the _events.txt file should be modified
			bookmarks <Seq[Tuple[Str, Int]]>: Bookmarks as a sequence of
				(name, tick) tuples.
			targetdemo <Str>: Absolute path to the demo to be marked.
			evtblocksz <Int>: Block size to read _events.txt in.
		"""
		self.mark_json = mark_json
		self.mark_events = mark_events
		self.bookmarks = bookmarks
		self.targetdemo = targetdemo
		self.evtblocksz = evtblocksz

		super().__init__(None, queue_out)

	def run(self):
		for container_type, should_mark, mark_func, exceptions in (
			(
				CNST.DATA_GRAB_MODE.JSON,
				self.mark_json,
				self._mark_json,
				(OSError, json.decoder.JSONDecodeError, KeyError, TypeError, ValueError),
			),
			(
				CNST.DATA_GRAB_MODE.EVENTS,
				self.mark_events,
				self._mark_events,
				(OSError, TypeError, ValueError),
			),
		):
			if not should_mark:
				continue

			try:
				res = mark_func()
				if res is not None: # if res is None, stop request has been set.
					self.queue_out_put(
						THREADSIG.BOOKMARK_CONTAINER_UPDATE_SUCCESS, container_type.value, res
					)
			except exceptions as error:
				self.queue_out_put(
					THREADSIG.BOOKMARK_CONTAINER_UPDATE_FAILURE, container_type.value, error
				)

			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return

		self.queue_out_put(THREADSIG.SUCCESS)

	def _mark_json(self):
		formatted_bookmarks = []
		for v, t in self.bookmarks:
			formatted_bookmarks.append({
				"name": CNST.EVENTFILE_BOOKMARK,
				"value": v,
				"tick": t,
			})

		full_json = os.path.splitext(self.targetdemo)[0] + ".json"
		json_data = {"events": []}
		if os.path.exists(full_json):
			with open(full_json, "r") as handle:
				json_data = json.load(handle)
		else:
			self.queue_out_put(THREADSIG.INFO_CONSOLE, "JSON file not found; Creating new.")

		json_data["events"] = [
			i for i in json_data["events"] if i["name"] != CNST.EVENTFILE_BOOKMARK
		]
		json_data["events"].extend(formatted_bookmarks)
		json_data["events"] = sorted(json_data["events"], key = lambda elem: elem["tick"])
		with open(full_json, "w") as handle:
			handle.write(json.dumps(json_data, indent = "\t"))
		self.queue_out_put(THREADSIG.INFO_CONSOLE, "JSON written.")
		return True

	def _mark_events(self):
		demo_name = os.path.splitext(os.path.basename(self.targetdemo))[0]
		demo_dir = os.path.dirname(self.targetdemo)

		curtime = datetime.now().strftime("%Y/%m/%d %H:%M")
		formatted_bookmarks = [
			f'[{curtime}] Bookmark {name} ("{demo_name}" at {tick})'
			for name, tick in self.bookmarks
		]

		evtpath = os.path.join(demo_dir, CNST.EVENT_FILE)
		if not os.path.exists(evtpath):
			self.queue_out_put(
				THREADSIG.INFO_CONSOLE, f"{CNST.EVENT_FILE} does not exist, creating empty."
			)
			open(evtpath, "w").close()

		if self.stoprequest.is_set():
			return None

		tmpevtpath = os.path.join(demo_dir, f".{CNST.EVENT_FILE}")
		interrupted = False
		with \
			EventReader(evtpath, blocksz = self.evtblocksz) as event_reader, \
			EventWriter(tmpevtpath, clearfile = True, empty_ok = True) as event_writer \
		:
			chunk_found = False
			chunk_exists = True
			# Run through chunks and modify the found one if it exists
			for chk in event_reader:
				if self.stoprequest.is_set():
					interrupted = True
					break
				regres = RE_DEM_NAME.search(chk.content)
				towrite = chk.content
				# Found chunk
				if regres is not None and regres[1] == demo_name:
					chunk_found = True
					towrite = [
						i for i in towrite.split("\n")
						if not RE_LOGLINE_IS_BOOKMARK.search(i)
					]
					towrite.extend(formatted_bookmarks)
					towrite = "\n".join(sorted(
						towrite, key = lambda elem: int(RE_TICK.search(elem)[1])
					))
					if not towrite:
						chunk_exists = False
						continue
					self.queue_out_put(THREADSIG.INFO_CONSOLE, "Logchunk found and modified.")
				event_writer.writechunk(towrite)

			# Append fabricated chunk if it was not found
			if not chunk_found:
				if formatted_bookmarks:
					event_writer.writechunk("\n".join(sorted(
						formatted_bookmarks, key = lambda elem: int(RE_TICK.search(elem)[1])
					)))
				else:
					chunk_exists = False

		if not interrupted:
			os.remove(evtpath)
			os.rename(tmpevtpath, evtpath)
		else:
			os.remove(tmpevtpath)
			return None

		return chunk_exists
