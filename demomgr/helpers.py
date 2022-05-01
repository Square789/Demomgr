"""Various helper functions and classes used all over the program."""

import datetime
import struct
from tkinter.ttk import Frame, Label
from math import log10, floor

from demomgr import constants as CNST

_CONVPREF = (
	"y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T",
	"P", "E", "Z", "Y"
)
_CONVPREF_CENTER = 8


def build_date_formatter(fmt):
	"""
	Creates a date formatter method that takes an UNIX timestamp and
	converts it to what's dictated by the given `fmt`.
	"""
	return lambda ts: datetime.datetime.fromtimestamp(ts).strftime(fmt)

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
		f"{isneg * '-'}{round((inp / (10**(mag * 3))), 3)}"
		f"{_CONVPREF[_CONVPREF_CENTER + mag]}{ext}"
	)

def deepupdate_dict(target, update):
	"""
	Updates dicts and calls itself recursively if a list or dict is encountered
	to perform updating at nesting levels instead of just the first one.
	Does not work with tuples.
	"""
	for k, v in update.items():
		if isinstance(v, list):
			target_obj = target.get(k, [])
			target[k] = (target_obj + v) if isinstance(target_obj, list) else v
		elif isinstance(v, dict):
			target_obj = target.get(k, {})
			target[k] = deepupdate_dict(target_obj, v) if isinstance(target_obj, dict) else v
		else:
			target[k] = v
	return target

def readbin_str(handle, leng = 260):
	"""Reads file handle by leng bytes and attempts to decode to utf-8."""
	rawbin = handle.read(leng)
	bin = rawbin.strip(b"\x00")
	return bin.decode("utf-8")

def readbin_int(handle, leng = 4):
	rawbin = handle.read(leng)
	return struct.unpack("i", rawbin)[0]

def readbin_flt(handle):
	rawbin = handle.read(4)
	return struct.unpack("f", rawbin)[0]

# Code happily duplicated from https://developer.valvesoftware.com/wiki/DEM_Format
def readdemoheader(path):
	"""
	Reads the header information of a demo.
	May raise:
		- OSError on denied read access or other file failures.
		- ValueError on malformed demos.
	"""
	demhdr = {}
	with open(path, "rb") as h:
		if readbin_str(h, 8) != "HL2DEMO":
			raise ValueError("Malformed demo, expected `HL2DEMO` header")
		try:
			demhdr["dem_prot"] = readbin_int(h)
			demhdr["net_prot"] = readbin_int(h)
			demhdr["hostname"] = readbin_str(h)
			demhdr["clientid"] = readbin_str(h)
			demhdr["map_name"] = readbin_str(h)
			demhdr["game_dir"] = readbin_str(h)
			demhdr["playtime"] = readbin_flt(h)
			demhdr["tick_num"] = readbin_int(h)
			demhdr["framenum"] = readbin_int(h)
			demhdr["tickrate"] = int(demhdr["tick_num"] / demhdr["playtime"]) if \
				demhdr["playtime"] != 0.0 else -1
		except struct.error as exc:
			raise ValueError() from exc

	return demhdr

def getstreakpeaks(killstreaks):
	"""
	Takes a list of DemoEvents, then returns a list of only the tuples
	whose values make up the peak of their sequence.
	For example if values of DemoEvents were: (1,2,3,4,5,6,1,2,1,2,3,4),
	the function would deliver the DemoEvents for (6,2,4).
	This function does not perform any sorting, input is expected to already
	be in a correct order.
	"""
	streakpeaks = []

	if not killstreaks:
		return streakpeaks

	prv = None
	for event in killstreaks:
		if prv is not None and event.value <= prv.value:
			streakpeaks.append(prv)
		prv = event
	# Get last streak, won't attach (-1, -1) since killstreaks is at least 1 element long
	streakpeaks.append(prv)

	return streakpeaks

def frmd_label(
		parent, text,
		styles = ("Framed.Contained.TFrame", "Labelframe.Contained.TLabel")
	):
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

def name_validator(ifallowed):
	"""
	Limit length of string to 40 chars
	Call signature: %P
	"""
	if len(ifallowed) > 40:
		return False
	return True
