"""
Contains the DemoInfo class and offers ability to construct it
from either a handle_events.RawLogchunk or a json file.
"""

import json
import re

from demomgr.helpers import getstreakpeaks
from demomgr import handle_events as handle_ev

RE_LINE = re.compile(r'\[(\d{4}/\d\d/\d\d \d\d:\d\d)\] (Killstreak|Bookmark)'
	r' (.*) \("([^"]*)" at (\d*)\)')

class GROUP:
	DATE = 1
	TYPE = 2
	VALUE = 3
	DEMO = 4
	TICK = 5

class DemoInfo():
	"""Container class to hold information regarding a demo."""
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

def parse_json(handle, demo_name):
	"""
	Parses the file handle which should contain a json file of a
	standard format and turns the contained data into DemoInfo.

	handle: Handle to read json from.
	demo_name: Name of associated demo file; i.e. "foo.dem". (str)

	May raise: IOError, json.decoder.JSONDecodeError, KeyError, ValueError
	"""
	cur_bm = []
	cur_ks = []

	curjson = json.load(handle)
	for k in curjson["events"]:
		if k["name"] == "Killstreak":
			cur_ks.append((int(k["value"]), int(k["tick"])))
		elif k["name"] == "Bookmark":
			cur_bm.append((k["value"], int(k["tick"])))
	cur_ks = getstreakpeaks(cur_ks)
	return DemoInfo(demo_name, cur_ks, cur_bm)

def parse_logchunk(in_chk):
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
		raise ValueError("Regex match failed, Logchunk likely malformed.")
	demo = regres[GROUP.DEMO] + ".dem"

	killstreaks = []
	bookmarks = []
	for line in loglines:
		regres = RE_LINE.search(line)
		line_type = regres[GROUP.TYPE]
		value = regres[GROUP.VALUE]
		tick = int(regres[GROUP.TICK])
		if line_type == "Killstreak":
			killstreaks.append((int(value), tick))
		elif line_type == "Bookmark":
			bookmarks.append((value, tick))
	killstreaks = getstreakpeaks(killstreaks)

	return DemoInfo(demo, killstreaks, bookmarks)

def parse_events(handle, blocksz):
	"""
	This function reads an events.txt file as it's written by the source
	engine, returns a list of DemoInfo instances containing demo name,
	killstreaks and bookmarks.

	handle : Open file handle to the events file. Must be readable.
	blocksz : Block size the handle file should be read in. (int)
	May raise IOError, PermissionError, ValueError.
	"""
	with handle_ev.EventReader(handle, blocksz=blocksz) as reader:
		out = []
		for chk in reader:
			out.append(parse_logchunk(chk))
	return out
