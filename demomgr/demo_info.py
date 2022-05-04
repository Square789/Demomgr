"""
Contains the DemoInfo class and offers ability to construct it
from either a handle_events.RawLogchunk or a json file.
"""

import os
import re

from demomgr.helpers import getstreakpeaks

RE_LINE = re.compile(
	r'\[(\d{4}/\d\d/\d\d \d\d:\d\d)\] (Killstreak|Bookmark)'
	r' (.*) \("(.*)" at (\d+)\)'
)

class GROUP:
	DATE = 1
	TYPE = 2
	VALUE = 3
	DEMO = 4
	TICK = 5

class DemoEvent():
	"""
	Simple event dataclass for a demo event.
	Supports setitem and getitem in range 0..2 mapping to
	`value`, `tick`, `time`.
	Instances are compared by `tick`.
	"""

	__slots__ = ("value", "tick", "time")

	def __init__(self, value, tick, time):
		"""
		value: Value of the event.
		tick <Int>: Tick the event occurred at.
		time <str/None>: Time the event was recorded at, in the format
			`YYYY/mm/dd HH:MM`. Unstable, I hope this is not influenced
			by any locales.
			May be None if the time could not be determined,
			realistically it only appears for events read from
			`_events.txt`.
		"""
		self.value = value
		self.tick = tick
		self.time = time

	def __setitem__(self, i, v):
		setattr(self, ("value", "tick", "time")[i], v)

	def __getitem__(self, i):
		return getattr(self, ("value", "tick", "time")[i])

	def __iter__(self):
		yield from (self.value, self.tick, self.time)

	def __gt__(self, other):
		if isinstance(other, DemoEvent):
			return self.tick > other.tick
		return NotImplemented

	def __lt__(self, other):
		if isinstance(other, DemoEvent):
			return self.tick < other.tick
		return NotImplemented


class DemoInfo():
	"""Container class to hold information regarding a demo."""

	__slots__ = ("demo_name", "killstreaks", "killstreak_peaks", "bookmarks")

	def __init__(self, demo_name, killstreaks, bookmarks):
		"""
		demo_name: The name of the demo that is described in the
			logchunk. (str)
		killstreaks <List>: Killstreaks as a list of DemoEvents.
		bookmarks <List>: Bookmarks as a list of DemoEvents.

		NOTE: `killstreak_peaks` will be invalidated if direct changes
			to `killstreaks` are made. Use `set_killstreaks` instead.
		"""
		# Funny dilemma: I know what properties are by now, but still
		# don't like code running just by setting an attribute.
		self.demo_name = demo_name
		self.killstreaks = killstreaks
		self.killstreak_peaks = getstreakpeaks(killstreaks)
		self.bookmarks = bookmarks

	def is_empty(self):
		"""
		Determines whether no events are stored in the DemoInfo.
		"""
		return not (self.killstreaks or self.bookmarks)

	@classmethod
	def from_json(cls, json_data, demo_name):
		"""
		Parses the given data which should be retrieved from a standard format
		JSON file and turns it into a DemoInfo instance.

		json_data: Dict converted from a JSON file as the source engine writes it.
		demo_name: Name of associated demo file; i.e. "foo.dem". (str)

		May raise: KeyError, ValueError, TypeError.
		"""
		cur_bm = []
		cur_ks = []

		for k in json_data["events"]:
			if k["name"] == "Killstreak":
				cur_ks.append(DemoEvent(int(k["value"]), int(k["tick"]), None))
			elif k["name"] == "Bookmark":
				cur_bm.append(DemoEvent(k["value"], int(k["tick"]), None))
		return cls(demo_name, cur_ks, cur_bm)

	def to_json(self):
		"""
		Converts the demo info to a JSON-compliant dict that can be
		written to a file and be reconstructed to an equal DemoInfo
		object by using `DemoInfo.from_json`.
		The event dicts will be ordered ascendingly by tick, just like
		they are produced by Team Fortress 2.

		May raise: ValueError if data has been screwed up.
		"""
		events = [{"name": "Killstreak", "value": v, "tick": t} for v, t, _ in self.killstreaks]
		events += [{"name": "Bookmark", "value": v, "tick": t} for v, t, _ in self.bookmarks]
		return {"events": sorted(events, key = lambda e: int(e["tick"]))}

	@classmethod
	def from_raw_logchunk(cls, in_chk):
		"""
		Takes a handle_events.RawLogchunk and converts it into DemoInfo.

		in_chk : RawLogchunk to process, as returned by an EventReader.

		May raise: ValueError on bad logchunks.
		"""
		loglines = in_chk.content.split("\n")
		if not loglines:
			raise ValueError("Logchunks may not be empty.")
		regres = RE_LINE.search(loglines[0])
		if not regres:
			raise ValueError("Regex match failed, Logchunk malformed.")
		demo = regres[GROUP.DEMO] + ".dem"

		killstreaks = []
		bookmarks = []
		for line in loglines:
			regres = RE_LINE.search(line)
			if regres is None:
				raise ValueError("Regex match failed, Logchunk malformed.")
			line_type = regres[GROUP.TYPE]
			value = regres[GROUP.VALUE]
			tick = int(regres[GROUP.TICK])
			if line_type == "Killstreak":
				killstreaks.append(DemoEvent(int(value), tick, regres[GROUP.DATE]))
			elif line_type == "Bookmark":
				bookmarks.append(DemoEvent(value, tick, regres[GROUP.DATE]))

		return cls(demo, killstreaks, bookmarks)

	def to_logchunk(self):
		"""
		Returns a string that can be written to an `_events.txt` file
		and will be interpretable as a valid logchunk by the events
		reader afterwards.
		All info is sorted by tick.

		May raise: ValueError if information has been messed up.
		"""
		demo_name = os.path.splitext(self.demo_name)[0]
		to_write = [("Killstreak", value, tick, date) for value, tick, date in self.killstreaks]
		to_write.extend(("Bookmark", value, tick, date) for value, tick, date in self.bookmarks)

		to_write.sort(key = lambda t: t[2])

		return "\n".join(
			f'[{date}] {type_} {value} ("{demo_name}" at {tick})'
			for type_, value, tick, date in to_write
		)

	def set_killstreaks(self, killstreaks):
		self.killstreaks = killstreaks
		self.killstreak_peaks = getstreakpeaks(killstreaks)
