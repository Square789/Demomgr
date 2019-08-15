import os
import time
import queue

from ._base import _StoppableBaseThread
from ..helpers import (FileStatFetcher, HeaderFetcher)
from ..filterlogic import filterstr_to_lambdas
from .read_folder import ThreadReadFolder

class ThreadFilter(_StoppableBaseThread):
	'''Thread takes no queue_inp, but queue_out and args[0] as a dict with the following keys:
		filterstring <Str>:Raw user input from the entry field
		curdir <Str>: Absolute path to current directory
		cfg <Dict>: Program configuration as in .demomgr/config.cfg
	'''
	def run(self):
		self.options = self.args[0].copy()
		filterstring = self.options["filterstring"]
		curdir = self.options["curdir"]
		cfg = self.options["cfg"]
		starttime = time.time()

		self.queue_out.put(("SetStatusbar", ("Filtering demos; Parsing filter...",)))
		try:
			filters = filterstr_to_lambdas(filterstring)
		except Exception as error:
			self.queue_out.put(("SetStatusbar",
				("Error parsing filter request: " + str(error), 4000)))
			self.queue_out.put(("Finish", 0)); return

		if self.stoprequest.isSet():
			self.queue_out.put(("Finish", 2)); return

		self.queue_out.put(("SetStatusbar", ("Filtering demos; Reading information...",)))
		bookmarkdata = None
		files = None
		self.datafetcherqueue = queue.Queue()
		self.datafetcherthread = ThreadReadFolder(None, self.datafetcherqueue, {"curdir":curdir, "cfg":cfg, })
		self.datafetcherthread.start()
		self.datafetcherthread.join(None, 1) # NOTE: Severe wait time?
		if self.stoprequest.isSet():
			self.queue_out.put(("Finish", 2)); return

		while True:
			try:
				queueobj = self.datafetcherqueue.get_nowait()
				if queueobj[0] == "Result":
					files = queueobj[1]["col_filename"]
					bookmarkdata = queueobj[1]["col_bookmark"]
				elif queueobj[0] == "Finish":
					break
			except queue.Empty:
				break
		del self.datafetcherqueue
		if bookmarkdata == None:
			bookmarkdata = ()
		if self.stoprequest.isSet():
			self.queue_out.put(("Finish", 2)); return

		filteredlist = {"col_filename":[], "col_bookmark":[], "col_ctime":[], "col_filesize":[], }
		file_amnt = len(files)
		for i, j in enumerate(files): #Filter
			self.queue_out.put(  ("SetStatusbar", ("Filtering demos; {} / {}".format(i + 1, file_amnt), ) )  )
			if bookmarkdata[i] == None: # Oh no, an additional if in an often-repeated segment of code
				tmp_bm = ((), ())
			else:
				tmp_bm = bookmarkdata[i]
			curdataset = {"name":j, "killstreaks":tmp_bm[0], "bookmarks":tmp_bm[1],
				"header": HeaderFetcher(os.path.join(curdir, j)),
				"filedata": FileStatFetcher(os.path.join(curdir, j))}
			#The Fetcher classes prevent unneccessary drive access when the user i.E. only filters by name
			for l in filters:
				if not l(curdataset):
					break
			else:
				filteredlist["col_filename"].append(curdataset["name"])
				filteredlist["col_bookmark"].append(bookmarkdata[i])
				filteredlist["col_ctime"   ].append(curdataset["filedata"]["modtime"])
				filteredlist["col_filesize"].append(curdataset["filedata"]["filesize"])
			if self.stoprequest.isSet():
				self.queue_out.put(("Finish", 2)); return
		del filters
		self.queue_out.put(("Result", filteredlist))
		self.queue_out.put(("SetStatusbar",
			("Filtered {} demos in {} seconds.".format(file_amnt,
				str(round(time.time() - starttime, 3))), 3000)))
		self.queue_out.put(("Finish", 1))
