'''A module that brings the MultiframeList class with it.
Its purpose is to display items and their properties over
several colums and easily format, sort and manage them as part of a UI.'''
# ONLY CONFIRMED TO WORK ON WINDOWS 7 64 bit, Tcl/Tk v8.6, NOT EVERYTHING
# IS TESTED.
import tkinter as tk
import tkinter.ttk as ttk
from operator import itemgetter
from math import floor

__version__ = "2.0"
__author__ = "Square789"

BLANK = ""

_DEF_OPT = {"inicolumns":[{""}],
			"listboxstyle":{},
			"ttkhook":False,
			"rightclickbtn":"3"}

_DEF_COL_OPT =	{"name":"<NO_NAME>",
				"sort":False,
				"width":None,
				"formatter":None,
				"fallback_type":None,}

ALL = "all"
END = "end"
COLUMN = "column"
ROW = "row"
BORDERWIDTH = 2
ENTRYHEIGHT = 16
_STANDARDWIDTH = 20

class Column():
	'''Class whose purpose is to store data and information regarding a
	column. Can be assigned to frames of a MultiframeList, displaying
	its data in there.
	##################################################################
	!!! Columns should not be instantiated or controlled directly, !!!
	!!! only through methods of a MultiframeList.                  !!!
	##################################################################
	Args:
		mfl: Parent, must be a MultiframeList
	KwArgs:
	col_id: The identifying name of the column it will be addressed by.
		This is recommended to be a descriptive name set by the developer.
		If not specified, is set to an integer that is not
		in use by another Column. May not be changed after creation.
	names: Name to appear in the label and title the column.
	sort: Whether the column should sort the entire MultiframeList when its
		label is clicked.
	width: Set column to fixed length; if None, it will expand as normally.
	formatter: A function that formats each element in a column's datalist.
		This is especially useful for i. e. dates, where you want
		to be able to sort by a unix timestamp but still be able to have the
		dates in a human-readable format.
	fallback_type: A datatype that all elements of the column will be converted
		to in case it has to be sorted. If not specified and elements are of
		different types, an exception will be raised.
	'''
	# COLUMNS ARE RESPONSIBLE FOR UI UPDATING. GENERAL FLOW LIKE THIS:
	# USER INTERFACES WITH THE MFL, MFL KEEPS TRACK OF A FEW LISTS AND
	# VARS, VALIDATES, GIVES COMMANDS TO COLUMNS, COLUMNS UPDATE UI
	# THEMSELVES

	def __init__(self, mfl, col_id=None, **kwargs):
		if not isinstance(mfl, MultiframeList):
			raise TypeError("Bad Column parent, must be MultiframeList.")
		self.mfl = mfl

		self.__cnfcmd = {
			"name":self.__conf_name, "sort":self.__conf_sort,
			"width":self.__conf_width, "formatter":self.__conf_formatter,
			"fallback_type": lambda: False, }

		if col_id is None:
			self.col_id = self.__generate_col_id()
		else:
			for col in self.mfl.columns:
				if col.col_id == col_id:
					raise ValueError(
						"Column id {} is already in use!".format(
						col_id.__repr__()) )
			self.col_id = col_id

		self.data = [BLANK for _ in range(self.mfl.length)]
		self.sortstate = 0 # 0 if next sort will be descending, else 1

		self.cnf = _DEF_COL_OPT.copy()
		self.cnf.update(kwargs)

		self.setdisplay(kwargs.pop("iniframe", None))

	def __repr__(self):
		return "<{} of {} at {}, col_id: {}>".format(
			self.__class__.__name__, self.mfl.__class__.__name__, id(self.mfl),
			self.col_id)

	def __len__(self):
		return len(self.data)

	def __generate_col_id(self):
		curid = 0
		idok = False
		while not idok:
			for col in self.mfl.columns:
				if col.col_id == curid:
					curid += 1
					break
			else:
				idok = True
		return curid

	def __conf_name(self):
		if self.assignedframe is not None:
			self.mfl.frames[self.assignedframe][2].config(
				text = self.cnf["name"] )

	def __conf_sort(self):
		if self.assignedframe is not None:
			if self.cnf["sort"]:
				self.mfl.frames[self.assignedframe][2].bind("<Button-1>",
					lambda _: self.mfl.sort(_, self) )
			else:
				self.mfl.frames[self.assignedframe][2].unbind("<Button-1>")

	def __conf_width(self):
		if self.assignedframe is not None:
			width = self.cnf["width"]
			for widg in self.mfl.frames[self.assignedframe]:
				widg.config(width = width)
			expand_opt = 1 if width is None else 0
			self.mfl.frames[self.assignedframe][0].pack(expand = expand_opt)

	def __conf_formatter(self): # NOTE: YES OR NO?
		self.format()

	def config(self, **kw):
		if not kw:
			return self.cnf
		for k in kw:
			if not k in self.__cnfcmd:
				raise ValueError("Unkown configuration arg \"{}\", must be "
					"one of {}.".format(k, ", ".join([ck
					for ck in self.__cnfcmd])))
			self.cnf[k] = kw[k]
			self.__cnfcmd[k]()

	def data_clear(self):
		'''Clears self.data, refreshes interface, if assigned a frame.'''
		self.data.clear()
		if self.assignedframe is not None:
			self.mfl.frames[self.assignedframe][1].delete(0, tk.END)

	def data_insert(self, elem, index=None):
		'''Inserts elem to self.data at index and refreshes interface, if
		assigned a frame. If index is not specified, elem will be appended
		instead.
		'''
		if index is not None:
			self.data.insert(index, elem)
		else:
			self.data.append(elem)
			index = tk.END
		if self.assignedframe is not None:
			if self.cnf["formatter"] is not None:
				self.mfl.frames[self.assignedframe][1].insert(index,
					self.cnf["formatter"](elem))
			else:
				self.mfl.frames[self.assignedframe][1].insert(index, elem)

	def data_pop(self, index):
		'''Pops the element at index, refreshes interface if assigned a
		frame.
		'''
		self.data.pop(index)
		if self.assignedframe is not None:
			self.mfl.frames[self.assignedframe][1].delete(index)

	def data_set(self, newdata):
		'''Sets the column's data to the list specified, refreshes interface
		if assigned a frame.
		'''
		if not isinstance(newdata, list):
			raise TypeError("Data has to be a list!")
		self.data = newdata
		if self.assignedframe is not None:
			self.mfl.frames[self.assignedframe][1].delete(0, tk.END)
			self.mfl.frames[self.assignedframe][1].insert(tk.END, *self.data)

	def format(self):
		'''If interface frame is specified, runs all data through
		self.cnf["formatter"] and displays result.
		'''
		if self.cnf["formatter"] is not None and self.assignedframe is not None:
			f_data = [self.cnf["formatter"](i) for i in self.data]
			self.mfl.frames[self.assignedframe][1].delete(0, tk.END)
			self.mfl.frames[self.assignedframe][1].insert(tk.END, *f_data)

	def setdisplay(self, wanted_frame):
		'''Sets the display frame of the column to wanted_frame. To unregister,
		set it no None.'''
		self.assignedframe = wanted_frame
		if self.assignedframe is not None:
			for fnc in self.__cnfcmd.values(): fnc() # configure the frame
			self.mfl.frames[self.assignedframe][1].delete(0, tk.END)
			self.mfl.frames[self.assignedframe][1].insert(tk.END, *self.data)
			# NOTE: I don't think these two recurring lines warrant their own
			# "setframetodata" method.

class MultiframeList(ttk.Frame):
	'''Instantiates a multiframe tkinter based list
	arguments:
	master - parent object, should be tkinter root or a tkinter widget

	keyword arguments:
	inicolumns <List<Dict>>: The columns here will be created and displayed
		upon instantiation.
		The dicts supplied should take form of Column constructor kwargs. See
		the multiframe_list.Column class for a list of acceptable kwargs.

	ttkhook <Bool>: A terrible idea of a feature, if set to True, the
		MultiframeList will grab the currently active theme (as well as listen
		to the <<ThemeChanged>> event) and attempt to apply style configuration
		options in the current theme's style called "MultiframeList.Listbox" to
		its listboxes, as those are not available as ttk variants.
	rightclickbtn <Str>: The button that will trigger the MultiframeRightclick
		virtual event. It is 3 (standard) on windows, this may differ from
		platform to platform.

	The list broadcasts the Virtual event "<<MultiframeSelect>>" to its parent
		whenever something is selected.
	The list broadcasts the Virtual event "<<MultiframeRightclick>>" to its
		parent whenever a right click is performed or the context menu button
		is pressed.
	'''
	_DEFAULT_LISTBOX_CONFIG = {
		"activestyle": "underline",
		"background": "SystemButtonFace",
		"borderwidth": 1,
		"cursor": "",
		"disabledforeground": "SystemDisabledText",
		"font": "TkDefaultFont",
		"foreground": "SystemWindowText",
		"highlightbackground": "SystemButtonFace",
		"highlightcolor": "SystemWindowFrame",
		"highlightthickness": 1,
		"justify": "left",
		"relief": "sunken",
		"selectbackground": "SystemHightlight",
		"selectborderwidth": 0,
		"selectforeground": "SystemHighlightText",
	}

	def __init__(self, master, **options):

		super().__init__(master)

		self.master = master

		self.options = _DEF_OPT.copy()
		self.curcellx = None
		self.curcelly = None
		self.coordx = None
		self.coordy = None

		self.scrollbar = ttk.Scrollbar(self, command = self.__scrollallbar)
		self.framecontainer = ttk.Frame(self)

		self.frames = [] # Each frame contains interface elements for display.
		self.columns = [] # Columns will provide data storage capability as
		#well as some metadata.

		self.length = 0

		self.options.update(options) #user-defined options here
		opt_vals = self.options.values()
		self.options = dict( zip(
			([k for k in self.options]),
			(map(
				lambda a, b: list(a) if b else a,
				opt_vals,
				[isinstance(i, tuple) for i in opt_vals])
			)))
		del opt_vals
		# Converts every tuple to a list, leaving anything that isn't a tuple untouched.

		self.addframes(len(self.options["inicolumns"]))
		for index, colopt in enumerate(self.options["inicolumns"]):
			colopt["iniframe"] = index
			self.columns.append(Column(self, **colopt))

		if self.options["ttkhook"]:
			self.ttkhookstyle = ttk.Style()
			self.bind("<<ThemeChanged>>", self.__themeupdate)
			self.__themeupdate(None)

		self.framecontainer.pack(expand = 1, fill = tk.BOTH, side = tk.LEFT)
		self.scrollbar.pack(fill = tk.Y, expand = 0, side = tk.LEFT)

	#====USER METHODS====

	def addcolumns(self, *coldicts):
		'''Takes any amount of dicts, then adds columns where the column
		constructor receives the dicts as kwargs. See the
		multiframe_list.Column class for a list of acceptable kwargs.
		'''
		for coldict in coldicts:
			self.columns.append(Column(self, **coldict))

	def addframes(self, amount):
		'''Adds amount of frames, display slots in a way, fills their listboxes
		up with empty strings and immediatedly displays them.
		'''
		startindex = len(self.frames)
		for i in range(amount):
			self.frames.append([])
			curindex = startindex + i
			self.frames[curindex].append(ttk.Frame(self.framecontainer))
			self.frames[curindex].append(tk.Listbox(self.frames[curindex][0], exportselection = False) )
			self.frames[curindex].append(ttk.Label(self.frames[curindex][0], text = BLANK, anchor = tk.W))
			# [0] is Frame, [1] is Listbox, [2] is Label
			# https://infohost.nmt.edu/tcc/help/pubs/tkinter/web/extra-args.html
			def _handler0(event, self = self, button = self.options["rightclickbtn"], currow = curindex, fromclick = False):#This sort of code might get me to commit die one day.
				return self.__setindex(event, button, currow, fromclick)
			def _handler1(event, self = self, button = 1, currow = curindex, fromclick = True):
				return self.__setindex(event, button, currow, fromclick)
			def _handler2(event, self = self, button = self.options["rightclickbtn"], currow = curindex, fromclick = True):
				return self.__setindex(event, button, currow, fromclick)
			self.frames[curindex][1].bind("<KeyPress-App>", _handler0)
			self.frames[curindex][1].bind("<<ListboxSelect>>", _handler1)
			self.frames[curindex][1].bind("<Button-" + self.options["rightclickbtn"] + ">", _handler2)
			self.frames[curindex][1].config(yscrollcommand = self.__scrollalllistbox)
			self.frames[curindex][1].insert(tk.END, *(BLANK for _ in range(self.length)))

			self.frames[curindex][2].pack(expand = 0, fill = tk.X, side = tk.TOP) 		#pack label
			self.frames[curindex][1].pack(expand = 1, fill = tk.BOTH, side = tk.LEFT)	#pack listbox
			self.frames[curindex][0].pack(expand = 1, fill = tk.BOTH, side = tk.LEFT)	#pack frame

	def assigncolumn(self, col_id, req_frame):
		'''Sets display of a column given by its column id to req_frame.
		The same frame may not be occupied by multiple columns and must
		exist. Set req_frame to None to hide the column.
		'''
		if req_frame is not None:
			self.frames[req_frame] # Raises error on failure
			for col in self.columns:
				if col.assignedframe == req_frame:
					raise RuntimeError("Frame {} is already in use by column "
						"\"{}\"".format(req_frame, col.col_id))
		col = self._get_col_by_id(col_id)
		old_frame = col.assignedframe
		col.setdisplay(req_frame)
		# old frame is now column-less, so the list itself has to update it
		if old_frame is None: return
		old_frameobj = self.frames[old_frame]
		old_frameobj[2].configure(text = BLANK)
		old_frameobj[2].unbind("<Button-1>")
		old_frameobj[1].delete(0, tk.END)
		old_frameobj[1].insert(0, *[BLANK
			for _ in range(self.length)])
		for w in old_frameobj: w.configure(width = _STANDARDWIDTH)

	def clear(self):
		'''Clears the MultiframeList.'''
		for col in self.columns:
			col.data_clear()
		self.length = 0
		self.curcellx = None
		self.curcelly = None
		self.__lengthmod_callback()

	def configcolumn(self, col_id, **cnf):
		'''Update the configuration of the column referenced by col_id
		with the values specified in cnf as kwargs.'''
		col = self._get_col_by_id(col_id)
		col.config(**cnf)

	def format(self, targetcols = None):
		'''Format the entire list based on the formatter functions in columns.
		Optionally, a list of columns to be formatted can be supplied by their
		id, which will leave all non-mentioned columns alone.

		! Call this after all input has been performed !'''
		if targetcols is None:
			for col in self.columns:
				col.format()
		else:
			for col_id in targetcols:
				self._get_col_by_id(col_id).format()
		self.__selectionmod_callback()

	def getcolumns(self):
		'''Returns a dict where key is a column id and value is the column's
		current display slot (frame). Value is None if the column is hidden.
		'''
		return {c.col_id: c.assignedframe for c in self.columns}

	def getselectedcell(self):
		'''Returns the coordinates of the currently selected cell as a tuple
		of length 2; (0, 0) starting in the top left corner;
		The two values may also be None.
		'''
		return (self.curcellx, self.curcelly)

	def getlastclick(self):
		'''Returns the coordinates in the listbox the last click was made in as
		a tuple. May consist of int or None.
		'''
		return (self.coordx, self.coordy)

	def getlen(self):
		'''Returns length of the multiframe-list.'''
		return self.length

	def removecolumn(self, col_id):
		'''Deletes the column addressed by col_id, safely unregistering all
		related elements.
		'''
		col = self._get_col_by_id(col_id)
		self.assigncolumn(col_id, None)
		for i, j in enumerate(self.columns):
			if j.col_id == col_id:
				self.columns.pop(i)
				break
		del col

	def removeframes(self, amount):
		'''Safely remove the specified amount of frames from the
		MultiframeList, unregistering all related elements.
		'''
		to_purge = range(len(self.frames) - 1, len(self.frames) - amount - 1,
			-1)
		for col in self.columns:
			if col.assignedframe in to_purge:
				col.setdisplay(None)
		for i in to_purge:
			self.frames[i][0].destroy()
			self.frames.pop(i)

	def setcell(self, col_to_mod, y, data):
		'''Sets the cell in col_to_mod at y to data.'''
		col = self._get_col_by_id(col_to_mod)
		if y > (self.length - 1):
			raise IndexError("Cell index does not exist.")
		col.data_pop(y)
		col.data_insert(data, y)

	def removerow(self, index):
		'''Will delete the entire row at index, visible or not visible.'''
		if index > (self.length - 1):
			raise IndexError("Index to remove out of range.")
		for col in self.columns:
			col.data_pop(index)
		self.length -= 1
		self.__lengthmod_callback()

	#==DATA MODIFICATION, ALL==

	def insertrow(self, data, insindex = None):
		'''Data should be supplied in the shape of a dict where a key is a
		column's id and the corresponding value is the element that should
		be appended to the column.
		If insindex is not specified, data will be appended, else inserted
		at the given position.
		Raises an exception if the lists differ in lengths.
		'''
		for col in self.columns:
			if col.col_id in data:
				col.data_insert(data.pop(col.col_id), insindex)
			else:
				col.data_insert(BLANK, insindex)
		self.length += 1
		self.__lengthmod_callback()

	def setdata(self, data):
		'''Data has to be supplied as a dict where:
		key is a column id and value is a list of values the column targeted by
		key should be set to. If the lists are of differing lengths, an
		exception will be raised.
		'''
		if not data:
			self.clear(); return
		ln = len(data[next(iter(data))])
		for k in data:
			if len(data[k]) != ln:
				raise ValueError("Differing lengths in supplied column data.")
		for col in self.columns:
			if col.col_id in data:
				col.data_set(data.pop(col.col_id))
			else:
				col.data_set([BLANK for _ in range(ln)])
		self.length = ln
		self.curcellx, self.curcelly = None, None
		self.__lengthmod_callback()

	def setcolumn(self, col_to_mod, data):
		'''Sets column specified by col_to_mod to data.
		Raises an exception if length differs from the rest of the
		columns.
		'''
		targetcol = self._get_col_by_id(col_to_mod)
		datalen = len(data)
		if len(self.columns) == 1:
			targetcol.data_set(data)
			self.length = datalen
			self.__lengthmod_callback()
			return
		for col in self.columns:
			if len(col.data) != datalen:
				raise ValueError("Length of supplied column data is"
					" different from other lengths.")
		targetcol.data_set(data)

	#==DATA MODIFICATION, VISIBLE ONLY==

	def insertrow_v(self, data, insindex = None):
		'''NOTE that only visible columns will be modified, hidden columns
		will be truncated or filled up with blank strings, for recommended
		control of invisible columns see the insertrow method.
		If an iterator is given as an arg, its elements will be appended
		to the currently visible columns, in order.
		If the input data is too long, it will be truncated, if too short, the
		MultiframeList will be filled up with empty strings so that all
		columns, visible or not, will end up with the same length.
		'''
		if data: # Data is specified
			col_to_mod = self.__getdisplayedcolumns()
			apd_data = list(data) + [ # extend data
				BLANK for _ in range(len(col_to_mod) - len(data))]
			for index, column in enumerate(col_to_mod):
				column.data_insert(apd_data[index], insindex)
			for column in self.__gethiddencolumns():
				column.data_insert(BLANK, insindex)
		self.length += 1
		self.__lengthmod_callback()

	def setdata_v(self, data, mode = "row"): #TODO: Update and stop using insertrow_v but who cares this func is garbage anyways
		'''NOTE that only visible columns will be modified, hidden columns
		will be truncated or filled up with blank strings, for recommended
		control of invisible columns see the setdata method.
		This function will set the data to the supplied data, inserting it
		following these rules:
		The mode keyword argument of this function has two forms:
		row (standard): The data (given through the data arg as a two-
			dimensional list) will be inserted into the currently visible
			columns, every sub-element being treated as a row from top to
			bottom.
		column: The data (given through the data arg as a two-dimensional
			list) will be inserted into the currently visible columns, each
			sub-element being treated as a column. Raises an exception if the
			supplied columns are not equal in length.
		'''
		if mode == "row":
			ln = len(data)
		elif mode == "column":
			if not data: self.clear(); return #On empty data, just clear so below data[0] doesn't raise exception
			data = list(zip(*data)) #Shift list
			ln = len(data[0])
			if not all([len(i) == ln for i in data]) == True:
				raise ValueError("Inequal column length in supplied data.")
		self.clear()
		for i in data:
			self.insertrow_v(i)
		self.length = ln
		self.__lengthmod_callback()

	#==DATA RETRIEVAL, DICT, ALL==

	def getrows(self, start, end = None):
		'''If end is omitted, only the row indexed at start will be included.
		If end is set to END, all data from start to the end of the
		MultiframeListbox will be returned.
		If start is set to ALL, all data that is present in the
		MultiframeListbox' columns will be included.
		This method will return two elements:
		A two-dimensional list that contains the requested rows from start to
			end, a row being unformatted data.
		A dict where the values are integers and the keys all column's ids.
			The integer for a column gives the index of all sub-lists in the
			first returned list that make up the data of a column, in order.
		For example, if the return values were:
		[["egg", "2", ""], ["foo", "3", "Comment"], ["bar", "0", ""]],
		{"name_col":0, "comment_col":2, "rating_col":1}, the data of the
		column "name_col" would be ["egg", "foo", "bar"], "rating_col"
		["2", "3", "0"] and "comment_col" ["", "Comment", ""].
		'''
		if start == "all":
			start = 0
			end = self.length
		if end == END:
			end = self.length
		if end is None:
			end = start + 1
		col_id_map = {c.col_id: ci for ci, c in enumerate(self.columns)}
		r_data = []
		cols = tuple([i for i in self.columns])
		for ind in range(start, end):
			cur_row = []
			for col in cols:
				cur_row.append(col.data[ind])
			r_data.append(cur_row)
		return r_data, col_id_map

	def getcolumn(self, col_id):
		'''Returns the data of the colum with col_id as a list.'''
		col = self._get_col_by_id(col_id)
		return col.data

	def getcell(self, col_id, y):
		'''Returns element y of the column specified by col_id.'''
		col = self._get_col_by_id(col_id)
		return col.data[y]

	#====SORT METHOD====

	def sort(self, _evt, call_col):
		'''This function will sort the list, modifying all column's data.
		It is designed to only be called through labels, taking an event
		placeholder as arg, followed by the calling column where id, sortstate
		and - if needed - the fallback type are read from.
		'''
		sortstate = call_col.sortstate
		caller_id = call_col.col_id
		scroll = None
		if len(self.frames) != 0:
			scroll = self.frames[0][1].yview()[0]
		rev = False
		if sortstate:
			rev = True
		call_col.sortstate = bool(abs(int(sortstate) - 1))
		tmpdat, colidmap = self.getrows(ALL)
		datacol_index = colidmap[caller_id]
		try:
			tmpdat = sorted(tmpdat, key = itemgetter(datacol_index),
				reverse = rev)
		except TypeError:
			fb_type = call_col.config()["fallback_type"]
			if fb_type is None: raise
			for i in range(len(tmpdat)):
				tmpdat[i][datacol_index] = fb_type(tmpdat[i][datacol_index])
			tmpdat = sorted(tmpdat, key = itemgetter(datacol_index),
				reverse = rev)
		newdat = {}
		for col_id in colidmap:
			datacol_i = colidmap[col_id]
			newdat[col_id] = [i[datacol_i] for i in tmpdat]
		self.setdata(newdat)
		self.format()
		if scroll is not None:
			self.__scrollalllistbox(scroll, 1.0)

	#====INTERNAL METHODS====

	def _get_col_by_id(self, col_id):
		'''Returns the column specified by col_id, raises an exception if it
		is not found.
		'''
		for col in self.columns:
			if col.col_id == col_id:
				return col
		raise ValueError("No column with column id \"{}\".".format(col_id))

	def __getdisplayedcolumns(self):
		'''Returns a list of references to the columns that are displaying
		their data currently, sorted starting at 0.
		'''
		# assumes that there are no unfilled frames, under no circumstances
		# leave it like this!!!
		r = sorted([i for i in self.columns if i.assignedframe is not None],
			key = lambda col: col.assignedframe)
		#print(r)
		return r

	def __gethiddencolumns(self):
		'''Get all columns that are not being currently displayed.'''
		return [col for col in self.columns if col.assignedframe is None]

	def __getemptyframes(self):
		'''Returns the indexes of all frames that are not assigned a column.'''
		existingframes = list(range(len(self.frames)))
		assignedframes = [col.assignedframe for col in self.columns]
		return [f for f in existingframes if not f in assignedframes]

	def __setindex(self, event, button, frameindex, fromclick):
		'''Called by listboxes; GENERATES EVENT, sets the current index.'''
		if self.length == 0: return
		if button == self.options["rightclickbtn"] and fromclick:
			offset = event.widget.yview()[0] * self.length
			tosel = int(floor((event.y + - BORDERWIDTH) / ENTRYHEIGHT) + offset)
			if tosel < 0: return
			if tosel >= self.length: tosel = self.length - 1
			event.widget.selection_clear(0, tk.END)
			event.widget.selection_set(tosel)
		sel = event.widget.curselection()[0]
		event.widget.focus_set()
		self.curcelly = sel
		self.curcellx = frameindex
		self.__selectionmod_callback()
		self.coordx = event.x
		self.coordy = event.y
		self.master.event_generate("<<MultiframeSelect>>", when = "tail")
		if button == self.options["rightclickbtn"]:
			self.master.event_generate("<<MultiframeRightclick>>",
				when = "tail")

	def __lengthmod_callback(self):
		'''Called by some methods after the MultiframeList's length was
		modified. This method updates frames without a column so the amount
		of blank strings in them stays correct and modifies the current
		selection index in case it is out of bounds.'''
		for fi in self.__getemptyframes():
			curframelen = self.frames[fi][1].size()
			if curframelen != self.length:
				if curframelen > self.length:
					self.frames[fi][1].delete(self.length, tk.END)
				else: # curframelen < self.length
					self.frames[fi][1].insert(tk.END,
						*(BLANK for _ in range(self.length - curframelen)))
		if self.curcelly is None: return
		if self.curcelly > self.length - 1:
			self.curcelly = self.length - 1
		if self.curcelly < 0:
			self.curcelly = None
		self.__selectionmod_callback()

	def __scrollallbar(self, a, b, c = None): #c only appears when holding mouse and scrolling on the scrollbar
		'''Bound to the scrollbar; Will scroll listboxes.'''
		if c:
			for i in self.frames:
				i[1].yview(a, b, c)
		else:
			for i in self.frames:
				i[1].yview(a, b)

	def __scrollalllistbox(self, a, b):
		'''Bound to all listboxes so that they will scroll the other ones
		and scrollbar.
		'''
		for i in self.frames:
			i[1].yview_moveto(a)
		self.scrollbar.set(a, b)

	def __selectionmod_callback(self):
		'''Called after selection (self.curcell[x/y]) is modified.
		Purely cosmetic effect, as actual selection access should only
		occur via self.curcell()'''
		sel = self.curcelly
		if sel is None:
			for i in self.frames:
				i[1].selection_clear(0, tk.END)
			return
		for i in self.frames:
			i[1].selection_clear(0, tk.END)
			i[1].selection_set(sel)
			i[1].activate(sel)

	def __themeupdate(self, _):
		'''Called from event binding when ttkhook is set to true at
		initialization. Changes Listbox look, as those are not in ttk.'''
		conf = self._DEFAULT_LISTBOX_CONFIG.copy()
		for style in (".", "MultiframeList.Listbox"):
			cur_style_cnf = self.ttkhookstyle.configure(style)
			if cur_style_cnf is not None:
				conf.update(cur_style_cnf)
		if self.frames:
			ok_options = self.frames[0][1].configure().keys()
			conf = {k: v for k, v in conf.items() if k in ok_options}
		for i in self.frames:
			lbwidg = i[1]
			lbwidg.configure(**conf)

if __name__ == "__main__":
	from random import randint
	def test():
		def adddata():
			mf.insertrow_v([randint(0,100) for _ in range(10)])
			mf.format()

		def add1col():
			if "newcol" in mf.getcolumns():
				mf.removecolumn("newcol")
			else:
				mf.addcolumns({"col_id":"newcol", "name":"added @ runtime"})
				mf.assigncolumn("newcol", 6)

		def getcurrrow(end = None):
			xind = mf.getselectedcell()[1]
			if xind is None:
				print("No row is selected, cannot output."); return
			outdat, mapdict = mf.getrows(xind, end)
			print(outdat, mapdict)
			def getlongest(seqs):
				longest = 0
				for i in seqs:
					if isinstance(i, (list, tuple)):
						res = getlongest(i)
					else:
						res = len(str(i))
					if res > longest:
						longest = res
				return longest
			l_elem = getlongest(outdat)
			l_elem2= getlongest(mapdict.keys())
			if l_elem2 > l_elem: l_elem = l_elem2
			frmtstr = "{:<{ml}}"
			print("|".join([frmtstr.format(i, ml = l_elem) 
				for i in mapdict.keys()]))
			print("-"*(l_elem + 1)*len(mapdict.keys()))
			for row in outdat:
				print("|".join([frmtstr.format(i, ml = l_elem) for i in row]))

		def remframe():
			if len(mf.frames) <= 7:
				print("Cannot remove this many frames from example!"); return
			mf.removeframes(1)

		def remrow():
			if mf.length == 0:
				print("List is empty already!"); return
			if mf.getselectedcell()[1] is None:
				print("Select a row to delete!"); return
			mf.removerow(mf.getselectedcell()[1])

		def swap01():
			c_a = 1
			c_b = 0
			if mf.getcolumns()[0] == 0:
				c_a = 0
				c_b = 1
			mf.assigncolumn(0, None)
			mf.assigncolumn(1, None)
			mf.assigncolumn(c_a, 1)
			mf.assigncolumn(c_b, 0)

		def priceconv(data):
			return str(data) + "$"

		btns = ({"text":"+row","command":adddata},
				{"text":"-row", "command":remrow},
				{"text":"---", "command":lambda: mf.clear()},
				{"text":"+frame", "fg":"#AA0000", "command":
					lambda: mf.addframes(1)},
				{"text":"-frame", "command":remframe},
				{"text":"getcolumns", "command":lambda: print(mf.getcolumns())},
				{"text":"getcurrow", "command":lambda: getcurrrow()},
				{"text":"get_to_end", "command":lambda: getcurrrow(END)},
				{"text":"getcurcell", "command":
					lambda: print(mf.getselectedcell())},
				{"text":"getlength", "command":lambda: print(mf.getlen())},
				{"text":"addcolumn", "command":lambda: add1col()},
				{"text":"swp01", "command":swap01}, )
		root = tk.Tk()
		mf = MultiframeList(root, inicolumns=(
		{"name":"smol col", "width":10},
		{"name":"Sortercol", "sort":True},
		{"name":"sickocol", "sort":True, "col_id":"sickocol"},
		{"name":"-100", "col_id":"sub_col", "formatter":lambda n: n-100},
		{"name":"Wide col", "width":30},
		{"name":"unconf name","col_id":"cnfcl"} ),
		listboxstyle = {"background":"#4E4E4E", "foreground":"#EEEEEE"})
		mf.configcolumn("sickocol", formatter = priceconv)
		mf.configcolumn("cnfcl", name = "Configured Name", sort = True,
			fallback_type = lambda x: int("0" + str(x)))
		mf.pack(expand = 1, fill = tk.BOTH)
		mf.addframes(2)
		mf.removeframes(1)

		for b_args in btns:
			b = tk.Button(root, **b_args)
			b.pack(fill = tk.X, side = tk.LEFT)

		#def testram():
		#	for _ in range(100):
		#		mf.addframes(3)
		#		mf.removeframes(3)
		#hellbutton = tk.Button(root, text = "Attempt to memleak",
		#	command = testram)
		#hellbutton.pack(fill = tk.X, side = tk.LEFT)
		root.mainloop()

	test()
