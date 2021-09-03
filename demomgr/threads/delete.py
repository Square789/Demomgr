import os
import re

from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr.handle_events import EventReader, EventWriter
from demomgr import constants as CNST

class ThreadDelete(_StoppableBaseThread):
	"""
	Thread to delete demos from a directory selectively.

	Sent to the output queue:
		DELETION_SUCCESS(1) when a file is successfully deleted.
			- Name of the deleted file

		DELETION_FAILURE(2) when a file deletion fails.
			- Name of the file
			- The raised error

		EVENT_FILE_UPDATE_START(0) when the event file update begins.

		EVENT_FILE_UPDATE_ERROR(1) when the event file update failed.
			- The OSError raised from the failure.

		EVENT_FILE_UPDATE_MISSING(0) when the event file is missing.
				(Note that EVENT_FILE_UPDATE_START is sent nonetheless
				but EVENT_FILE_UPDATE_ERROR is not.)

		EVENT_FILEUPDATE_SUCCESS(0) when the event file update
			succeeded.
	"""

	def __init__(self, queue_out, demodir, files, to_delete, cfg):
		"""
		Thread takes an output queue and the following kwargs:
			demodir <Str>: Absolute directory to delete demos in.
			files <List[Str]>: List of all files in demodir. `_events.txt`
				logchunks of files not in here will be removed.
			to_delete <List[Str]>: Simple file names of the files to be removed.
				There will be one `DELETION_*` signal sent for each file in the
				order of the given list.
			cfg <demomgr.config.Config>: Program configuration.
		"""
		self.demodir = demodir
		self.files = files
		self.to_delete = to_delete
		self.cfg = cfg

		super().__init__(None, queue_out)

	def run(self):
		evtpath = os.path.join(self.demodir, CNST.EVENT_FILE)
		tmpevtpath = os.path.join(self.demodir, "." + CNST.EVENT_FILE)
		deleted = {x: False for x in self.to_delete}

		# --- Delete
		for file in self.to_delete:
			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return
			try:
				# os.remove(os.path.join(self.demodir, file))
				print(f": deleting {os.path.join(self.demodir, file)}")
				deleted[file] = True
				self.queue_out_put(THREADSIG.DELETION_SUCCESS, file)
			except OSError as error:
				self.queue_out_put(THREADSIG.DELETION_FAILURE, file, error)

		# --- Update _events.txt
		okayfiles = set(
			file for file in self.files
			if file not in deleted or not deleted[file]
		)
		self.queue_out_put(THREADSIG.EVENT_FILE_UPDATE_START)
		if not os.path.exists(evtpath):
			self.queue_out_put(THREADSIG.EVENT_FILE_UPDATE_MISSING)
		else:
			try:
				with \
					EventReader(evtpath, blocksz = self.cfg.events_blocksize) as reader, \
					EventWriter(tmpevtpath, clearfile = True) as writer \
				:
					for outchunk in reader:
						regres = re.search(CNST.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						chunkname = regres[0] + ".dem" if regres else ""
						if chunkname in okayfiles:
							okayfiles.remove(chunkname)
							writer.writechunk(outchunk)
						else:
							print(f": chunk {chunkname} not in okayfiles, dropping")
			except OSError as error:
				self.queue_out_put(THREADSIG.EVENT_FILE_UPDATE_ERROR, error)
				try:
					os.remove(tmpevtpath)
				except OSError:
					pass
			else:
				try:
					pass
					# os.remove(evtpath)
					# os.rename(tmpevtpath, evtpath)
					print(f": removing {evtpath} and {tmpevtpath} -> {evtpath}")
				except OSError as error:
					self.queue_out_put(THREADSIG.EVENT_FILE_UPDATE_ERROR, error)
				else:
					self.queue_out_put(THREADSIG.EVENT_FILE_UPDATE_SUCCESS)

		self.queue_out_put(THREADSIG.SUCCESS)
