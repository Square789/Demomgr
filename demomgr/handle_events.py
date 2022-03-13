"""
Classes designed to ease up the handling of a _events.txt file as written
by the source engine.
2022 update: This code is like 2 years old and could use a serious make-over.
"""

_DEF = {"sep": ">\n"}

read_DEF = {"blocksz": 65536, "resethandle": True}
write_DEF = {"clearfile": False, "forceflush": False, "empty_ok": False}

class RawLogchunk():
	"""
	Class to contain a raw logchunk and the following attributes:

	content: Content read directly from the file. (str)
	is_last: Whether the chunk is the last one in the file. (bool)
	fromfile: Absolute path to file that the chunk was read from. (str)
	"""

	__slots__ = ("content", "is_last", "fromfile")

	def __init__(self, content, is_last, fromfile):
		self.content = content
		self.is_last = is_last
		self.fromfile = fromfile

	def __bool__(self):
		return bool(self.content)

	def __repr__(self):
		return f"<Logchunk from file {self.fromfile}>"

	def __str__(self):
		return self.content

class EventReader():
	"""
	Class designed to read a Source engine demo event log file.

	handle: Must either be a file handle object or a string to a file.
		If a file handle, must be opened in r, w+, a+ mode and with
			utf-8 encoding. It will not be closed after destruction
			of the reader.
	sep: Seperator of individual logchunks. (Default '>\\n', str)
	resethandle: Will reset the file handle's position to 0 upon
		creation. (Default True, bool)
	blocksz: Blocksize to read files in. (Default 65536, int)

	May raise:
		OSError when handle creation fails.
		UnicodeError when a given handle is not opened in utf-8.
		UnicodeDecodeError when reading an event file with non-utf-8 data.
	"""
	def __init__(self, handle, sep = None, resethandle = None, blocksz = None):
		self.isownhandle = False

		if isinstance(handle, str):
			self.isownhandle = True
			handle = open(handle, "r", encoding = "utf-8")
		else:
			if handle.encoding.lower() not in ("utf8", "utf-8"):
				raise UnicodeError("Handle must be opened in utf-8 encoding!")

		self.handle = handle
		self.cnf = _DEF.copy()
		self.cnf.update(read_DEF)
		for v, n in ((sep, "sep"), (resethandle, "resethandle"), (blocksz, "blocksz")):
			if v is not None:
				self.cnf[n] = v

		self.filename = self.handle.name

		if self.cnf["resethandle"]:
			self.handle.seek(0)

		self.lastchunk = ""

		self.chunkbuffer = []

	def __enter__(self):
		return self

	def __iter__(self):
		return self

	def __exit__(self, *_):
		self.destroy()

	def __next__(self):
		chk = self.getchunks(1)[0]
		if not chk or chk.content.isspace():
			raise StopIteration
		return chk

	def destroy(self):
		self.handle.close()
		del self

	def getchunks(self, toget = 1):
		"""
		Gets specified amout of chunks from the file.
		Returns a list of RawLogchunks.

		toget: How many RawLogchunks the list should contain.
			(Default 1, int)

		Warning: The amount of returned chunks may be lower than
			the requested amount if the file has ended.
		"""
		while len(self.chunkbuffer) < toget:
			self.__read()
		returnbfr = []
		for _ in range(toget):
			returnbfr.append(self.chunkbuffer.pop(0))
		return returnbfr

	def reset(self):
		"""Resets the EventReader to the start of the file."""
		self.handle.seek(0)
		self.lastchunk = ""
		self.chunkbuffer = []

	def __read(self):
		"""
		Internal method reading logchunks and adding them to
		`self.chunkbuffer`.
		"""
		raw = ""
		rawread = ""
		logchunks = []
		rawread = self.handle.read(self.cnf["blocksz"])
		raw = self.lastchunk + rawread
		logchunks = raw.split(self.cnf["sep"])
		if (self.handle.tell() - 1) <= self.cnf["blocksz"]: # This was the first read
			if logchunks and logchunks[0] == "":
				logchunks.pop(0)
		if len(logchunks) == 0:
			self.chunkbuffer.append(RawLogchunk("", True, self.handle.name))
			return
		# Sometimes, the file starts with >, in which case the first logchunk may be empty.
		elif len(logchunks) == 1:
			if rawread == "":
				self.lastchunk = ""
			else:
				self.lastchunk = logchunks.pop(0) # Big logchunk
		else:
			self.lastchunk = logchunks.pop(-1)
		self.chunkbuffer.extend(
			[RawLogchunk(i[:-1], not bool(rawread), self.handle.name) for i in logchunks]
		)

class EventWriter():
	"""
	Class designed to write to a Source engine demo event log file.

	handle: Must either a file handle object or one of the types accepted
		by `open`.
		If a file handle, must be opened in a+ mode.
		If a file handle, it will not be closed after destruction
		of the writer.
	sep: Seperator of individual logchunks. (str)
	clearfile: Whether to delete the file's contents once as soon as the
		handler is created. (Default False, bool)
	forceflush: Will call the flush() method on the file handle after
		every written logchunk. (Default False, bool)
	empty_ok: If false, raises a ValueError if an empty chunk is
		written. If true, does not write the chunk, but continues without
		raising an exception. (Default False, bool)
	"""
	def __init__(self, handle, sep = None, clearfile = None, forceflush = None, empty_ok = None):
		self.cnf = _DEF.copy()
		self.cnf.update(write_DEF)
		for v, n in (
			(sep, "sep"), (clearfile, "clearfile"),
			(forceflush, "forceflush"), (empty_ok, "empty_ok")
		):
			if v is not None:
				self.cnf[n] = v

		self.isownhandle = False
		if isinstance(handle, (str, bytes, int)):
			self.isownhandle = True
			handle = open(handle, "a+", encoding = "utf-8")
		else:
			if handle.encoding.lower() not in ("utf8", "utf-8"):
				raise UnicodeError("Handle must be opened in utf-8 encoding!")

		self.handle = handle

		self.filename = self.handle.name

		if self.handle.mode != "a+":
			raise ValueError("Handle must be openend in a+ format.")

		if self.cnf["clearfile"]:
			self.handle.seek(0)
			self.handle.truncate(0)

		self.handle.seek(0, 2) # Move to end of file

	def __enter__(self):
		return self

	def __exit__(self, *_): # NOTE: maybe handle exceptions dunno
		self.destroy()

	def writechunk(self, in_chk):
		"""Writes a string or RawLogchunk to the file following options specified."""
		if not isinstance(in_chk, (RawLogchunk, str)):
			raise ValueError(f"Expected RawLogchunk or str, not {type(in_chk).__name__}")
		if not in_chk:
			if self.cnf["empty_ok"]:
				return
			else:
				raise ValueError("Empty logchunks can not be written.")
		# If start of file, don't write >\n, else do.
		# Always write \n when done
		if self.handle.tell() == 0:
			pass
		else:
			self.handle.write(self.cnf["sep"])
		self.handle.write(str(in_chk))
		self.handle.write("\n")
		if self.cnf["forceflush"]:
			self.handle.flush()

	def writechunks(self, in_chks):
		"""Accepts a list of Strings or Logchunks and writes them to file."""
		for i in in_chks:
			self.writechunk(i)

	def destroy(self):
		"""Closes handle if it was created inside of the EventWriter."""
		if self.isownhandle:
			self.handle.close()
		del self
