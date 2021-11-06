"""
Contains the DemoInfo class and offers ability to construct it
from either a handle_events.RawLogchunk or a json file.
"""

import re

from demomgr.helpers import getstreakpeaks
from demomgr import handle_events as handle_ev

RE_LINE = re.compile(r'\[(\d{4}/\d\d/\d\d \d\d:\d\d)\] (Killstreak|Bookmark)'
	r' (.*) \("([^"]*)" at (\d+)\)')

class GROUP:
	DATE = 1
	TYPE = 2
	VALUE = 3
	DEMO = 4
	TICK = 5

class DemoInfo():
	"""Container class to hold information regarding a demo."""

	__slots__ = ("demo_name", "killstreaks", "bookmarks")

	def __init__(self, demo_name, killstreaks, bookmarks):
		"""
		demo_name: The name of the demo that is described in the
			logchunk. (str)
		killstreaks <Tuple/List>: Killstreaks:
			[(streak <Int>, tick <Int>), ...]
		bookmarks <Tuple/List>: Bookmarks:
			[(bookmarkname <Str>, tick <Int>), ...)]
		"""
		self.demo_name = demo_name
		self.killstreaks = killstreaks
		self.bookmarks = bookmarks

	@classmethod
	def from_json(cls, json_data, demo_name):
		"""
		Parses the given data which should be retrieved from a standard format
		json file and turns it into a DemoInfo instance.

		json_data: Dict converted from a JSON file as the source engine writes it.
		demo_name: Name of associated demo file; i.e. "foo.dem". (str)

		May raise: KeyError, ValueError
		"""
		cur_bm = []
		cur_ks = []

		for k in json_data["events"]:
			if k["name"] == "Killstreak":
				cur_ks.append((int(k["value"]), int(k["tick"])))
			elif k["name"] == "Bookmark":
				cur_bm.append((k["value"], int(k["tick"])))
		return cls(demo_name, cur_ks, cur_bm)

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
				killstreaks.append((int(value), tick))
			elif line_type == "Bookmark":
				bookmarks.append((value, tick))
		killstreaks = getstreakpeaks(killstreaks)

		return cls(demo, killstreaks, bookmarks)

def parse_events(handle, blocksz):
	"""
	This function reads an events.txt file as it's written by the source
	engine, returns a list of DemoInfo instances containing demo name,
	killstreaks and bookmarks.

	handle : Open file handle to the events file. Must be readable.
	blocksz : Block size the handle file should be read in. (int)
	May raise OSError, PermissionError, ValueError.
	"""
	with handle_ev.EventReader(handle, blocksz=blocksz) as reader:
		return [DemoInfo.from_raw_logchunk(chk) for chk in reader]
