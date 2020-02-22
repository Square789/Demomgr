import os
import time
import queue

from demomgr.constants import THREADSIG
from demomgr.filterlogic import filterstr_to_lambdas
from demomgr.helpers import (FileStatFetcher, HeaderFetcher)
from demomgr.threads._base import _StoppableBaseThread
from demomgr.threads.read_folder import ThreadReadFolder

class ThreadFilter(_StoppableBaseThread):
	'''Thread takes no queue_inp, but queue_out and the following kwargs:
		filterstring <Str>: Raw user input from the entry field
		curdir <Str>: Absolute path to current directory
		cfg <Dict>: Program configuration as in .demomgr/config.cfg
		silent <Bool>: If True, thread will not drop progress messages
	'''
	def __init__(self, queue_inp, queue_out, filterstring, curdir, cfg, silent = False, *args, **kwargs):
		self.options = {"curdir": curdir, "filterstring": filterstring,
			"cfg": cfg, "silent": silent}

		super().__init__(queue_inp, queue_out, *args, **kwargs)

	def run(self):
		filterstring = self.options["filterstring"]
		curdir = self.options["curdir"]
		cfg = self.options["cfg"]
		starttime = time.time()

		self.queue_out_put(THREADSIG.INFO_STATUSBAR, ("Filtering demos; Parsing filter...", ))
		try:
			filters = filterstr_to_lambdas(filterstring)
		except Exception as error:
			self.queue_out_put(THREADSIG.INFO_STATUSBAR,
				("Error parsing filter request: " + str(error), 4000))
			self.queue_out_put(THREADSIG.FAILURE); return

		if self.stoprequest.isSet():
			self.queue_out_put(THREADSIG.ABORTED); return

		if not self.options["silent"]:
			self.queue_out_put(THREADSIG.INFO_STATUSBAR, ("Filtering demos; Reading information...",))
		bookmarkdata = None
		files = None
		self.datafetcherqueue = queue.Queue()
		self.datafetcherthread = ThreadReadFolder(self.datafetcherqueue, targetdir = curdir, cfg = cfg)
		self.datafetcherthread.start()
		self.datafetcherthread.join(None, dontstop = True) # NOTE: Can't really wait for join to this thread here.
		if self.stoprequest.isSet():
			self.queue_out_put(THREADSIG.ABORTED); return

		while True:
			try:
				queueobj = self.datafetcherqueue.get_nowait()
				if queueobj[0] == THREADSIG.RESULT_DEMODATA:
					files = queueobj[1]["col_filename"]
					bookmarkdata = queueobj[1]["col_bookmark"]
				elif queueobj[0] < 0x100: # Finish signal
					break
			except queue.Empty:
				break
		del self.datafetcherqueue
		if bookmarkdata == None:
			bookmarkdata = ()
		if self.stoprequest.isSet():
			self.queue_out_put(THREADSIG.ABORTED); return

		filteredlist = {"col_filename": [], "col_bookmark": [], "col_ctime": [], "col_filesize":[]}
		file_amnt = len(files)
		for i, j in enumerate(files): #Filter
			if not self.options["silent"]:
				self.queue_out_put(THREADSIG.INFO_STATUSBAR, ("Filtering demos; {} / {}".format(i + 1, file_amnt), ))
			if bookmarkdata[i] == None:
				tmp_bm = ((), ())
			else:
				tmp_bm = bookmarkdata[i]
			curdataset = {"name": j, "killstreaks": tmp_bm[0], "bookmarks": tmp_bm[1],
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
				self.queue_out_put(THREADSIG.ABORTED); return
		del filters
		self.queue_out_put(THREADSIG.INFO_STATUSBAR,
			("Filtered {} demos in {} seconds.".format(file_amnt,
				str(round(time.time() - starttime, 3))), 3000))
		self.queue_out_put(THREADSIG.RESULT_DEMODATA, filteredlist)
		self.queue_out_put(THREADSIG.SUCCESS)
