import os

from demomgr.demo_data_manager import DemoDataManager
from demomgr.threads._base import _StoppableBaseThread
from demomgr.threads._threadsig import THREADSIG

class ThreadDelete(_StoppableBaseThread):
	"""
	Thread to delete demos from a directory selectively.

	Sent to the output queue:
		DELETION_SUCCESS(1) when a file is successfully deleted.
			- Name of the deleted file

		DELETION_FAILURE(2) when a file deletion fails.
			- Name of the file
			- The raised error
	"""

	def __init__(self, queue_out, demodir, to_delete, cfg):
		"""
		Thread takes an output queue and the following kwargs:
			demodir <Str>: Absolute directory to delete demos in.
			to_delete <List[Str]>: Names of the files to be removed.
			cfg <demomgr.config.Config>: Program configuration.
		"""
		self.demodir = demodir
		self.to_delete = to_delete
		self.cfg = cfg

		super().__init__(None, queue_out)

	def run(self):
		ddm = DemoDataManager(self.demodir, self.cfg)

		for file in self.to_delete:
			ddm.write_demo_info([file], [None])
			try:
				# os.remove(os.path.join(self.demodir, file))
				print("Delete thread would delete", os.path.join(self.demodir, file))
			except OSError as e:
				self.queue_out_put(THREADSIG.DELETION_FAILURE, file, e)
			else:
				self.queue_out_put(THREADSIG.DELETION_SUCCESS, file)

			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return

		ddm.flush()
		# TODO handle ddm write results?

		self.queue_out_put(THREADSIG.SUCCESS)
