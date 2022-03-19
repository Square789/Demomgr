"""Contains the ThreadReadFolder class."""

import os
import time

from demomgr.demo_data_manager import DemoDataManager
from demomgr.demo_info import DemoInfo
from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import constants as CNST

class ThreadReadFolder(_StoppableBaseThread):
	"""
	Thread to read a directory containing demos and return a dict of names,
	creation dates, demo information and filesizes.

	Sent to the output queue:
		RESULT_DEMODATA(1) for a set of demo data, the thread's main
				reason for existence.
			- Demo data as a dict that requires little work to be fed
				into the main window's MultiframeList. May be `None` on
				failure.

		INFO_STATUSBAR(2) for displaying info on a statusbar
				# TODO: REMOVE (issue #31)
			- Message to be displayed.
			- Timeout to remove the message after (May be `None`)
				to specify permanent duration.
	"""

	def __init__(self, queue_out, targetdir, cfg):
		"""
		Thread requires an output queue and the following args:
			targetdir <Str>: Full path to the directory to be read out
			cfg <Dict>: Program configuration
		"""
		self.targetdir = targetdir
		self.cfg = cfg

		super().__init__(None, queue_out)

	def __stop(self, status_msg, status_timeout, result, exitcode):
		"""
		Outputs end signals to self.queue_out.
		If the first arg is None, the Statusbar tuple will not be output.
		"""
		if status_msg is not None:
			self.queue_out_put(THREADSIG.INFO_STATUSBAR, status_msg, status_timeout)

		self.queue_out_put(THREADSIG.RESULT_DEMODATA, result)
		self.queue_out_put(exitcode)

	def run(self):
		"""
		Get data from all the demos in current folder;
		return it in a format that can be directly fed into listbox.
		"""
		if self.targetdir is None:
			self.__stop(None, None, None, THREADSIG.FAILURE)
			return

		self.queue_out_put(
			THREADSIG.INFO_STATUSBAR,
			f"Reading demo information from {self.targetdir} ...",
			None,
		)
		starttime = time.time()

		try:
			files = [
				i for i in os.listdir(self.targetdir)
				if os.path.splitext(i)[1] == ".dem" and
					os.path.isfile(os.path.join(self.targetdir, i))
			]
		except FileNotFoundError:
			self.__stop(
				f"ERROR: Current directory {self.targetdir!r} does not exist.",
				None,
				None,
				THREADSIG.FAILURE,
			)
			return
		except OSError as exc:
			self.__stop(f"Error reading directory: {exc}.", None, None, THREADSIG.FAILURE)
			return

		# Grab demo information
		datamode = self.cfg.data_grab_mode
		ddm = DemoDataManager(self.targetdir, self.cfg)

		# Get FS info and punch it into returnable shape, disposes of exceptions
		sizes = [None] * len(files)
		dates_created = [None] * len(files)
		for i, x in enumerate(ddm.get_fs_info(files)):
			if isinstance(x, dict):
				sizes[i] = x["size"]
				dates_created[i] = x["mtime"]

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			return

		# Get demo info.
		demo_info = [None] * len(files)
		encountered_exception = None
		same_exception = True
		info_read_success_count = 0
		for i, result in enumerate(ddm.get_demo_info(files, datamode)):
			if isinstance(result, Exception):
				if encountered_exception is None:
					encountered_exception = result
				else:
					if same_exception and result != encountered_exception:
						same_exception = False
				continue
			info_read_success_count += 1
			demo_info[i] = result

		ddm.destroy()

		if datamode is CNST.DATA_GRAB_MODE.NONE:
			res_msg = "Demo information disabled."
		else:
			res_msg = (
				f"Processed data from {info_read_success_count}/{len(files)} files in "
				f"{round(time.time() - starttime, 4)} seconds"
			)
			if encountered_exception is not None and same_exception:
				res_msg += f": {encountered_exception}."
			else:
				res_msg += "."

		self.__stop(
			res_msg,
			5000,
			{
				"col_filename": files, "col_demo_info": demo_info,
				"col_ctime": dates_created, "col_filesize": sizes
			},
			THREADSIG.SUCCESS,
		)
		return
