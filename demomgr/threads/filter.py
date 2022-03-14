import os
import time
import queue
from demomgr.demo_info import DemoInfo

from demomgr.filterlogic import process_filterstring, FILTERFLAGS
from demomgr.helpers import readdemoheader
from demomgr.threads.read_folder import ThreadReadFolder
from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread

class ThreadFilter(_StoppableBaseThread):
	"""
	Thread to filter a directory of demos.
	"""

	def __init__(self, queue_out, filterstring, curdir, cfg, silent = False):
		"""
		Thread requires output queue and the following args:
			filterstring <Str>: Raw user input from the entry field
			curdir <Str>: Absolute path to current directory
			cfg <Dict>: Program configuration
			silent <Bool>: If True, thread will not drop progress messages
		"""
		self.filterstring = filterstring
		self.curdir = curdir
		self.cfg = cfg
		self.silent = silent

		super().__init__(None, queue_out)

	def run(self):
		starttime = time.time()

		self.queue_out_put(THREADSIG.INFO_STATUSBAR, ("Filtering demos; Parsing filter...", ))
		try:
			filters, flags = process_filterstring(self.filterstring)
		except Exception as error:
			self.queue_out_put(
				THREADSIG.INFO_STATUSBAR, (f"Error parsing filter request: {error}", 4000)
			)
			self.queue_out_put(THREADSIG.FAILURE)
			return

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		if not self.silent:
			self.queue_out_put(
				THREADSIG.INFO_STATUSBAR, ("Filtering demos; Reading information...", )
			)

		self.datafetcherqueue = queue.Queue()
		self.datafetcherthread = ThreadReadFolder(
			self.datafetcherqueue, targetdir = self.curdir, cfg = self.cfg
		)
		self.datafetcherthread.start()
		# NOTE: Can't really wait for join to this thread here.
		self.datafetcherthread.join(None, nostop = True)
		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		demo_data = None
		while True:
			try:
				queueobj = self.datafetcherqueue.get_nowait()
				if queueobj[0] is THREADSIG.RESULT_DEMODATA:
					demo_data = queueobj[1]
				elif queueobj[0].is_finish_signal():
					if queueobj[0] is THREADSIG.SUCCESS:
						break
					self.queue_out_put(
						THREADSIG.INFO_STATUSBAR,
						("Demo fetching thread failed during filtering.", 4000)
					)
					self.queue_out_put(THREADSIG.FAILURE)
					return
			except queue.Empty:
				break
		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		errors = 0
		filtered_demo_data = {
			"col_filename": [], "col_demo_info": [], "col_ctime": [], "col_filesize": []
		}
		file_amnt = len(demo_data["col_filename"])
		for i, demo_name in enumerate(demo_data["col_filename"]):
			if not self.silent:
				self.queue_out_put(
					THREADSIG.INFO_STATUSBAR, (f"Filtering demos; {i+1} / {file_amnt}", )
				)

			curdataset = {
				"name": demo_name,
				"demo_info": (
					DemoInfo(demo_name, [], []) if demo_data["col_demo_info"][i] is None
					else demo_data["col_demo_info"][i]
				),
				"header": None,
				"filedata": {
					"filesize": demo_data["col_filesize"][i],
					"modtime": demo_data["col_ctime"][i],
				},
			}
			if flags & FILTERFLAGS.HEADER:
				try:
					curdataset["header"] = readdemoheader(os.path.join(self.curdir, demo_name))
				except (OSError, ValueError):
					errors += 1
					continue

			if all(lambda_(curdataset) for lambda_ in filters):
				filtered_demo_data["col_filename" ].append(demo_name)
				filtered_demo_data["col_demo_info"].append(demo_data["col_demo_info"][i])
				filtered_demo_data["col_ctime"    ].append(demo_data["col_ctime"][i])
				filtered_demo_data["col_filesize" ].append(demo_data["col_filesize"][i])

			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return

		res_msg = f"Filtered {file_amnt} demos in {round(time.time() - starttime, 3)} seconds."
		if errors > 0:
			res_msg += f" {errors} of those excluded due to errors."
		self.queue_out_put(THREADSIG.INFO_STATUSBAR, (res_msg, 3000))
		self.queue_out_put(THREADSIG.RESULT_DEMODATA, filtered_demo_data)
		self.queue_out_put(THREADSIG.SUCCESS)
