'''Various helper functions and classes used all over the program.'''

import os
import struct
import re
import datetime
from tkinter.ttk import Frame, Label
from math import log10, floor

import handle_events as handle_ev

import _constants as _DEF

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
	'''Turns unix timestamp into readable format (_DEF.DATE_FORMAT)'''
	return datetime.datetime.fromtimestamp(inp).strftime(_DEF.DATE_FORMAT)

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
	demhdr = _DEF.FALLBACK_HEADER.copy()
	
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

def extractlogarg(logchunk):
	'''Extracts the argument(killstreak number or bookmark name) from a
	logchunk.
	'''
	return re.search(_DEF.EVENTFILE_ARGIDENT, logchunk)[0]

def _convertlogchunks(logchunk):
	'''Converts each _events.txt logchunk to a tuple: (filename,
		[(Streak: killstreakpeaks), (tick), ...],
		[(Bookmark: bookmarkname), (tick), ...])
	'''
	loglines = logchunk.split("\n")
	if loglines:
		filenamesearch = re.search(_DEF.EVENTFILE_FILENAMEFORMAT, loglines[0])
	else:
		return ("", (), ())
	if filenamesearch:
		filename = filenamesearch[0] + ".dem"
	else:
		return ("", (), ())
	#if the code reached this point, file name is present
	killstreaks = []
	bookmarks = []

	for i in loglines:
		if i == "": #Line empty, likely last line.
			continue
		tick = re.search(_DEF.EVENTFILE_TICKLOGSEP, i)[0]
		# Retrieves tick number
		searchres = i.find(_DEF.EVENTFILE_BOOKMARK)
		if searchres != -1: # Line mentions a bookmark
			bmname = extractlogarg(i)
			bookmarks.append((bmname, int(tick)))
			continue
		searchres = i.find(_DEF.EVENTFILE_KILLSTREAK)
		if searchres != -1: # Line mentions a killstreak
			ksnum = int(extractlogarg(i))
			killstreaks.append((ksnum, int(tick)))
			continue
	streakpeaks = getstreakpeaks(killstreaks)
	return (filename, streakpeaks, bookmarks) #there he is

def getstreakpeaks(killstreaks):
	'''Takes a list of tuples where: element 0 is a number and 1 is a time
	tick (which is ignored), then only returns the tuples that make up the
	peak of their sequence.
	For example: (1,2,3,4,5,6,1,2,1,2,3,4) -> (6,2,4) [Only element 0 of
	the tuples displayed].
	This function does not perform any sorting, input is expected to already
	be in a correct order.'''
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

def readevents(handle, blocksz):
	'''This function reads an events.txt file as it's written by the source
	engine, returns (filename, ( (killstreakpeak, tick)... ),
		( (bookmarkname, tick)... ) ).
	May raise exceptions.
	'''
	reader = handle_ev.EventReader(handle, blocksz=blocksz)
	out = []
	for chk in reader:
		out.append(_convertlogchunks(chk.content))
	reader.destroy()
	return out

def assignbookmarkdata(files, bookmarkdata):
	'''Takes a list of files and the bookmarkdata; returns a list that
	contains the parallel bookmarkdata; ("", [], []) if no match found.
	'''
	assignedlogs = [("", [], []) for i in range(len(files))]
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

def frmd_label(parent, text,
	styles = ("Framed.Contained.TFrame", "Labelframe.Contained.TLabel")):
	'''Returns a ttk.Frame object containing a ttk.Label with text specified
	that is supposed to be integrated into a Labelframe.
	styles defaults to a tuple of ("Framed.Contained.TFrame",
	"Labelframe.Contained.TLabel").
	'''
	outerfrm = Frame(parent)
	frm = Frame(parent, style = styles[0], padding = 1)
	lbl = Label(frm, text = text, style = styles[1], padding = (3, 0))
	lbl.pack()
	return frm

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
				self.header = _DEF.FALLBACK_HEADER
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
