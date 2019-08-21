'''Various helper functions and classes used all over the program.'''

import os
import struct
import re
import datetime
from tkinter.ttk import Frame, Label
from math import log10, floor

from . import constants as CNST

#LIST HAS TO BE OF SAME LENGTH TO LEFT AND RIGHT SIDE, STARTING AT ""
_convpref = ["y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T",
	"P", "E", "Z", "Y", ]
def convertunit(inp, ext = "B"):
	'''Unit conversion function. Takes an integer as input, rounds off the
	number to the last 3 digits and returns it as a string followed by an
	order of magnitude identifier + ext .'''
	isneg = False
	if inp < 0:
		inp = abs(inp)
		isneg = True
	elif inp == 0:
		return "0 " + ext
	mag = floor(log10(inp)) // 3
	return isneg*"-" + str(round((inp / (10 ** (mag * 3))), 3)) + " " \
		+ _convpref[round(len(_convpref)/2) + mag] + ext
	#round(2.5) results in 2, which it technically shouldn't but that's good

def formatdate(inp):
	'''Turns unix timestamp into readable format (CNST.DATE_FORMAT)'''
	return datetime.datetime.fromtimestamp(inp).strftime(CNST.DATE_FORMAT)

def readbinStr(handle, leng = 260):
	'''Reads file handle by leng bytes and attempts to decode to utf-8.'''
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
	'''Reads the header information of a demo. May raise exceptions on
	denied read access or malformed demos.
	'''
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
		demhdr["tickrate"] = int(demhdr["tick_num"] / demhdr["playtime"])
	h.close()

	return demhdr

def getstreakpeaks(killstreaks):
	'''Takes a list of tuples where: element 0 is a number and 1 is a time
	tick (which is ignored), then only returns the tuples that make up the
	peak of their sequence.
	For example: (1,2,3,4,5,6,1,2,1,2,3,4) -> (6,2,4) [Only element 0 of
	the tuples displayed].
	This function does not perform any sorting, input is expected to already
	be in a correct order.
	'''
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

def assignbookmarkdata(files, bookmarkdata):
	'''Takes a list of files and the bookmarkdata; returns a list that
	contains the parallel bookmarkdata; None if no match found.
	'''
	assignedlogs = [None for _ in files]
	for i in bookmarkdata:
		for j in range(len(files)):
			if i[0] == files[j]:
				assignedlogs[j] = i
	return assignedlogs

def formatbookmarkdata(filelist, bookmarkdata):
	'''Converts bookmarkdata into a list of strings:
	"X Bookmarks, Y Killstreaks". needs filelist to assign bookmarkdata to.
	'''
	assignedlogs = assignbookmarkdata(filelist, bookmarkdata)
	listout = ["" for i in assignedlogs]
	for i in range(len(assignedlogs)): #convert the correctly assigned logs ("", [], []) into information displaying strings
		if assignedlogs[i] != ("", [], []):
			listout[i] = str(len(assignedlogs[i][2])) + " Bookmarks;" \
				" " + str(len(assignedlogs[i][1])) + " Killstreaks."
		else:
			listout[i] = "None"
	return listout

def format_bm_pair(toformat):
	'''Formats a bookmark pair ((), ()) into readable strings'''
	if toformat is None:
		return "None"
	return f"{len(toformat[0])} Killstreaks; {len(toformat[1])} Bookmarks"

def frmd_label(parent, text,
	styles = ("Framed.Contained.TFrame", "Labelframe.Contained.TLabel")):
	'''Returns a ttk.Frame object containing a ttk.Label with text specified
	that is supposed to be integrated into a Labelframe.
	styles defaults to a tuple of ("Framed.Contained.TFrame",
	"Labelframe.Contained.TLabel").
	'''
	frm = Frame(parent, style = styles[0], padding = 1)
	lbl = Label(frm, text = text, style = styles[1], padding = (3, 0))
	lbl.pack()
	return frm

def tk_secure_str(in_str, repl = None):
	'''If any character in in_str is out of tkinter's char displaying range
	(0x0000 - 0xFFFF), it will be replaced with the constant REPLACEMENT_CHAR.
	This can be overridden by passing repl as an additional parameter.
	'''
	if repl is None:
		repl = CNST.REPLACEMENT_CHAR
	in_str = [i for i in in_str]
	for i, j in enumerate(in_str):
		if ord(j) > 0xFFFF:
			in_str[i] = repl
	return "".join(in_str)

class HeaderFetcher: #used in _thread_filter.py
	'''Only read a header when the class is accessed.'''
	def __init__(self, filepath):
		self.filepath = filepath
		self.header = None

	def __getitem__(self, key):
		if self.header == None:
			try:
				self.header = readdemoheader(self.filepath)
			except Exception:
				self.header = CNST.FALLBACK_HEADER
		return self.header[key]

class FileStatFetcher: #used in _thread_filter.py
	'''Only read a file's size and moddate when the class is accessed.'''
	def __init__(self, filepath):
		self.filepath = filepath
		self.data = None

	def __getitem__(self, key):
		if self.data == None:
			statres = os.stat(self.filepath)
			self.data = {"filesize":statres.st_size, "modtime":statres.st_mtime}
		return self.data[key]
