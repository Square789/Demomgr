import tkinter as tk
import tkinter.ttk as ttk

import os

from ._base import BaseDialog
from .. import multiframe_list as mfl
from .. import constants as CNST
from ..helpers import (assignbookmarkdata, formatdate, convertunit,
	formatbookmarkdata, frmd_label, readdemoheader, HeaderFetcher,
	FileStatFetcher, format_bm_pair)
from ..filterlogic import filterstr_to_lambdas
from .deleter import Deleter

class Cleanup(BaseDialog): #TODO: Add thread
	'''Cleanup dialog that allows for a selection of multiple demos and
	invokes a fitting Cleanup dialog based on the user's selection.
	'''
	def __init__(self, parent, files, bookmarkdata, dates, filesizes, curdir,
			cfg, styleobj):
		'''Args:
		parent: Tkinter widget that is the parent of this dialog.
		files: List of file names that should be offered in the demos.
		bookmarkdata: Bookmarkdata, has to be parallel to files.
		dates: List of dates as UNIX timestamps, has to be parallel to files.
		filesizes: List of integers, has to be parallel to files.
		curdir: The absolute path to the directory containing all files.
		cfg: Program configuration.
		styleobj: Instance of tkinter.ttk.Style.
		'''
		self.master = parent

		self.bookmarkdata = bookmarkdata
		self.files = files
		self.dates = dates
		self.filesizes = filesizes
		self.curdir = curdir
		self.cfg = cfg
		self.styleobj = styleobj

		self.symbollambda = lambda x: " X" if x else ""

		self.keepevents_var = tk.BooleanVar()
		self.deluselessjson_var = tk.BooleanVar()
		self.selall_var = tk.BooleanVar()
		self.filterbox_var = tk.StringVar()

		self.result_ = {"state":0}

		super().__init__(parent, "Cleanup...")

	def body(self, master):
		'''UI'''
		master.bind("<<MultiframeSelect>>", self.__procentry)

		self.demoinflabel = ttk.Label(master, text = "", justify = tk.LEFT,
			anchor = tk.W, font = ("Consolas", 8))

		condframe = ttk.LabelFrame(master, padding = (3, 8),
			labelwidget = frmd_label(master, "Demo selector / Filterer"))
		self.filterbox = ttk.Entry(condframe, textvariable = self.filterbox_var)
		self.applybtn = ttk.Button(condframe, text = "Apply filter",
			command = self.__applycond, style = "Contained.TButton")

		optframe = ttk.LabelFrame(master, padding = (3, 8, 3, 8),
			labelwidget = frmd_label(master, "Options"))
		keepevents_checkbtn = ttk.Checkbutton(optframe,
			variable = self.keepevents_var, text = "Make backup of " +
			CNST.EVENT_FILE, style = "Contained.TCheckbutton")
		deljson_checkbtn = ttk.Checkbutton(optframe,
			variable = self.deluselessjson_var, text = "Delete orphaned "
			"json files", style = "Contained.TCheckbutton")

		self.listbox = mfl.MultiframeList(master, inicolumns = (
			{"name":"", "col_id":"col_sel", "width":2,
				"formatter": self.symbollambda},
			{"name":"Filename", "col_id":"col_filename", "sort":True, },
			{"name":"Bookmarks", "col_id":"col_bookmark", "width":26,
				"formatter":format_bm_pair, },
			{"name":"Date created", "col_id":"col_ctime", "width":19,
				"formatter":formatdate, "sort":True, },
			{"name":"Filesize", "col_id":"col_filesize",  "width":10,
				"formatter":convertunit, "sort":True, }, ), )
		self.listbox.setdata({
			"col_sel":[False for _ in self.files],
			"col_filename":self.files,
			"col_ctime":self.dates,
			"col_bookmark":self.bookmarkdata,
			"col_filesize":self.filesizes, })
		self.listbox.format()

		#NOTE: looks icky
		self.listbox.frames[0][2].pack_propagate(False)
		selall_checkbtn = ttk.Checkbutton(self.listbox.frames[0][2],
			variable = self.selall_var, text = "", command = self.selall)

		okbutton = ttk.Button(master, text = "Delete",
			command = lambda: self.done(1) )
		cancelbutton = ttk.Button(master, text= "Cancel",
			command = lambda: self.done(0) )

		self.applybtn.pack(side = tk.RIGHT)
		self.filterbox.pack(side = tk.RIGHT, fill = tk.X, expand = 1, padx = (0, 5))
		condframe.pack(fill = tk.BOTH, pady = (4, 5))

		keepevents_checkbtn.pack(side = tk.LEFT, ipadx = 2, padx = 4)
		deljson_checkbtn.pack(side = tk.LEFT, ipadx = 2, padx = 4)
		optframe.pack(fill = tk.BOTH, pady = 5)

		selall_checkbtn.pack(side = tk.LEFT, anchor = tk.W)
		self.listbox.pack(side = tk.TOP, fill = tk.BOTH, expand = 1)
		self.demoinflabel.pack(side = tk.TOP, fill = tk.BOTH, expand = 0, anchor = tk.W)

		okbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		cancelbutton.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (3, 0))

	def __setinfolabel(self, content):
			self.demoinflabel.config(text = content)

	def __procentry(self, event):
		index = self.listbox.getselectedcell()[1]
		if self.cfg["previewdemos"]:
			try:
				hdr = readdemoheader(os.path.join(self.curdir,
					self.listbox.getcell("col_filename", index)) )
			except Exception:
				hdr = CNST.FALLBACK_HEADER
			self.__setinfolabel("Host: {}| ClientID: {}| Map: {}".format(
				hdr["hostname"], hdr["clientid"], hdr["map_name"]))

		if self.listbox.getselectedcell()[0] != 0: return
		if index == None: return
		self.listbox.setcell("col_sel", index,
			(not self.listbox.getcell("col_sel", index)))
		if False in self.listbox.getcolumn("col_sel"):
			self.selall_var.set(0)
		else:
			self.selall_var.set(1)

	def __setitem(self, index, value, lazyui = False): #value: bool
		self.listbox.setcell("col_sel", index, value)
		if not lazyui:
			if False in self.listbox.getcolumn("col_sel"): #~ laggy
				self.selall_var.set(0)
			else:
				self.selall_var.set(1)
			# Do not refresh ui. This is done while looping over the elements,
			# then a final refresh is performed.

	def __applycond(self):
		'''Apply user-entered condition to the files. This blocks the
		UI, as I cannot be bothered to do it otherwise tbf.'''
		filterstr = self.filterbox_var.get()
		if filterstr == "":
			return
		self.__setinfolabel("Parsing filter conditions...")
		try:
			filters = filterstr_to_lambdas(filterstr)
		except Exception as error:
			self.__setinfolabel("Error parsing filter: " + str(error))
			return
		self.__setinfolabel("Applying filters, please hold on...")
		for i, j in enumerate(self.files):
			if self.bookmarkdata[i] == None:
				tmp_bm = ((), ())
			else:
				tmp_bm = self.bookmarkdata[i]
			curfile = {"name":j, "killstreaks":tmp_bm[0], "bookmarks":tmp_bm[1],
				"header": HeaderFetcher(os.path.join(self.curdir, j)),
				"filedata": FileStatFetcher(os.path.join(self.curdir, j))}
			curdemook = True
			for f in filters:
				if not f(curfile):
					curdemook = False
					break
			if curdemook:
				self.__setitem(i, True, True)
			else:
				self.__setitem(i, False, True)
		if len(self.listbox.getcolumn("col_sel")) != 0: #set sel_all checkbox
			self.__setitem(0, self.listbox.getcell("col_sel", 0), False)
		self.__setinfolabel("Done.")

	def selall(self):
		if False in self.listbox.getcolumn("col_sel"):
			self.listbox.setcolumn("col_sel", [True for _ in self.files])
		else:
			self.listbox.setcolumn("col_sel", [False for _ in self.files])
		self.listbox.format(["col_sel"])

	def done(self, param):
		if param:
			dialog_ = Deleter(self.master, demodir = self.curdir,
				files = self.listbox.getcolumn("col_filename"),
				selected = self.listbox.getcolumn("col_sel"),
				keepeventsfile = self.keepevents_var.get(),
				deluselessjson = self.deluselessjson_var.get(),
				cfg = self.cfg, styleobj = self.styleobj,
				eventfileupdate = "selectivemove")
			self.grab_set() #NOTE: This is quite important.
			if dialog_.result_["state"] != 0:
				self.result_["state"] = 1
				self.destroy()
		else:
			self.destroy()
