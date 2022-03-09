import os

from demomgr.helpers import readdemoheader
from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread


class ReadDemoMetaThread(_StoppableBaseThread):
	"""
	Thread to deliver filesystem-related information on a demo.

	Sent to the output queue:
		RESULT_FS_INFO(1) when file system info on a demo is retrieved.
			- Either a dict containing the keys `"size"` and `"ctime"`
				or `None` if there was an error fetching the data.

		RESULT_HEADER(1) when the demo header is read.
			- Either a dict representing the demo header as returned by
				the helper function `readdemoheader` or `None` if there
				was an error retrieving it.
	"""
	def __init__(self, queue_out, target_demo_path):
		"""
		Thread requires output queue and the following args:
			target_demo_path <Str> : Full path to the target demo.
		"""
		self.target_demo_path = target_demo_path

		super().__init__(None, queue_out)

	def run(self):
		try:
			stat_res = os.stat(self.target_demo_path)
			stat_res = {"size": stat_res.st_size, "ctime": stat_res.st_ctime}
		except OSError:
			stat_res = None
		self.queue_out_put(THREADSIG.RESULT_FS_INFO, stat_res)

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		try:
			header = readdemoheader(self.target_demo_path)
		except (OSError, ValueError):
			header = None
		self.queue_out_put(THREADSIG.RESULT_HEADER, header)

		self.queue_out_put(THREADSIG.SUCCESS)
