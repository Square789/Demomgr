"""Contains the ThreadMarkDemo class."""

import os

from demomgr.demo_data_manager import DemoDataManager
from demomgr.demo_info import DemoInfo
from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import constants as CNST


class ThreadMarkDemo(_StoppableBaseThread):
	"""
	Thread for modifying the bookmarks of a demo.

	Sent to the output queue:
		BOOKMARK_CONTAINER_UPDATE_START(1) at the start of a bookmark
				container update process.
			- Container type as the proper enum member.

		BOOKMARK_CONTAINER_UPDATE_SUCCESS(2) when a bookmark container
				is updated.
			- Container type as the proper enum member.
			- Boolean indicating whether the container now exists or not.

		BOOKMARK_CONTAINER_UPDATE_FAILURE(2) when a bookmark container
				update fails. Its existence state should be
				unchanged.
			- Container type as the proper enum member.
			- Error that occurred.
	"""
	def __init__(self, queue_out, bookmarks, targetdemo, cfg):
		"""
		Thread takes an output queue and as the following args:
			bookmarks <Seq[Tuple[Str, Int]]>: Bookmarks as a sequence of
				(name, tick) tuples.
			targetdemo <Str>: Absolute path to the demo to be marked.
			cfg <config.Config>: Program configuration.
		"""
		self.bookmarks = bookmarks
		self.targetdemo = targetdemo
		self.cfg = cfg

		super().__init__(None, queue_out)

	def run(self):
		finish_sig = THREADSIG.SUCCESS
		ddm = DemoDataManager(os.path.dirname(self.targetdemo), self.cfg)
		demo_name = os.path.basename(self.targetdemo)

		for data_mode in CNST.DATA_GRAB_MODE:
			if data_mode is CNST.DATA_GRAB_MODE.NONE:
				continue

			self.queue_out_put(THREADSIG.BOOKMARK_CONTAINER_UPDATE_START, data_mode)
			res, = ddm.get_demo_info([demo_name], data_mode)
			if isinstance(res, Exception): # Fetching failed.
				self.queue_out_put(
					THREADSIG.BOOKMARK_CONTAINER_UPDATE_FAILURE, data_mode, res
				)
				continue # NOTE: this skips the stoprequest check but who cares

			if res is None:
				res = DemoInfo(demo_name, [], self.bookmarks)
			else:
				res.bookmarks = self.bookmarks

			ddm.write_demo_info([demo_name], [res], data_mode)
			ddm.flush()
			wr = ddm.get_write_results()[data_mode][demo_name]
			if isinstance(wr, Exception):
				self.queue_out_put(THREADSIG.BOOKMARK_CONTAINER_UPDATE_FAILURE, data_mode, wr)
			else:
				self.queue_out_put(
					THREADSIG.BOOKMARK_CONTAINER_UPDATE_SUCCESS,
					data_mode,
					not res.is_empty(),
				)

			if self.stoprequest.is_set():
				finish_sig = THREADSIG.ABORTED
				break

		ddm.destroy()
		self.queue_out_put(finish_sig)
