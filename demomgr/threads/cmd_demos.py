import os
import shutil

from demomgr.constants import BULK_OPERATION, DATA_GRAB_MODE
from demomgr.demo_data_manager import DemoDataManager
from demomgr.threads._base import _StoppableBaseThread
from demomgr.threads._threadsig import THREADSIG


class CMDDemosThread(_StoppableBaseThread):
	"""
	Thread to bulk delete, or copy/move demos between directories
	alongside with their info.

	Sent to the output queue:
		SUCCESS(0) when the thread is not aborted.

		FAILURE(0) never.

		ABORTED(0) on abort.

		FILE_OPERATION_SUCCESS(1) when a file is successfully deleted.
			- Name of the deleted file

		FILE_OPERATION_FAILURE(2) when a file deletion fails.
			- Name of the file
			- The raised error
	"""

	def __init__(
		self,
		queue_out,
		source_dir,
		target_dir,
		mode,
		files_to_process,
		info_to_process,
		cfg
	):
		"""
		Thread takes an output queue and the following kwargs:
			source_dir <Str>: Absolute directory to copy/move/delete
				demos from.
			target_dir <Str|None>: Absolute directory to copy/move demos to.
			mode <BULK_OPERATION>: What to do.
			files_to_process <List[Str]>: Names of the demos to be processed.
			info_to_process <Dict[Str, List[DATA_GRAB_MODE]]> A dict specifying
				partial work units for demo information. Each entry should
				map a demo name to an iterable of data grab modes.
				These will be worked on in addition to all demos
				successfully processed in `files_to_process`.
			cfg <demomgr.config.Config>: Program configuration.

			Note that all demos that are successfully processed in
			`files_to_process` will be added to `info_to_process` internally,
			which will have an effect on the dict passed in for it.
		"""
		self.source_dir = source_dir
		self.target_dir = target_dir
		self.mode = mode
		self.to_process = files_to_process
		self.info_to_process = info_to_process
		self.cfg = cfg

		self.finish_sig = THREADSIG.SUCCESS

		self._FULL_DGM = [x for x in DATA_GRAB_MODE if x is not DATA_GRAB_MODE.NONE]

		super().__init__(None, queue_out)

	def run(self):
		file_processor, info_processor = {
			BULK_OPERATION.COPY: (self.copy, self.copy_info),
			BULK_OPERATION.MOVE: (self.move, self.move_info),
			BULK_OPERATION.DELETE: (self.delete, self.delete_info),
		}[self.mode]

		successfully_processed = file_processor()
		for file in successfully_processed:
			self.info_to_process[file] = self._FULL_DGM

		mode_files_map = {m: [] for m in DATA_GRAB_MODE}
		for file, modes in self.info_to_process.items():
			for mode in modes:
				mode_files_map[mode].append(file)
		info_processor({m: files for m, files in mode_files_map.items() if files})

		self.queue_out_put(self.finish_sig)

	# === Stage 1 functions ===

	# NOTE: _move, _copy and _delete are almost duplicates. Could probably be condensed.
	def move(self):
		successfully_moved = []
		for file in self.to_process:
			try:
				shutil.move(
					os.path.join(self.source_dir, file),
					os.path.join(self.target_dir, file),
				)
			except OSError as e:
				self.queue_out_put(THREADSIG.FILE_OPERATION_FAILURE, file, e)
			else:
				self.queue_out_put(THREADSIG.FILE_OPERATION_SUCCESS, file)
				successfully_moved.append(file)

			if self.stoprequest.is_set():
				self.finish_sig = THREADSIG.ABORTED
				break

		return successfully_moved

	def copy(self):
		successfully_copied = []
		for file in self.to_process:
			try:
				shutil.copy(
					os.path.join(self.source_dir, file),
					os.path.join(self.target_dir, file),
				)
			except OSError as e:
				self.queue_out_put(THREADSIG.FILE_OPERATION_FAILURE, file, e)
			else:
				self.queue_out_put(THREADSIG.FILE_OPERATION_SUCCESS, file)
				successfully_copied.append(file)

			if self.stoprequest.is_set():
				self.finish_sig = THREADSIG.ABORTED
				break

		return successfully_copied

	def delete(self):
		successfully_deleted = []
		for file in self.to_process:
			try:
				os.remove(os.path.join(self.source_dir, file))
			except OSError as e:
				self.queue_out_put(THREADSIG.FILE_OPERATION_FAILURE, file, e)
			else:
				self.queue_out_put(THREADSIG.FILE_OPERATION_SUCCESS, file)
				successfully_deleted.append(file)

			if self.stoprequest.is_set():
				self.finish_sig = THREADSIG.ABORTED
				break

		return successfully_deleted

	# === Stage 2 functions ===

	def _copy_demo_info(self, files, src_ddm, dst_ddm, mode):
		"""
		Copies the demo info of all specified files from the `src_ddm`
		to `dst_ddm`, for the given mode `mode`.
		Note that this may fail, as usual, and will not transfer demo
		info where reading failed.
		"""
		# Filter out any failed reads so you don't end up writing exceptions
		info_to_transfer = []
		data = []
		for file, res in zip(files, src_ddm.get_demo_info(files, mode)):
			if not isinstance(res, Exception):
				info_to_transfer.append(file)
				data.append(res)

		dst_ddm.write_demo_info(info_to_transfer, data, mode)
		dst_ddm.flush()

	def move_info(self, fmm):
		src_ddm = DemoDataManager(self.source_dir, self.cfg)
		dest_ddm = DemoDataManager(self.target_dir, self.cfg)

		for mode, files in fmm.items():
			write_results = {}
			self._copy_demo_info(files, src_ddm, dest_ddm, mode)
			write_results = dest_ddm.get_write_results()[mode]

			# Delete demo info in the source dir, but only the ones that have been
			# transferred successfully
			info_transfer_successful = [
				demo for demo, res in write_results.items() if res is None
			]
			src_ddm.write_demo_info(
				info_transfer_successful, [None] * len(info_transfer_successful), mode
			)
			src_ddm.flush()
			# Consider info move failed when deleting it in the source dir fails.
			# I think this may fail when the OS really screws up and destroys
			# the source data while still raising an OSError?
			# Whatever, not my problem
			for demo, res in src_ddm.get_write_results()[mode].items():
				if res is not None:
					write_results[demo] = res

			self.queue_out_put(
				THREADSIG.RESULT_INFO_WRITE_RESULTS,
				mode,
				write_results,
			)

		src_ddm.destroy()
		dest_ddm.destroy()

	def copy_info(self, fmm):
		src_ddm = DemoDataManager(self.source_dir, self.cfg)
		dest_ddm = DemoDataManager(self.target_dir, self.cfg)

		for mode, files in fmm.items():
			self._copy_demo_info(files, src_ddm, dest_ddm, mode)
			self.queue_out_put(
				THREADSIG.RESULT_INFO_WRITE_RESULTS,
				mode,
				dest_ddm.get_write_results()[mode],
			)

		src_ddm.destroy()
		dest_ddm.destroy()

	def delete_info(self, fmm):
		ddm = DemoDataManager(self.source_dir, self.cfg)

		for mode, files in fmm.items():
			ddm.write_demo_info(files, [None] * len(files), mode)
			ddm.flush()
			self.queue_out_put(
				THREADSIG.RESULT_INFO_WRITE_RESULTS,
				mode,
				ddm.get_write_results()[mode],
			)

		ddm.destroy()
