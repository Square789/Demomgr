import os
from demomgr.constants import BULK_OPERATION, DATA_GRAB_MODE

from demomgr.threads._base import _StoppableBaseThread
from demomgr.threads._threadsig import THREADSIG


class CMDDemosThread(_StoppableBaseThread):
	"""
	Thread copy or move demos between directories.

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

	def __init__(self, queue_out, source_dir, target_dir, mode, to_process, cfg):
		"""
		Thread takes an output queue and the following kwargs:
			source_dir <Str>: Absolute directory to copy/move/delete
				demos from.
			target_dir <Str|None>: Absolute directory to copy/move demos to.
			mode <BULK_OPERATION>: What to do.
			to_process <Dict[Str]>: Names of the demos to be processed.
			cfg <demomgr.config.Config>: Program configuration.
		"""
		self.source_dir = source_dir
		self.target_dir = target_dir
		self.mode = mode
		self.to_process = to_process
		self.cfg = cfg

		super().__init__(None, queue_out)

	def run(self):
		{
			BULK_OPERATION.COPY: self._run_copy,
			BULK_OPERATION.MOVE: self._run_move,
			BULK_OPERATION.DELETE: self._run_delete,
		}[self.mode]()

	def _run_move(self):
		successfully_moved = []
		for file in self.to_process:
			try:
				# shutil.move(
				# 	os.path.join(self.source_dir, file),
				# 	os.path.join(self.target_dir, file),
				# )
				print("Demo CMD thread: Would move file at", os.path.join(self.source_dir, file))
			except OSError as e:
				self.queue_out_put(THREADSIG.FILE_OPERATION_FAILURE, file, e)
			else:
				self.queue_out_put(THREADSIG.FILE_OPERATION_SUCCESS, file)
				successfully_moved.append(file)

			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				break

		self.queue_out_put(THREADSIG.SUCCESS)

	def _run_copy(self):
		successfully_copied = []
		for file in self.to_process:
			try:
				# shutil.copy(
				# 	os.path.join(self.source_dir, file),
				# 	os.path.join(self.target_dir, file),
				# )
				print("Demo CMD thread: Would copy file at", os.path.join(self.source_dir, file))
			except OSError as e:
				self.queue_out_put(THREADSIG.FILE_OPERATION_FAILURE, file, e)
			else:
				self.queue_out_put(THREADSIG.FILE_OPERATION_SUCCESS, file)
				successfully_copied.append(file)

			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				break

		self.queue_out_put(THREADSIG.SUCCESS)

	def _run_delete(self):
		successfully_deleted = []
		for file in self.to_process:
			try:
				# os.remove(os.path.join(self.source_dir, file))
				print("Demo CMD thread: Would delete file at", os.path.join(self.source_dir, file))
			except OSError as e:
				self.queue_out_put(THREADSIG.FILE_OPERATION_FAILURE, file, e)
			else:
				self.queue_out_put(THREADSIG.FILE_OPERATION_SUCCESS, file)
				successfully_deleted.append(file)

			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				break

		self.queue_out_put(THREADSIG.SUCCESS)
