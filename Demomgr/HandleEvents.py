'''Classes designed to ease up the handling of a _events.txt file as written by the source engine'''
'''UNDER DEVELOPMENT, THESE DO NOT WORK AND ARE AS OF NOW UNUSED.'''

import re

_DEF = {	"sep":">\n", "resethandle":True}

read_DEF = {"blocksz":65536}

class EventDecodeError(BaseException):
	pass

class EventReader():
	def __init__(self, handle, cnf = {}, **cnfargs):

		self.handle = handle
		self.cnf = _DEF
		self.cnf.update(read_DEF)
		self.cnf.update(cnfargs)
		self.cnf.update(cnf)

		if self.cnf["resethandle"]:
			self.handle.seek(0)

		self.lastchunk = ""
		self.logchunks = []
		self.raw = ""
		self.rawread = ""
		self.failed = False

	def __enter__(self):
		return self

	def __exit__(self):
		self.destroy()

	def read(self, desiredlen = 1):
		done = False
		while not done:
			print("itel")
			self.rawread = self.handle.read(self.cnf["blocksz"])
			self.raw = self.lastchunk + self.rawread
			self.logchunks = self.raw.split(_DEF["sep"])
			self.lastchunk = self.logchunks.pop(-1)
			if len(self.lastchunk) == self.cnf["blocksz"]:
				continue#This WILL take up more space than blocksz but who cares, it's not like you have 100MB of bookmarks in one demo or so
			if (self.rawread == ""):#EOF
				done = True
			if (len(self.raw) < self.cnf["blocksz"]):#EOF
				done = True
			if len(self.logchunks) >=desiredlen:#Enough has been gathered
				done = True
		if (self.rawread == "") or (len(self.raw) < self.cnf["blocksz"]):#End of file was reached
			self.logchunks.append(self.lastchunk)
		return self.logchunks[0:desiredlen]

	def close(self):
		self.destroy()

	def destroy(self):
		self.handle.close()
		del self