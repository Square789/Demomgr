'''Classes designed to ease up the handling of a _events.txt file as written
by the source engine.
'''

_DEF = {"sep":">\n"}

read_DEF = {"blocksz":65536, "resethandle":True}
write_DEF = {"clearfile":False, "forceflush":False, "empty_ok":False}

class Logchunk():
	'''Logchunk class, stores the following attributes:
	content: String; Content read directly from the file.
	message: Dict;
		"last": Boolean; True if the logchunk is either empty or the last
		one in the file, else False.
	fromfile: String; Absolute path to file that the chunk was read from.
	'''
	def __init__(self, content, message, fromfile):
		self.content = content
		self.message = message
		self.fromfile = fromfile

	def __bool__(self):
		return bool(self.content)

	def __repr__(self):
		return "<Logchunk from file " + self.fromfile + ">"

	def __str__(self):
		return self.content

class EventReader():
	'''Class designed to read a Source engine demo event log file.

	handle: Must either be a file handle object or a string to a file.
	If a file handle, must be opened in r, w+, a+ so it can be read.
	If a file handle, it will not be closed after destruction of the reader.

	Keyword args:

	sep: String; Seperator for individual logchunks.
	resethandle: Bool; Will reset the file handle's position to 0 upon creation.
	blocksz: Integer; Blocksize to read files in. Default is 65536.
	'''
	def __init__(self, handle, cnf=None, **cnfargs):
		if cnf is None:
			cnf = {}
		self.isownhandle = False
		if isinstance(handle, str):
			self.isownhandle = True
			handle = open(handle, "r")
		self.handle = handle
		self.cnf = _DEF
		self.cnf.update(read_DEF)
		self.cnf.update(cnfargs)
		self.cnf.update(cnf)

		self.filename = self.handle.name

		if self.cnf["resethandle"]:
			self.handle.seek(0)

		self.lastchunk = ""

		self.chunkbuffer = []

	def __enter__(self):
		return self

	def __iter__(self):
		self.reset()
		return self

	def __exit__(self, *_):
		self.destroy()

	def __next__(self):
		chk = self.getchunks(1)[0]
		if chk.content.isspace() or chk.content == "":
			raise StopIteration
		return chk

	def close(self):
		self.destroy()

	def destroy(self):
		self.handle.close()
		del self

	def getchunks(self, toget = 1):
		'''Method that returns the number of specified datachunks in the file.'''
		while len(self.chunkbuffer) <= toget:
			self.__read()
		returnbfr = []
		for _ in range(toget):
			returnbfr.append(self.chunkbuffer.pop(0))
		return returnbfr

	def reset(self):
		'''Resets the EventReader to the start of the file.'''
		self.handle.seek(0)
		self.lastchunk = ""
		self.chunkbuffer = []

	def __read(self):
		'''Internal method reading logchunks and adding them to self.chunkbuffer.'''
		raw = ""
		rawread = ""
		logchunks = []
		done = False
		if done: return
		rawread = self.handle.read(self.cnf["blocksz"])
		if rawread == "": #we can be sure the file is over.
			done = True
		raw = self.lastchunk + rawread
		logchunks = raw.split(self.cnf["sep"])
		if len(logchunks) == 0:
			self.chunkbuffer = self.chunkbuffer + Logchunk("", {"last":True}, self.handle.name)
			return
		elif len(logchunks) == 1:
			if rawread == "":
				self.lastchunk = ""
			else:
				self.lastchunk = logchunks.pop(0)#Big logchunk
		else:
			self.lastchunk = logchunks.pop(-1)
		self.chunkbuffer = self.chunkbuffer + [Logchunk(i[:-1], {"last": not bool(rawread)}, self.handle.name) for i in logchunks]#Cut off \n @ end; NOTE: THIS MAY BE 2 OR 1 CHARS DEPENDING ON SYSTEM

class EventWriter():
	'''Class designed to write to a Source engine demo event log file.

	handle: Must either be a file handle object or a string to a file.
	If a file handle, must be opened in a+ mode.
	If a file handle, it will not be closed after destruction of the writer.

	Keyword args:

	sep: String; Seperator for individual logchunks.
	clearfile: Bool; Will delete the file's contents once as soon as the
		handler is created.
	forceflush: Bool; Will call the flush() method on the file handle after
		every written logchunk.
	empty_ok: Bool; If false, raises a ValueError if an empty chunk is
		written. If true, does not write the chunk, but continues without
		raising an exception.
	'''
	def __init__(self, handle, cnf=None, **cnfargs):
		if cnf is None:
			cnf = {}
		self.cnf = _DEF
		self.cnf.update(write_DEF)
		self.cnf.update(cnfargs)
		self.cnf.update(cnf)
		self.isownhandle = False
		if isinstance(handle, str):
			self.isownhandle = True
			handle = open(handle, "a+")

		self.handle = handle

		self.filename = self.handle.name

		if self.handle.mode != "a+":
			raise ValueError("Handle must be openend in a+ format.")

		if self.cnf["clearfile"]:
			self.handle.seek(0)
			self.handle.truncate(0)

		self.handle.seek(0, 2) #Move to end of file

	def __enter__(self):
		return self

	def __exit__(self, *_):#NOTE: maybe handle exceptions dunno
		self.destroy()

	def writechunk(self, in_chk):
		'''Writes a string or Logchunk to the file following options specified.'''
		if not isinstance(in_chk, (Logchunk, str) ):
			raise ValueError("Expected Logchunk or str, not " + type(in_chk).__name__)
		if not in_chk:
			if self.cnf["empty_ok"]:
				return
			else:
				raise ValueError("Empty logchunks can not be written.")
		#If start of file, don't write >\n, else do.
		#Always write \n when done
		if self.handle.tell() == 0:
			pass
		else:
			self.handle.write(self.cnf["sep"])
		self.handle.write(str(in_chk))
		self.handle.write("\n")
		if self.cnf["forceflush"]:
			self.handle.flush()

	def writechunks(self, in_chks):
		'''Accepts a list of Strings or Logchunks and writes them to file.'''
		for i in in_chks:
			self.writechunk(i)

	def close(self):
		'''Alias for self.destroy()'''
		self.destroy()

	def destroy(self):
		'''Closes handle if it was created inside of the EventWriter.'''
		if self.isownhandle:
			self.handle.close()
		del self
