import os
import time
import queue
import shutil
import re

from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import handle_events as handle_ev
from demomgr import constants as CNST

class ThreadDelete(_StoppableBaseThread):
	"""
	Thread to delete demos from a directory selectively.
	"""

	def __init__(self, queue_out, demodir, files, to_delete, cfg):
		"""
		Thread takes output queue and the following kwargs:
			demodir <Str>: Absolute directory to delete demos in.
			files <List[Str]>: List of all files in demodir. `_events.txt`
				logchunks of files not in here will be removed.
			to_delete <List[Str]>: Simple file names of the files to be removed
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
		errorsencountered = 0
		deletedfiles = 0
		deleted = {x: False for x in self.to_delete}
		starttime = time.time()

		# --- Delete
		for file in self.to_delete:
			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return
			try:
				# os.remove(os.path.join(self.demodir, file))
				print(f"deleting {os.path.join(self.demodir, file)}")
				deletedfiles += 1
				deleted[file] = True
				self.queue_out_put(THREADSIG.INFO_CONSOLE, f"\nDeleted {file}.")
			except Exception as error:
				errorsencountered += 1
				self.queue_out_put(THREADSIG.INFO_CONSOLE, f"\nError deleting {file}: {error}.")

		# --- Update _events.txt
		self.queue_out_put(THREADSIG.INFO_CONSOLE, f"\n\nUpdating {CNST.EVENT_FILE}...")
		if not os.path.exists(evtpath):
			self.queue_out_put(THREADSIG.INFO_CONSOLE, " Event file not found, skipping.")
		else:
			reader = None
			writer = None
			try:
				reader = handle_ev.EventReader(evtpath, blocksz = self.cfg.events_blocksize)
				writer = handle_ev.EventWriter(tmpevtpath, clearfile = True)
			except (OSError, PermissionError) as error:
				self.queue_out_put(
					THREADSIG.INFO_CONSOLE, f" Error updating event file:\n{error}\n"
				)
				if reader is not None:
					reader.destroy()
				if writer is not None:
					writer.destroy()
			else:
				okayfiles = set(
					file for file in self.files
					if file not in deleted or not deleted[file]
				)
				for outchunk in reader:
					regres = re.search(CNST.EVENTFILE_FILENAMEFORMAT, outchunk.content)
					chunkname = regres[0] + ".dem" if regres else ""
					if chunkname in okayfiles:
						okayfiles.remove(chunkname)
						writer.writechunk(outchunk)
					else:
						print(f"chunk {chunkname} not in okayfiles, dropping")
				reader.destroy()
				writer.destroy()

				# os.remove(evtpath)
				# os.rename(tmpevtpath, evtpath)
				# os.remove(tmpevtpath)
				self.queue_out_put(THREADSIG.INFO_CONSOLE, " Done!")

		self.queue_out_put(
			THREADSIG.INFO_CONSOLE,
			(
				f"\n\n==[Done]==\nTime taken: {round(time.time() - starttime, 3)} "
				f"seconds\nFiles deleted: {deletedfiles}\n"
				f"Errors encountered: {errorsencountered}\n=========="
			)
		)
		self.queue_out_put(THREADSIG.SUCCESS)
