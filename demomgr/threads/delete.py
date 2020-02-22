import os
import time
import queue
import shutil
import re

from demomgr.constants import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import handle_events as handle_ev
from demomgr import constants as CNST

class ThreadDelete(_StoppableBaseThread):
	'''
	Thread takes no queue_inp, but the following kwargs:
		demodir <Str>: Absolute directory to delete demos in.
		files <List[Str]>: List of all files in demodir.
		selected <List[Bool]>: List of bools of same length as files.
		filestodel <List[Str]>: Simple file names of the files to be removed;
			[j for i, j in enumerate(files) if selected[i]];
		cfg <Dict>: Program configuration as in .demomgr/config.cfg
		eventfileupdate <Str; "passive"|"selectivemove">: eventfile update mode.
	'''
	def __init__(self, queue_inp, queue_out, demodir, files, selected, filestodel, cfg,
			eventfileupdate = "passive", *args, **kwargs):
		self.options = {"demodir": demodir, "files": files, "selected": selected,
			"filestodel": filestodel, "cfg": cfg, "eventfileupdate": eventfileupdate}

		super().__init__(queue_inp, queue_out, *args, **kwargs)

	def run(self):
		evtpath = os.path.join(self.options["demodir"], CNST.EVENT_FILE)
		tmpevtpath = os.path.join(self.options["demodir"], "." + CNST.EVENT_FILE)
		errorsencountered = 0
		deletedfiles = 0
		starttime = time.time()
	#-----------Deletion loop-----------#
		for i in self.options["filestodel"]:
			if self.stoprequest.isSet():
				self.queue_out_put(THREADSIG.ABORTED); return
			try:
				os.remove(os.path.join(self.options["demodir"], i))
				deletedfiles += 1
				self.queue_out_put(THREADSIG.INFO_CONSOLE, "\nDeleted {} .".format(i))
			except Exception as error:
				errorsencountered += 1
				self.queue_out_put(THREADSIG.INFO_CONSOLE, "\nError deleting \"{}\": {} .".format(i, str(error)))
	#-----------------------------------#
		self.queue_out_put(THREADSIG.INFO_CONSOLE, "\n\nUpdating " + CNST.EVENT_FILE + "...") #---Update eventfile
		if not os.path.exists(evtpath):
			self.queue_out_put(THREADSIG.INFO_CONSOLE, " Event file not found, skipping.")
		else:
			readeropen = False
			writeropen = False
			try:
				reader = handle_ev.EventReader(evtpath, blocksz = self.options["cfg"]["evtblocksz"])
				readeropen = True
				writer = handle_ev.EventWriter(tmpevtpath, clearfile = True)
				writeropen = True
			except (OSError, PermissionError) as error:
				self.queue_out_put(
					THREADSIG.INFO_CONSOLE,
					" Error updating eventfile:\n{}\n".format(str(error))
				)
				if readeropen: reader.destroy()
				if writeropen: writer.destroy()
			else:
				if self.options["eventfileupdate"] == "passive":
					for outchunk in reader:
						regres = re.search(CNST.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						if regres:
							curchunkname = regres[0] + ".dem"
						else:
							curchunkname = ""
						#create a new list of okay files or basically waste twice the time going through all the .json files?
						if not curchunkname in self.options["filestodel"]:
							writer.writechunk(outchunk)

				elif self.options["eventfileupdate"] == "selectivemove": # Requires to have entire dir/actual files present in self.files;
					okayfiles = set([j for i, j in enumerate(self.options["files"])
							if not self.options["selected"][i]])
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
			"\nErrors encountered: {}\n==========".format(round(time.time() - starttime, 3),
				deletedfiles, errorsencountered
			)
		)
		self.queue_out_put(THREADSIG.SUCCESS); return
