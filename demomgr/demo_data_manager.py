
from enum import IntEnum
import json
import os
import shutil
import tempfile

from demomgr.constants import DATA_GRAB_MODE, EVENT_FILE
from demomgr.demo_info import DemoInfo
import demomgr.handle_events as he


class PROCESSOR_TYPE(IntEnum):
	READER = 0
	WRITER = 1


class DemoInfoProcessor():
	def __init__(self, ddm):
		self.ddm = ddm
		self.is_acquired = False

	def acquire(self):
		"""
		Processor should acquire resources here.
		This method may raise `OSError`s, in which case it is
		considered faulty and will be removed from DDMs.
		"""
		if self.is_acquired:
			raise RuntimeError("Acquired processor was acquired again!")
		self.is_acquired = True

	def release(self):
		"""
		Processor should release resources here.
		This method is expected to never raise errors and instead
		(in case of a writer) report exceptions by writing them into
		`self._write_results` or ignoring them otherwise.
		"""
		if not self.is_acquired:
			raise RuntimeError("Non-acquired processor was released!")
		self.is_acquired = False


class Reader(DemoInfoProcessor):
	def get_info(self, names):
		raise NotImplementedError("Le abstract class")


class Writer(DemoInfoProcessor):
	def __init__(self, ddm):
		super().__init__(ddm)
		self._write_results = {}

	def write_info(self, name, info):
		raise NotImplementedError("Le abstract class")

	def get_write_results(self):
		r = self._write_results
		self._write_results = {}
		return r


class EventsReader(Reader):
	def __init__(self, ddm):
		super().__init__(ddm)
		self.reader = None

	def get_info(self, names):
		if self.reader is None:
			return [None] * len(names)

		pending_names = set(names)
		try:
			for chk in self.reader:
				try:
					info = DemoInfo.from_raw_logchunk(chk)
				except ValueError:
					continue
				self.chunk_cache[info.demo_name] = info
				pending_names.discard(info.demo_name)
				if not pending_names:
					break
		except (OSError, UnicodeDecodeError) as e:
			return [e] * len(names)
		return [self.chunk_cache.get(name, None) for name in names]

	def acquire(self):
		super().acquire()
		events_file = os.path.join(self.ddm.directory, EVENT_FILE)
		if not os.path.exists(events_file):
			self.reader = None
		else:
			self.reader = he.EventReader(events_file, blocksz = self.ddm.cfg.events_blocksize)
		self.chunk_cache = {}

	def release(self):
		super().release()
		if self.reader is None:
			return
		try:
			self.reader.destroy()
		except OSError:
			pass
		finally:
			self.reader = None


class EventsWriter(Writer):
	def __init__(self, ddm):
		super().__init__(ddm)

	def _exhaust_reader(self, target_names):
		if not target_names:
			return

		if self.reader is None: # No _events.txt exists.
			return

		for chk in self.reader:
			try:
				cur_info = DemoInfo.from_raw_logchunk(chk)
			except ValueError:
				continue
			name = cur_info.demo_name
			self._name_to_chunk_idx_map[name] = len(self._demo_info)
			self._demo_info.append(cur_info)
			if name in target_names:
				target_names.remove(name)
				if not target_names:
					return

	def write_info(self, names, info):
		self._write_on_release = True
		self._expected_write_result_names.update(names)
		try:
			self._exhaust_reader(set(names))
		except (OSError, UnicodeDecodeError) as e:
			# Disgusting case where reader failed, possibly in the middle of being
			# exhausted. Not continuing since a risk of losing event info that is
			# not being modified exists.
			self._reader_error = e

		for name, info in zip(names, info):
			if name in self._name_to_chunk_idx_map:
				self._demo_info[self._name_to_chunk_idx_map[name]] = info
			else:
				self._name_to_chunk_idx_map[name] = len(self._demo_info)
				self._demo_info.append(info)

	def acquire(self):
		super().acquire()
		events_file = os.path.join(self.ddm.directory, EVENT_FILE)
		if not os.path.exists(events_file):
			self.reader = None
		else:
			self.reader = he.EventReader(events_file, blocksz = self.ddm.cfg.events_blocksize)
		self._write_on_release = False
		self._reader_error = None
		self._demo_info = []
		self._name_to_chunk_idx_map = {}
		self._expected_write_result_names = set()

	def release(self):
		super().release()
		fname = writer = write_result = None

		try:
			if self._reader_error is not None or not self._write_on_release:
				# If this is True, the reader failed and integrity of `self._demo_info`
				# can't be guaranteed. Don't write anything, system probably has bigger
				# problems at this point.
				write_result = self._reader_error
				return

			fhandle_int, fname = tempfile.mkstemp(text = True)
			writer = he.EventWriter(fhandle_int)

			for info in self._demo_info:
				if info is not None and not info.is_empty():
					writer.writechunk(info.to_logchunk())
			# Writes any pending logchunks from a non-fully-exhausted reader.
			# This is so stupidly overengineered lmao
			if self.reader is not None:
				for chk in self.reader:
					try:
						info = DemoInfo.from_raw_logchunk(chk)
					except ValueError:
						continue
					writer.writechunk(info.to_logchunk())
				self.reader.destroy()
				self.reader = None

			writer.destroy()
			writer = None

			shutil.copyfile(fname, os.path.join(self.ddm.directory, EVENT_FILE))
		except (OSError, UnicodeDecodeError, UnicodeEncodeError) as e:
			write_result = e
		finally:
			for name in self._expected_write_result_names:
				self._write_results[name] = write_result

			if self.reader is not None:
				try:
					self.reader.destroy()
				except OSError as e:
					pass
				finally:
					self.reader = None

			if writer is not None:
				try:
					writer.destroy()
				except OSError as e:
					pass

			if fname is not None:
				try:
					os.unlink(fname)
				except OSError:
					pass


class JSONReader(Reader):
	def _single_get_info(self, name):
		json_name = os.path.splitext(name)[0] + ".json"
		try:
			fh = open(os.path.join(self.ddm.directory, json_name), "r", encoding = "utf-8")
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
		except (KeyError, ValueError, TypeError) as e:
			return e

	def get_info(self, names):
		return [self._single_get_info(name) for name in names]


class JSONWriter(Writer):
	def _single_write_info(self, name, info):
		json_path = os.path.join(self.ddm.directory, os.path.splitext(name)[0] + ".json")
		if info is not None and not info.is_empty():
			try:
				new = json.dumps(info.to_json(), indent = "\t", ensure_ascii = False)
			except ValueError as e:
				return e
			try:
				with open(json_path, "w", encoding = "utf-8") as f:
					f.write(new)
			except (OSError, UnicodeEncodeError) as e:
				return e
		else:
			try:
				if os.path.exists(json_path):
					os.unlink(json_path)
			except OSError as e:
				return e

		return None

	def write_info(self, names, info):
		for name, info_obj in zip(names, info):
			self._write_results[name] = self._single_write_info(name, info_obj)


class NoneReader(Reader):
	def get_info(self, names):
		return [None] * len(names)


class NoneWriter(Writer):
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
	"""

	def __init__(self, directory, cfg):
		"""
		Creates a new DemoDataManager.

		directory: Directory the DDM should operate on. (str)
		cfg: Program configuration (demomgr.config.Config)
		"""
		self.readers = {}
		self.writers = {}
		self.directory = directory
		self.cfg = cfg
		self._write_results = {}

	def _get_reader(self, mode):
		"""
		Returns a reader for the specified mode or creates it
		newly if it does not exist.
		"""
		if mode not in self.readers:
			r = _PROCESSOR_MAP[mode][PROCESSOR_TYPE.READER](self)
			r.acquire()
			self.readers[mode] = r
		return self.readers[mode]

	def _get_writer(self, mode):
		"""
		Returns a writer for the specified mode or creates it
		newly if it does not exist.
		"""
		if mode not in self.writers:
			w = _PROCESSOR_MAP[mode][PROCESSOR_TYPE.WRITER](self)
			w.acquire()
			self.writers[mode] = w
		return self.writers[mode]

	def _merge_write_results(self, mode, results):
		if mode not in self._write_results:
			self._write_results[mode] = {}
		for name, result in results.items():
			self._write_results[mode][name] = result

	def _fetch_write_results(self, mode):
		if mode not in self.writers:
			return
		self._merge_write_results(mode, self.writers[mode].get_write_results())

	def get_write_results(self):
		"""
		Retrieves information on how writing of DemoInfo went.
		This method only returns a non-empty result after `flush` is
		called, where it will return a dict mapping touched data modes
		to other dicts where a demo name (str) maps to either:
			- An exception
			- None if all went well
		This method should be called before an operation is affecting
		the same demo/mode pair twice, in order to get a fully overview
		of all write processes.
		"""
		r = self._write_results
		self._write_results = {}
		return r

	def get_demo_info(self, demos, mode):
		"""
		Retrieves information about demos via the data grab mode
		given in `mode`.

		This returns a list of (For each string passed in via `demos`):
		A DemoInfo object, `None` in case no info container at all was
		found, or an exception if one occurred.
		"""
		try:
			r = self._get_reader(mode)
		except OSError as e:
			return [e] * len(demos)
		return r.get_info(demos)

	def get_fs_info(self, names):
		"""
		Retrieves file system info for all given demos.

		Returns a list of either:
			- Dict with two keys: 'size', 'mtime', containing the
			  demo's size and last modification time.
			- An exception if one occurred while getting file system
			  info.
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

	def write_demo_info(self, names, demo_info, mode):
		"""
		Sets information for the given demos for the supplied mode.
		This will destroy any existing information.
		If empty demo info is given for a demo name, any existing info
		containers will be deleted/omitted so that the next read
		attempt on the name returns `None`.
		Returns whether an error occurred. If it did, it can be
		retrieved immediatedly via `get_write_results`.

		May raise:
			- ValueError in case `names` and `demo_info` differ in
			  length.
		"""
		if len(demo_info) != len(names):
			raise ValueError("Each supplied demo name must have a corresponding DemoInfo.")

		try:
			w = self._get_writer(mode)
		except OSError as e:
			self._merge_write_results(mode, {name: e for name in names})
			return True

		w.write_info(names, demo_info)
		return False

	def flush(self):
		"""
		Call this to write any data to where it should be.
		`write_demo_info(x, y)` -> `get_demo_info(x)` may not return
		`y`, but `write_demo_info(x, y) -> `flush()` ->
		`get_demo_info(x)` will.

		This function may return (not raise) an OSError, in which case
		the data written may be all over the place and ruined.
		The return value of `get_write_results` will be updated
		nonetheless.
		If this happens, the DDM should not be used anymore.
		Shouldn't happen on a sane system.
		"""
		exc = None
		for mode in DATA_GRAB_MODE:
			if mode not in self.writers: # No need to release reader
				continue

			if mode in self.readers:
				self.readers[mode].release()
			self.writers[mode].release()
			self._fetch_write_results(mode)

		_acquired_processors = []
		for mode in DATA_GRAB_MODE:
			if mode not in self.writers:
				continue

			try:
				self.writers[mode].acquire()
				_acquired_processors.append(self.writers[mode])
				if mode in self.readers:
					self.readers[mode].acquire()
					_acquired_processors.append(self.readers[mode])
			except OSError as e:
				exc = e
				for prc in _acquired_processors:
					prc.release()
				for writer_mode in self.writers.keys():
					self._fetch_write_results(writer_mode)
				self.readers = {}
				self.writers = {}

		return exc

	def destroy(self):
		"""
		Releases and removes all processors of the DemoDataManager.
		"""
		for prc in self.readers.values():
			prc.release()
		for mode, prc in self.writers.items():
			prc.release()
			self._fetch_write_results(mode)
		self.readers = {}
		self.writers = {}

	def __del__(self):
		self.destroy()
