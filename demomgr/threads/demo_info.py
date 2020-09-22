"""
Thread to read a demo's header and supply other information
"""

import os

from demomgr.helpers import readdemoheader
from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread

class ThreadDemoInfo(_StoppableBaseThread):
	"""
	Thread to deliver filesystem-related information on a demo.
	"""
	def __init__(self, queue_out, target_demo_path):
		"""
		Thread requires output queue and the following args:
			target_demo_path <Str> : Full path to the target demo.
		"""
		self.target_demo_path = target_demo_path

		super().__init__(None, queue_out)

	def run(self):
		stat_res = os.stat(self.target_demo_path)
		self.queue_out_put(THREADSIG.RESULT_FS_INFO, {
			"size": stat_res.st_size,
			"ctime": stat_res.st_ctime,
		})

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		try:
			header = readdemoheader(self.target_demo_path)
		except (OSError, PermissionError, FileNotFoundError):
			header = None
		self.queue_out_put(THREADSIG.RESULT_HEADER, header)

		self.queue_out_put(THREADSIG.SUCCESS)
