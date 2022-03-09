import os
from demomgr.constants import BULK_OPERATION, DATA_GRAB_MODE

from demomgr.demo_data_manager import DemoDataManager
from demomgr.threads._base import _StoppableBaseThread
from demomgr.threads._threadsig import THREADSIG


class CMDDemoInfoThread(_StoppableBaseThread):
	"""
	Thread copy, move or delete demo info between directories.
	This thread can not be aborted because the incomplete file states
	that would come with that are something I am not handling.

	Sent to the output queue:
		SUCCESS(0) always.

		FAILURE(0) never.

		ABORTED(0) never.

		FILE_OPERATION_SUCCESS(1) when a file is successfully deleted.
			- Name of the deleted file

		FILE_OPERATION_FAILURE(2) when a file deletion fails.
			- Name of the file
			- The raised error

		RESULT_INFO_WRITE_RESULTS(1) always.
			- The DemoDataManager's write results, as returned by
			  `get_write_results`.
	"""

	def __init__(self, queue_out, source_dir, target_dir, mode, to_process, cfg):
		"""
		Thread takes an output queue and the following kwargs:
			source_dir <Str>: Absolute directory to copy/move/delete
				demos from.
			target_dir <Str|None>: Absolute directory to copy/move demos to.
			mode <BULK_OPERATION>: Whether to copy, move or delete demo info.
			to_process <Dict[Str, List[DATAGRABMODE]]>: Names of the demos
				whose info is to be processed and the modes processing should
				happen for.
			cfg <demomgr.config.Config>: Program configuration.
		"""
		self.source_dir = source_dir
		self.target_dir = target_dir
		self.mode = mode
		self.cfg = cfg

		mode_files_map = {m: [] for m in DATA_GRAB_MODE}
		for file, modes in to_process:
			for mode in modes:
				mode_files_map[mode] = file
		self.file_modes_map = {m: files for m, files in mode_files_map.items() if files}

		super().__init__(None, queue_out)

	def run(self):
		{
			BULK_OPERATION.COPY: self._run_copy,
			BULK_OPERATION.MOVE: self._run_move,
			BULK_OPERATION.DELETE: self._run_delete,
		}[self.mode]()

		self.queue_out_put(THREADSIG.SUCCESS)

	def _copy_info(self, files, src_ddm, dst_ddm, mode):
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

	def _run_move(self):
		src_ddm = DemoDataManager(self.source_dir, self.cfg)
		dest_ddm = DemoDataManager(self.target_dir, self.cfg)

		dest_wr = {}
		for mode, files in self.file_modes_map.items():
			self._copy_info(files, src_ddm, dest_ddm, mode)

			dest_wr[mode] = dest_ddm.get_write_results()[mode]
			info_transfer_successful = [
				demo for demo, res in dest_wr[mode].items() if res is None
			]
			# Delete demo info in the source dir, but only the ones that have been
			# transferred successfully
			src_ddm.write_demo_info(
				info_transfer_successful, [None] * len(info_transfer_successful), mode
			)
			src_ddm.flush()

		self.queue_out_put(
			THREADSIG.RESULT_INFO_WRITE_RESULTS,
			src_ddm.get_write_results(),
			dest_wr,
		)

	def _run_copy(self):
		src_ddm = DemoDataManager(self.source_dir, self.cfg)
		dest_ddm = DemoDataManager(self.target_dir, self.cfg)

		for mode, files in self.file_modes_map.items():
			self._copy_info(files, src_ddm, dest_ddm, mode)

		self.queue_out_put(
			THREADSIG.RESULT_INFO_WRITE_RESULTS,
			dest_ddm.get_write_results(),
		)

	def _run_delete(self):
		ddm = DemoDataManager(self.source_dir, self.cfg)

		for mode, files in self.file_modes_map.items():
			ddm.write_demo_info(files, [None] * len(files), mode)
		ddm.flush()

		self.queue_out_put(THREADSIG.RESULT_INFO_WRITE_RESULTS, ddm.get_write_results())
