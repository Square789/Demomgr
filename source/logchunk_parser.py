import re

from source.helpers import getstreakpeaks
from source import handle_events as handle_ev

RE_LINE = re.compile(r'\[(\d{4}/\d\d/\d\d \d\d:\d\d)\] (Killstreak|Bookmark)'
	' (.*) \("([^"]*)" at (\d*)\)')
# takes ~120 steps, other three regexes take ~ 300 steps altogether

class GROUP:
	DATE = 1
	TYPE = 2
	VALUE = 3
	DEMO = 4
	TICK = 5

class ParsedLogchunk():
	'''Contains two attributes:
		demo_name <Str>: The name of the demo that is described in the
			logchunk.
		bookmarks <Tuple>: Bookmarks (including killstreaks):
			((killstreakpeak <Int>, tick <Int>), ...),
			(bookmarkname <Str>, tick <Int>), ...))
	'''
	def __init__(self, demo_name, bookmarks):
		self.demo_name = demo_name
		self.bookmarks = bookmarks

def parse_logchunk(in_chk):
	'''Takes a handle_events.Logchunk and converts it into a ParsedLogchunk.'''
	loglines = in_chk.content.split("\n")
	if not loglines:
		raise ValueError("Logchunks may not be empty.")
	demo = RE_LINE.search(loglines[0])[GROUP.DEMO] + ".dem"

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
	events = (killstreaks, bookmarks)

	return ParsedLogchunk(demo, events)

def read_events(handle, blocksz):
	'''This function reads an events.txt file as it's written by the source
	engine, returns (filename, ( (killstreakpeak, tick)... ),
		( (bookmarkname, tick)... ) ).
	May raise exceptions.
	'''
	reader = handle_ev.EventReader(handle, blocksz=blocksz)
	out = []
	for chk in reader:
		p_l = parse_logchunk(chk)
		out.append((p_l.demo_name, p_l.bookmarks[0], p_l.bookmarks[1]))
	reader.destroy()
	return out
