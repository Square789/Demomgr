"""Various helper functions and classes used all over the program."""

import os
import datetime
import struct
import re
from tkinter.ttk import Frame, Label
from math import log10, floor

from demomgr import constants as CNST

_CONVPREF = ["y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T",
	"P", "E", "Z", "Y", ]
_CONVPREF_CENTER = 8

class CfgReducing:
	REQUIRED_CFG_KEYS = ()

	@classmethod
	def reduce_cfg(class_, cfg):
		"""
		Reduces input cfg only to the values required for this thread/dialog.
		(Class attribute `REQUIRED_CFG_KEYS`)
		Will not create copies or perform error checks, so make sure only
		immutables are used and cfg is actually complete.
		"""
		return {k: cfg[k] for k in class_.REQUIRED_CFG_KEYS}

def build_date_formatter(cfg):
	"""
	Creates a date formatter method that takes an UNIX timestamp and
	converts it to what's dictated by "date_fmt" in the supplied cfg
	dict, value not bound to cfg.
	"""
	dfmt = cfg["date_format"]
	return lambda ts: datetime.datetime.fromtimestamp(ts).strftime(dfmt)

def convertunit(inp, ext = "B"):
	"""
	Unit conversion function. Takes an integer as input, rounds off the
	number to the last 3 digits and returns it as a string followed by an
	order of magnitude identifier + ext .
	"""
	isneg = inp < 0
	if inp == 0:
		return f"0 {ext}"
	if isneg:
		inp = abs(inp)
	mag = floor(log10(inp)) // 3
	return (
		f"{isneg * '-'}{round((inp / (10**(mag*3))), 3)}"
		f"{_CONVPREF[_CONVPREF_CENTER + mag]}{ext}"
	)

def deepupdate_dict(target, update):
	"""
	Updates dicts and calls self recursively if a list or dict is encountered
	to perform updating at nesting levels instead of just the first one.
	Does not work with tuples.
	"""
	for k, v in update.items():
		if isinstance(v, list):
			target[k] = target.get(k, []) + v
		elif isinstance(v, dict):
			target[k] = deepupdate_dict(target.get(k, {}), v)
		else:
			target[k] = v
	return target

def readbinStr(handle, leng = 260):
	"""Reads file handle by leng bytes and attempts to decode to utf-8."""
	rawbin = handle.read(leng)
	bin = rawbin.strip(b"\x00")
	return bin.decode("utf-8")

def readbinInt(handle, leng = 4):
	rawbin = handle.read(leng)
	return struct.unpack("i", rawbin)[0]

def readbinFlt(handle):
	rawbin = handle.read(4)
	return struct.unpack("f", rawbin)[0]

def readdemoheader(path): #Code happily duplicated from https://developer.valvesoftware.com/wiki/DEM_Format
	"""
	Reads the header information of a demo. May raise exceptions on
	denied read access or malformed demos.
	"""
	demhdr = CNST.FALLBACK_HEADER.copy()

	h = open(path, "rb")
	if readbinStr(h, 8) == "HL2DEMO":
		demhdr["dem_prot"] = readbinInt(h)
		demhdr["net_prot"] = readbinInt(h)
		demhdr["hostname"] = readbinStr(h)
		demhdr["clientid"] = readbinStr(h)
		demhdr["map_name"] = readbinStr(h)
		demhdr["game_dir"] = readbinStr(h)
		demhdr["playtime"] = readbinFlt(h)
		demhdr["tick_num"] = readbinInt(h)
		demhdr["framenum"] = readbinInt(h)
		demhdr["tickrate"] = int(demhdr["tick_num"] / demhdr["playtime"]) if \
			demhdr["playtime"] != 0.0 else -1
	h.close()

	return demhdr

def getstreakpeaks(killstreaks):
	"""
	Takes a list of tuples where: element 0 is a number and 1 is a time
	tick (which is ignored), then only returns the tuples that make up the
	peak of their sequence.
	For example: (1,2,3,4,5,6,1,2,1,2,3,4) -> (6,2,4) [Only element 0 of
	the tuples displayed].
	This function does not perform any sorting, input is expected to already
	be in a correct order.
	"""
	streakpeaks = []
	if killstreaks:
		localkillstreaks = killstreaks.copy()
		localkillstreaks.append((-1, -1))
		prv = (-1, -1)
		for i in localkillstreaks:
			if i[0] <= prv[0]:
				streakpeaks.append(prv)
			prv = i
	return streakpeaks

def assign_demo_info(files, demo_info):
	"""
	Creates a list where each DemoInfo object in demo_info is sitting next
	to its file. If a file does not have a relevant entry in demo_info,
	it will have None matched up instead.

	files : List of file names ["abc.dem", "def.dem", ...]
	demo_info : List of DemoInfo instances.
	"""
	assigned_dat = [None for _ in files]
	for i, file in enumerate(files):
		for j in demo_info:
			if j.demo_name == file:
				assigned_dat[i] = j
				break
	return assigned_dat

def format_bm_pair(toformat):
	"""
	Formats a primitive killstreak/bookmark pair ((), ())
	into a readable string.
	"""
	if toformat is None:
		return "None"
	return f"{len(toformat[0])} Killstreaks; {len(toformat[1])} Bookmarks"

def frmd_label(parent, text,
		styles = ("Framed.Contained.TFrame", "Labelframe.Contained.TLabel")):
	"""
	Returns a ttk.Frame object containing a ttk.Label with text specified
	that is supposed to be integrated into a Labelframe.
	styles defaults to a tuple of ("Framed.Contained.TFrame",
	"Labelframe.Contained.TLabel").
	"""
	frm = Frame(parent, style = styles[0], padding = 1)
	lbl = Label(frm, text = text, style = styles[1], padding = (3, 0))
	lbl.pack()
	return frm

def tk_secure_str(in_str, repl = None):
	"""
	If any character in in_str is out of tkinter's char displaying range
	(0x0000 - 0xFFFF), it will be replaced with the constant REPLACEMENT_CHAR.
	This can be overridden by passing repl as an additional parameter.
	"""
	if repl is None:
		repl = CNST.REPLACEMENT_CHAR
	return "".join((i if ord(i) <= 0xFFFF else repl) for i in in_str)

def int_validator(inp, ifallowed):
	"""
	Test whether only (positive) integers are being keyed into a widget.
	Call signature: %S %P
	"""
	if len(ifallowed) > 10:
		return False
	try:
		return int(inp) >= 0
	except ValueError:
		return False
	return True

def name_validator(ifallowed):
	"""
	Limit length of string to 40 chars
	Call signature: %P
	"""
	if len(ifallowed) > 40:
		return False
	return True