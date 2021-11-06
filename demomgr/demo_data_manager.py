
from enum import IntEnum
import json
import os
import tempfile

from demomgr.constants import DATA_GRAB_MODE, EVENT_FILE
from demomgr.demo_info import DemoInfo
from demomgr import handle_events


class PROCESSOR_TYPE(IntEnum):
	READER = 0
	WRITER = 1


class DemoInfoProcessor():
	def __init__(self, directory):
		self.directory = directory
		self.acquire()

	def acquire(self):
		"""
		Processor should acquire resources here.
		"""

	def release(self):
		"""
		Processor should release resources here.
		"""


class Reader(DemoInfoProcessor):
	def get_info(self, names):
		raise NotImplementedError("Le abstract class")


class Writer(DemoInfoProcessor):
	def write_info(self, name, info):
		raise NotImplementedError("Le abstract class")


class EventsReader(Reader):
	def get_info(self, names):
		pending_names = set(names)
		if set(pending_names - self.chunk_cache.keys()):
			while pending_names:
				chk, = self.reader.getchunks(1)
				if not chk:
					break
				try:
					info = DemoInfo.from_raw_logchunk(chk)
				except ValueError:
					continue
				self.chunk_cache[info.demo_name] = info
				pending_names.discard(info.demo_name)
		return [self.chunk_cache.get(name, None) for name in names]

	def acquire(self):
		self.reader = handle_events.EventReader(os.path.join(self.directory, EVENT_FILE))
		self.chunk_cache = {}

	def release(self):
		self.reader.close()


class EventsWriter(Writer):
	pass


class JSONReader(Reader):
	def _single_get_info(self, name):
		try:
			json_name = os.path.splitext(name)[0] + ".json"
			fh = open(os.path.join(self.directory, json_name), "r")
		except FileNotFoundError:
			return None
		except (OSError, PermissionError) as e:
			return e

		try:
			data = json.load(fh)
		except (json.decoder.JSONDecodeError, UnicodeDecodeError) as e:
			print(fh, e)
			fh.close()
			return e
		fh.close()

		try:
			return DemoInfo.from_json(data, name)
		except (KeyError, ValueError) as e:
			return e

	def get_info(self, names):
		return [self._single_get_info(name) for name in names]


class JSONWriter(Writer):
	pass


class NoneReader(Reader):
	def get_info(self, names):
		return [None] * len(names)


_PROCESSOR_MAP = {
	DATA_GRAB_MODE.EVENTS: {
		PROCESSOR_TYPE.READER: EventsReader,
		PROCESSOR_TYPE.WRITER: EventsWriter,
	},
	DATA_GRAB_MODE.JSON: {
		PROCESSOR_TYPE.READER: JSONReader,
		PROCESSOR_TYPE.WRITER: JSONWriter,
	},
	DATA_GRAB_MODE.NONE: {
		PROCESSOR_TYPE.READER: NoneReader,
	},
}

class DemoDataManager():
	"""
	High-level class overlooking all demo data in a directory,
	being able to read and modify it as safely as possible.
	"""
	def __init__(self, directory):
		self.readers = {}
		self.writers = {}
		self.directory = directory

	def _get_reader(self, mode):
		"""
		Returns a reader for the specified mode or creates it
		newly if it does not exist.
		"""
		if mode not in self.readers:
			self.readers[mode] = _PROCESSOR_MAP[mode][PROCESSOR_TYPE.READER](self.directory)
		return self.readers[mode]

	def _get_writer(self, mode):
		raise NotImplementedError("asdf")

	def get_demo_info(self, demos, mode):
		"""
		Retrieves information about demos via the data grab mode
		given in `mode`.

		This returns a list of: A DemoInfo object, None in case no info
		container at all was found, or an exception if one occurred.
		This may raise an OSError when reader initialization fails.
		"""
		return self._get_reader(mode).get_info(demos)

	def get_fs_info(self, name):
		"""
		Retrieves file system info for all given demos.
		"""


	def set_info(self, name, demo_info, modes = None):
		"""
		Sets information for the given demo for all supplied modes.
		This will destroy any existing information.
		If `modes` is `None`, will set the data for all possible modes.
		"""

	def append_info(self, name, demo_info):
		pass

	def flush(self):
		"""
		Call this to write any data to where it should be.
		`set_info(x, y)` -> `get_info(x)` may not return `y`,
		but `set_info(x, y) -> `flush()` -> `get_info(x)` will.
		This function may raise OSErrors.
		"""
		for mode in DATA_GRAB_MODE:
			if mode in self.readers and mode in self.writers:
				self.readers[mode].release()
				self.writers[mode].flush()
				self.readers[mode].acquire()

	def destroy(self):
		for prc in self.readers.values():
			prc.release()
		for prc in self.writers.values():
			prc.release()
		self.readers = {}
		self.writers = {}

	def __del__(self):
		self.destroy()

	__enter__ = lambda s: s
	__exit__ = lambda s, *_: s.destroy()
