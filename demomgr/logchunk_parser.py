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

class Logchunk():
	"""Container class to hold attributes of a logchunk."""
	def __init__(self, demo_name, killstreaks, bookmarks):
		"""
		demo_name <Str>: The name of the demo that is described in the
			logchunk.
		killstreaks <Tuple/List>: Killstreaks:
			[(streak <Int>, tick <Int>), ...]
		bookmarks <Tuple/List>: Bookmarks:
			[(bookmarkname <Str>, tick <Int>), ...)]
		"""
		self.demo_name = demo_name
		self.killstreaks = killstreaks
		self.bookmarks = bookmarks

def parse_logchunk(in_chk):
	"""
	Takes a handle_events.Logchunk and converts it into a Logchunk.

	in_chk : Full logchunk as it is read from file.
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

	return Logchunk(demo, killstreaks, bookmarks)

def read_events(handle, blocksz):
	"""
	This function reads an events.txt file as it's written by the source
	engine, returns a list of Logchunk instances containing demo name,
	killstreaks and bookmarks.

	handle : Open file handle to the events file. Must be readable.
	blocksz : Block size the handle file should be read in.
	May raise IOError, PermissionError, ValueError.
	"""
	with handle_ev.EventReader(handle, blocksz=blocksz) as reader:
		out = []
		for chk in reader:
			out.append(parse_logchunk(chk))
	return out
