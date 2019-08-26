import os
import time
import queue
import shutil
import re

from ._base import _StoppableBaseThread
from .. import handle_events as handle_ev
from .. import constants as CNST

class ThreadDelete(_StoppableBaseThread):
	'''Thread takes no queue_inp, but an additional dict with the following keys:
		keepeventsfile <Bool>: Whether to create a backup of _events.txt
		demodir <Str>: Absolute directory to delete demos in.
		files <List[Str]>: List of all files in demodir.
		selected <List[Bool]>: List of bools of same length as files.
		filestodel <List[Str]>: Simple file names of the files to be removed;
			[j for i, j in enumerate(files) if selected[i]];
		cfg <Dict>: Program configuration as in .demomgr/config.cfg
		eventfileupdate <Str; "passive"|"selectivemove">: eventfile update mode.
	'''
	def run(self):
		self.options = self.args[0].copy()
		evtpath = os.path.join(self.options["demodir"], CNST.EVENT_FILE)
		del self.args
		if self.options["keepeventsfile"]: #---Backup _events file
			try:
				if os.path.exists(evtpath): #This will fail when demodir is blocked
					backupfolder = os.path.join(os.getcwd(), CNST.CFG_FOLDER, CNST.EVENT_BACKUP_FOLDER)
					if not os.path.exists(backupfolder):
						os.makedirs(backupfolder)
					i = 0
					while True:
						if os.path.exists(os.path.join(backupfolder, os.path.splitext(CNST.EVENT_FILE)[0] + str(i) + ".txt" )  ): #enumerate files: _events0.txt; _events1.txt; _events2.txt ...
							i += 1
						else:
							break
					self.queue_out.put(("ConsoleInfo", "\nCreating eventfile backup at " + os.path.join(os.getcwd(), CNST.CFG_FOLDER, CNST.EVENT_BACKUP_FOLDER, (os.path.splitext(CNST.EVENT_FILE)[0] + str(i) + ".txt") ) + " .\n"  ) )
					shutil.copy2(os.path.join(self.options["demodir"], CNST.EVENT_FILE), os.path.join(os.getcwd(), CNST.CFG_FOLDER, CNST.EVENT_BACKUP_FOLDER, (os.path.splitext(CNST.EVENT_FILE)[0] + str(i) + ".txt")))
				else:
					self.queue_out.put(("ConsoleInfo", "\nEventfile does not exist; can not create backup.\n"))
			except Exception as error:
				self.queue_out.put(("ConsoleInfo", "\nError while copying eventfile: {}.\n".format(str(error))))
		if self.stoprequest.isSet():
			self.queue_out.put(("Finish", 2))
			return
		errorsencountered = 0 #---Delete files
		deletedfiles = 0
		starttime = time.time()
	#-----------Deletion loop-----------#
		for i in self.options["filestodel"]:
			if self.stoprequest.isSet():
				self.queue_out.put(("Finish", 2)); return
			try:
				os.remove(os.path.join(self.options["demodir"], i))
				deletedfiles += 1
				self.queue_out.put(("ConsoleInfo", "\nDeleted {} .".format(i)))
			except Exception as error:
				errorsencountered += 1
				self.queue_out.put(("ConsoleInfo", "\nError deleting \"{}\": {} .".format(i, str(error))))
	#-----------------------------------#
		self.queue_out.put(("ConsoleInfo", "\n\nUpdating " + CNST.EVENT_FILE + "...")) #---Update eventfile; NOTE: NO CHECK FOR STOPREQUEST IN HERE; WILL ONLY ADD COMPLEXITY DUE TO HAVING TO CLOSE OPEN RESOURCES.
		if os.path.exists(evtpath):
			tmpevtpath = os.path.join(self.options["demodir"], "." + CNST.EVENT_FILE)
			readeropen = False
			writeropen = False
			try:
				reader = handle_ev.EventReader(evtpath, blocksz = self.options["cfg"]["evtblocksz"])
				readeropen = True
				writer = handle_ev.EventWriter(tmpevtpath, clearfile = True)
				writeropen = True

				if self.options["eventfileupdate"] == "passive":
					while True: #NOTE: Could update those to be for loops, but I dont wanna break this
						outchunk = next(reader)
						regres = re.search(CNST.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						if regres: curchunkname = regres[0] + ".dem"
						else: curchunkname = ""
						if not curchunkname in self.options["filestodel"]:#create a new list of okay files or basically waste twice the time going through all the .json files?
							writer.writechunk(outchunk)
						if outchunk.message["last"]: break

				elif self.options["eventfileupdate"] == "selectivemove":#Requires to have entire dir/actual files present in self.files;
					okayfiles = set([j for i, j in enumerate(self.options["files"]) if not self.options["selected"][i]])
					while True:
						chunkexists = False
						outchunk = next(reader)
						regres = re.search(CNST.EVENTFILE_FILENAMEFORMAT, outchunk.content)
						if regres: curchunkname = regres[0] + ".dem"
						else: curchunkname = ""
						if curchunkname in okayfiles:
							okayfiles.remove(curchunkname)
							chunkexists = True
						if chunkexists:
							writer.writechunk(outchunk)
						if outchunk.message["last"]: break
				reader.destroy()
				writer.destroy()

				os.remove(evtpath)
				os.rename(tmpevtpath, evtpath)
				self.queue_out.put( ("ConsoleInfo", " Done!") )
			except (OSError, PermissionError) as error:
				self.queue_out.put( ("ConsoleInfo", "\n<!!!>\nError updating eventfile:\n{}\n<!!!>".format(str(error))) )
				if readeropen: reader.destroy()
				if writeropen: writer.destroy()
		else:
			self.queue_out.put( ("ConsoleInfo", " Event file not found, skipping.") )
		self.queue_out.put(("ConsoleInfo",
			"\n\n==[Done]==\nTime taken: {} seconds\nFiles deleted: {}\nErrors encountered: {}\n==========".format(
			round(time.time() - starttime, 3), deletedfiles, errorsencountered)))
		self.queue_out.put(("Finish", 1))
