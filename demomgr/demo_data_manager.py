
from enum import IntEnum
import json
import os
import re
import tempfile

from demomgr.constants import DATA_GRAB_MODE, EVENT_FILE
from demomgr.demo_info import DemoInfo
from demomgr import handle_events


RE_DEM_NAME = re.compile(
	r'\[\d{4}/\d\d/\d\d \d\d:\d\d\] (?:Killstreak|Bookmark) .* \("([^"]*)" at \d*\)$'
)
RE_TICK = re.compile(
	r'\[\d{4}/\d\d/\d\d \d\d:\d\d\] (?:Killstreak|Bookmark) .* \("[^"]*" at (\d*)\)'
)
RE_LOGLINE_IS_BOOKMARK = re.compile(r"\[\d\d\d\d/\d\d/\d\d \d\d:\d\d\] Bookmark ")


class PROCESSOR_TYPE(IntEnum):
	READER = 0
	WRITER = 1


class DemoInfoProcessor():
	def __init__(self, ddm):
		self.ddm = ddm

	def acquire(self):
		"""
		Processor should acquire resources here.
		Note that this method is used for __enter__, so return `self`
		from it.
		"""
		return self

	def release(self):
		"""
		Processor should release resources here.
		"""

	__enter__ = lambda s: s.acquire()
	__exit__ = lambda s, *_: s.release()


class Reader(DemoInfoProcessor):
	def get_info(self, names):
		raise NotImplementedError("Le abstract class")


class Writer(DemoInfoProcessor):
	def write_info(self, name, info):
		raise NotImplementedError("Le abstract class")


class EventsReader(Reader):
	def __init__(self, ddm):
		super().__init__(ddm)
		self.reader = None

	def get_info(self, names):
		chunk_cache = {}
		pending_names = set(names)
		try:
			for chk in self.reader:
				try:
					info = DemoInfo.from_raw_logchunk(chk)
				except ValueError:
					continue
				chunk_cache[info.demo_name] = info
				pending_names.discard(info.demo_name)
				if not pending_names:
					break
		except OSError as e:
			return [e] * len(names)
		return [chunk_cache.get(name, None) for name in names]

	def acquire(self):
		self.reader = handle_events.EventReader(
			os.path.join(self.ddm.directory, EVENT_FILE),
			blocksz = self.ddm.cfg.events_blocksize,
		)
		return self

	def release(self):
		self.reader.destroy()


class EventsWriter(Writer):
	def __init__(self, ddm):
		super().__init__(ddm)
		self.writer = None

	def _cleanup(self, tempfile_path = None, prc = None, writer = None):
		if tempfile_path is not None:
			try:
				os.unlink(tempfile_path)
			except OSError:
				pass
		if prc is not None:
			try:
				prc.release()
			except OSError:
				pass
		if writer is not None:
			try:
				writer.destroy()
			except OSError:
				pass

	def write_info(self, names, info):
		try:
			_, fname = tempfile.mkstemp(text = True)
		except OSError as e:
			return [e] * len(names)

		# Set up event reader and writer
		# NOTE: ugly hack, getting the reader out of a processor like that
		read_processor = self.ddm._get_reader(DATA_GRAB_MODE.EVENTS)
		try:
			read_processor.acquire()
		except OSError as e:
			self._cleanup(fname)
			return [e] * len(names)
		event_reader = read_processor.reader
		try:
			event_writer = handle_events.EventWriter(fname)
		except OSError as e:
			self._cleanup(prc=read_processor)
			return [e] * len(names)

		pending_modification = {n: i for n, i in zip(names, info)}
		try:
			for chk in event_reader:
				try:
					cur_info = DemoInfo.from_raw_logchunk(chk)
				except ValueError:
					print(f"_events writer: Dropped faulty logchunk:\n===\n{str(chk)}\n===")
					continue
				name = cur_info.demo_name
				if name in pending_modification:
					cur_info = pending_modification.pop(name)
				if not cur_info.is_empty():
					event_writer.writechunk(cur_info.to_logchunk())
				else:
					print(f"_events writer: No logchunk for demo {name!r}")
			for name, cur_info in pending_modification.items():
				if not cur_info.is_empty():
					print(f"_events writer: Appending logchunk for demo {name!r}")
					event_writer.writechunk(cur_info.to_logchunk())
		except OSError as e:
			self._cleanup(fname, read_processor, event_writer)
			return [e] * len(names)

		self._cleanup(prc = read_processor, writer = event_writer)
		print("tempfile stored at", fname)

		return [None] * len(names)

	def acquire(self):
		self.writer = handle_events.EventWriter(os.path.join(self.ddm.directory, EVENT_FILE))
		return self

	def release(self):
		if self.writer is not None:
			self.writer.destroy()


class JSONReader(Reader):
	def _single_get_info(self, name):
		json_name = os.path.splitext(name)[0] + ".json"
		try:
			fh = open(os.path.join(self.ddm.directory, json_name), "r")
		except FileNotFoundError:
			return None
		except OSError as e:
			return e

		try:
			data = json.load(fh)
		except (json.decoder.JSONDecodeError, UnicodeDecodeError) as e:
			return e
		finally:
			fh.close()

		try:
			return DemoInfo.from_json(data, name)
		except (KeyError, ValueError) as e:
			return e

	def get_info(self, names):
		return [self._single_get_info(name) for name in names]


class JSONWriter(Writer):
	def _single_write_info(self, name, info: DemoInfo):
		json_name = os.path.splitext(name)[0] + ".json"
		try:
			new = json.dumps(info.to_json())
		except ValueError as e:
			return e

		json_path = os.path.join(self.ddm.directory, json_name)
		if not info.is_empty():
			print(f"JSON writer: Would write {json_path!r}")
			# try:
			# 	with open(json_path, "w") as f:
			# 		json.dump(new, f)
			# except OSError as e:
			# 	return e
		else:
			print(f"JSON writer: Would delete {json_path!r}")
			# try:
			# 	os.unlink(json_path)
			# except OSError as e:
			# 	return e

		return None

	def write_info(self, names, info):
		return [self._single_write_info(name, info_obj) for name, info_obj in zip(names, info)]


class NoneReader(Reader):
	def get_info(self, names):
		return [None] * len(names)


class NoneWriter(Reader):
	def write_info(self, names, _):
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
		PROCESSOR_TYPE.WRITER: NoneWriter,
	},
}

class DemoDataManager():
	"""
	High-level class overlooking all demo data in a directory,
	being able to read and modify it as safely as possible.

	This thing is not thread-safe.
	"""
	def __init__(self, directory, cfg):
		"""
		Initializes a new DemoDataManager.

		directory: Directory the DDM should operate on. (str)
		cfg: Program configuration (demomgr.config.Config)
		"""
		self.readers = {}
		self.writers = {}
		self.directory = directory
		self.cfg = cfg

	def _get_reader(self, mode):
		"""
		Returns a reader for the specified mode or creates it
		newly if it does not exist.
		"""
		if mode not in self.readers:
			self.readers[mode] = _PROCESSOR_MAP[mode][PROCESSOR_TYPE.READER](self)
		return self.readers[mode]

	def _get_writer(self, mode):
		"""
		Returns a writer for the specified mode or creates it
		newly if it does not exist.
		"""
		if mode not in self.writers:
			self.writers[mode] = _PROCESSOR_MAP[mode][PROCESSOR_TYPE.WRITER](self)
		return self.writers[mode]

	def get_demo_info(self, demos, mode):
		"""
		Retrieves information about demos via the data grab mode
		given in `mode`.

		This returns a list of: A DemoInfo object, None in case no info
		container at all was found, or an exception if one occurred.

		May raise: OSError in case reader initialization fails.
		"""
		with self._get_reader(mode) as r:
			return r.get_info(demos)

	def get_fs_info(self, names):
		"""
		Retrieves file system info for all given demos.

		Returns a list of:
			- Dict with two keys: 'size', 'mtime', containing the
			  demo's size and last modification time.
			- An exception if one occurred while getting file system
			  info.
		for each demo.
		"""

		res = []
		for name in names:
			target = os.path.join(self.directory, name)
			try:
				stat_res = os.stat(target)
				stat_res = {"size": stat_res.st_size, "mtime": stat_res.st_mtime}
			except OSError as e:
				stat_res = e
			res.append(stat_res)
		return res

	def write_demo_info(self, names, demo_info, modes = None):
		"""
		Sets information for the given demos for all supplied modes.
		This will destroy any existing information.
		If empty demo info is given for a demo name, any existing info
		containers will be deleted/omitted so that the next read
		attempt on the name returns `None`.
		If `modes` is `None`, will set the data for all possible modes.
		(That is, first `EVENTS`, then `JSON`).

		Returns a list of lists for each mode that was passed in,
		each inner list describing how writing each demo's info went.
		(`None` on success, an exception on error.)

		May raise: OSError.
		"""
		if len(demo_info) != len(names):
			raise ValueError("Each supplied demo name must have a corresponding DemoInfo.")

		modes = (DATA_GRAB_MODE.EVENTS, DATA_GRAB_MODE.JSON) if modes is None else modes

		results = []
		for mode in modes:
			with self._get_writer(mode) as w:
				results.append(w.write_info(names, demo_info))
		return results

	# def flush(self):
	# 	"""
	# 	Call this to write any data to where it should be.
	# 	`set_info(x, y)` -> `get_info(x)` may not return `y`,
	# 	but `set_info(x, y) -> `flush()` -> `get_info(x)` will.
	# 	This function may raise OSErrors.
	# 	"""
	# 	for mode in DATA_GRAB_MODE:
	# 		if mode in self.readers and mode in self.writers:
	# 			self.readers[mode].release()
	# 			self.writers[mode].flush()
	# 			self.readers[mode].acquire()

	# def destroy(self):
	# 	"""
	# 	Removes all processors of the DemoDataManager.
	# 	"""
	# 	for prc in self.readers.values():
	# 		prc.release()
	# 	for prc in self.writers.values():
	# 		prc.release()
	# 	self.readers = {}
	# 	self.writers = {}

	# def __del__(self):
	# 	self.destroy()

	__enter__ = lambda s: s
	__exit__ = lambda s, *_: s.destroy()
