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

	def __init__(self, queue_out, demodir, files, selected, filestodel, evtblocksz,
			eventfileupdate = "passive"):
		"""
		Thread takes output queue and the following kwargs:
			demodir <Str>: Absolute directory to delete demos in.
			files <List[Str]>: List of all files in demodir.
			selected <List[Bool]>: List of bools of same length as files.
			filestodel <List[Str]>: Simple file names of the files to be removed;
				[j for i, j in enumerate(files) if selected[i]];
			evtblocksz <Int>: Amount of bytes to read in _events.txt at once.
			eventfileupdate <Str; "passive"|"selectivemove">: eventfile update mode.
		"""
		self.demodir = demodir
		self.files = files
		self.selected = selected
		self.filestodel = filestodel
		self.evtblocksz = evtblocksz
		self.eventfileupdate = eventfileupdate

		super().__init__(None, queue_out)

	def run(self):
		evtpath = os.path.join(self.demodir, CNST.EVENT_FILE)
		tmpevtpath = os.path.join(self.demodir, "." + CNST.EVENT_FILE)
		errorsencountered = 0
		deletedfiles = 0
		starttime = time.time()
	#-----------Deletion loop-----------#
		for i in self.filestodel:
			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED); return
			try:
				os.remove(os.path.join(self.demodir, i))
				deletedfiles += 1
				self.queue_out_put(THREADSIG.INFO_CONSOLE, f"\nDeleted {i} .")
			except Exception as error:
				errorsencountered += 1
				self.queue_out_put(THREADSIG.INFO_CONSOLE, f"\nError deleting \"{i}\": {error} .")
	#-----------------------------------#
		self.queue_out_put(THREADSIG.INFO_CONSOLE, f"\n\nUpdating {CNST.EVENT_FILE}...") #---Update eventfile
		if not os.path.exists(evtpath):
			self.queue_out_put(THREADSIG.INFO_CONSOLE, " Event file not found, skipping.")
		else:
			reader = None
			writer = None
			try:
				reader = handle_ev.EventReader(evtpath, blocksz = self.evtblocksz)
				writer = handle_ev.EventWriter(tmpevtpath, clearfile = True)
			except (OSError, PermissionError) as error:
				self.queue_out_put(
					THREADSIG.INFO_CONSOLE,
					" Error updating eventfile:\n{}\n".format(str(error)),
				)
				if reader is not None: reader.destroy()
				if writer is not None: writer.destroy()
			else:
				if self.eventfileupdate == "passive":
					for outchunk in reader:
						regres = re.search(CNST.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						if regres:
							curchunkname = regres[0] + ".dem"
						else:
							curchunkname = ""
						#create a new list of okay files or basically waste twice the time going through all the .json files?
						if not curchunkname in self.filestodel:
							writer.writechunk(outchunk)

				elif self.eventfileupdate == "selectivemove": # Requires to have entire dir/actual files present in self.files;
					okayfiles = set([j for i, j in enumerate(self.files)
							if not self.selected[i]])
					for outchunk in reader:
						regres = re.search(CNST.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						if regres:
							curchunkname = regres[0] + ".dem"
						else:
							curchunkname = ""
						if curchunkname in okayfiles:
							okayfiles.remove(curchunkname)
							writer.writechunk(outchunk)
				reader.destroy()
				writer.destroy()

				os.remove(evtpath)
				os.rename(tmpevtpath, evtpath)
				self.queue_out_put(THREADSIG.INFO_CONSOLE, " Done!")

		self.queue_out_put(THREADSIG.INFO_CONSOLE,
			"\n\n==[Done]==\nTime taken: {} seconds\nFiles deleted: {}"
			"\nErrors encountered: {}\n==========".format(
				round(time.time() - starttime, 3), deletedfiles, errorsencountered
			)
		)
		self.queue_out_put(THREADSIG.SUCCESS); return
