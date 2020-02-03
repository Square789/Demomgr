'''A module that brings the MultiframeList class with it.
Its purpose is to display items and their properties over
several colums and easily format, sort and manage them as part of a UI.'''
# ONLY CONFIRMED TO WORK ON WINDOWS 7 64 bit, Tcl/Tk v8.6, NOT EVERYTHING
# IS TESTED.
import tkinter as tk
import tkinter.ttk as ttk
from operator import itemgetter
from math import floor

__version__ = "3.0"
__author__ = "Square789"

BLANK = ""

_DEF_LISTBOX_WIDTH = 20

_DEF_OPT = {"inicolumns": [],
			"listboxstyle": {},
			"rightclickbtn": "3", }

_DEF_COL_OPT =	{"name": "<NO_NAME>",
				"sort": False,
				"minsize": 0,
				"weight": 1,
				"w_width": _DEF_LISTBOX_WIDTH,
				"formatter": None,
				"fallback_type": None,}

ALL = "all"
END = "end"
COLUMN = "column"
ROW = "row"
BORDERWIDTH = 2
ENTRYHEIGHT = 16

SORTSYM = ("\u25B2", "\u25BC", "\u25A0") #desc, asc, none

class Column():
	"""
	Class whose purpose is to store data and information regarding a
	column. Can be assigned to frames of a MultiframeList, displaying
	its data in there.
	##################################################################
	!!! Columns should not be instantiated or controlled directly, !!!
	!!! only through methods of a MultiframeList.                  !!!
	##################################################################
	Required args:

	mfl: Parent, must be a MultiframeList

	Optional args:

	col_id: The identifying name of the column it will be addressed by.
		This is recommended to be a descriptive name set by the developer.
		If not specified, is set to an integer that is not
		in use by another Column. May not be changed after creation.
	names: Name to appear in the label and title the column.
	sort: Whether the column should sort the entire MultiframeList when its
		label is clicked.
	w_width: The width the widgets in this Column's occupied frame
		should have, measured in text units.
		The tkinter default for the label is 0, for the listbox 20, it is
		possible that the listbox stretches further than it should.
		! NOT TO BE CONFUSED WITH minsize !
	minsize: Specify the minimum amount of pixels the column should occupy.
		This option gets passed to the grid geometry manager.
		! NOT TO BE CONFUSED WITH w_width !
	weight: Weight parameter according to the grid geometry manager.
	formatter: A function that formats each element in a column's datalist.
		This is especially useful for i. e. dates, where you want
		to be able to sort by a unix timestamp but still be able to have the
		dates in a human-readable format.
	fallback_type: A datatype that all elements of the column will be converted
		to in case it has to be sorted. If not specified and elements are of
		different types, an exception will be raised.
	"""
	# COLUMNS ARE RESPONSIBLE FOR UI UPDATING. GENERAL FLOW LIKE THIS:
	# USER INTERFACES WITH THE MFL, MFL KEEPS TRACK OF A FEW LISTS AND
	# VARS, VALIDATES, GIVES COMMANDS TO COLUMNS, COLUMNS UPDATE UI
	# THEMSELVES

	def __init__(self, mfl, col_id=None, **kwargs):
		if not isinstance(mfl, MultiframeList):
			raise TypeError("Bad Column parent, must be MultiframeList.")
		self.mfl = mfl
		self.assignedframe = None

		self.__cnfcmd = {
			"name":self.__cnf_name, "sort":self.__cnf_sort,
			"minsize":self.__cnf_grid, "weight": self.__cnf_grid,
			"formatter":self.__cnf_formatter, "w_width": self.__cnf_w_width,
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
		self.sortstate = 2 # 0 if next sort will be descending, else 1

		self.cnf = _DEF_COL_OPT.copy()
		self.cnf.update(kwargs)

	def __repr__(self):
		return "<{} of {} at {}, col_id: {}>".format(
			self.__class__.__name__, self.mfl.__class__.__name__,
			hex(id(self.mfl)), self.col_id)

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

	def __cnf_formatter(self): # NOTE: YES OR NO?
		self.format()

	def __cnf_grid(self):
		if self.assignedframe is not None:
			curr_grid = self.mfl.framecontainer.grid_columnconfigure(
				self.assignedframe)
			callargs = {}
			for value in ("minsize", "weight"):
				if curr_grid[value] != self.cnf[value]:
					callargs[value] = self.cnf[value]
			if callargs:
				self.mfl.framecontainer.grid_columnconfigure(self.assignedframe,
					**callargs)
			# width = self.cnf["minsize"]
			#for widg in self.mfl.frames[self.assignedframe]:
			#	widg.config(width = width)
			# expand_opt = 1 if width is None else 0
			# self.mfl.frames[self.assignedframe][0].pack(expand = expand_opt)

	def __cnf_name(self):
		if self.assignedframe is not None:
			self.mfl.frames[self.assignedframe][2].config(
				text = self.cnf["name"] )

	def __cnf_sort(self):
		if self.assignedframe is not None:
			if self.cnf["sort"]:
				self.set_sortstate(self.sortstate)
				self.mfl.frames[self.assignedframe][2].bind("<Button-1>",
					lambda _: self.mfl.sort(_, self))
			else:
				self.mfl.frames[self.assignedframe][3].configure(text = BLANK)
				self.mfl.frames[self.assignedframe][2].unbind("<Button-1>")

	def __cnf_w_width(self):
		if self.assignedframe is not None:
			self.mfl.frames[self.assignedframe][1].configure(
				width = self.cnf["w_width"])

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

	def format(self, exclusively = None):
		'''If interface frame is specified, runs all data through
		self.cnf["formatter"] and displays result.
		If exclusively is set (as an iterable),
		only specified indices will be formatted.
		'''
		if self.cnf["formatter"] is not None and self.assignedframe is not None:
			if exclusively is None:
				f_data = [self.cnf["formatter"](i) for i in self.data]
				self.mfl.frames[self.assignedframe][1].delete(0, tk.END)
				self.mfl.frames[self.assignedframe][1].insert(tk.END, *f_data)
			else:
				for i in exclusively:
					tmp = self.data[i]
					self.mfl.frames[self.assignedframe][1].delete(i)
					self.mfl.frames[self.assignedframe][1].insert(i, self.cnf["formatter"](tmp))

	def setdisplay(self, wanted_frame):
		'''Sets the display frame of the column to wanted_frame. To unregister,
		set it no None.'''
		self.assignedframe = wanted_frame
		if self.assignedframe is not None:
			for fnc in self.__cnfcmd.values(): fnc() # configure the frame
			self.set_sortstate(self.sortstate)
			self.mfl.frames[self.assignedframe][1].delete(0, tk.END)
			self.mfl.frames[self.assignedframe][1].insert(tk.END, *self.data)
			# NOTE: I don't think these two recurring lines warrant their own
			# "setframetodata" method.

	def set_sortstate(self, to):
		'''Sets the column's sortstate, causing it to update on the UI.'''
		if self.assignedframe is not None:
			if self.cnf["sort"]:
				self.mfl.frames[self.assignedframe][3].configure(text = SORTSYM[to])
		self.sortstate = to

class MultiframeList(ttk.Frame):
	"""
	Instantiates a multiframe tkinter based list
	
	Arguments:
	master - parent object, should be tkinter root or a tkinter widget

	keyword arguments:
	inicolumns <List<Dict>>: The columns here will be created and displayed
		upon instantiation.
		The dicts supplied should take form of Column constructor kwargs. See
		the multiframe_list.Column class for a list of acceptable kwargs.

	rightclickbtn <Str>: The button that will trigger the MultiframeRightclick
		virtual event. It is 3 (standard) on windows, this may differ from
		platform to platform.

	A terrible idea of a feature:
		The MultiframeList will grab the currently active theme (as well as
		listen to the <<ThemeChanged>> event) and attempt to apply style
		configuration options in the current theme's style called
		"MultiframeList.Listbox" to its listboxes, as those are not available
		as ttk variants.
		Further styling options are available to the column title and sort
		indicator labels: "MultiframeListTitle.TLabel" and
		"MultiframeListSortInd.TLabel"
	The list broadcasts the Virtual event "<<MultiframeSelect>>" to its parent
		whenever something is selected.
	The list broadcasts the Virtual event "<<MultiframeRightclick>>" to its
		parent whenever a right click is performed or the context menu button
		is pressed.
	"""
	_DEFAULT_LISTBOX_CONFIG = {
		"activestyle": "underline",
		"background": "#FFFFFF",
		"borderwidth": 1,
		"cursor": "",
		"disabledforeground": "#6D6D6D",
		"font": "TkDefaultFont",
		"foreground": "#000000",
		"highlightbackground": "#FFFFFF",
		"highlightcolor": "#B4B4B4",
		"highlightthickness": 1,
		"justify": "left",
		"relief": "sunken",
		"selectbackground": "#3399FF",
		"selectborderwidth": 0,
		"selectforeground": "#FFFFFF",
	}

	def __init__(self, master, **options):

		super().__init__(master, takefocus = True)

		self.master = master

		self.bind("<Down>", lambda _: self.__setindex_arr(1))
		self.bind("<Up>", lambda _: self.__setindex_arr(-1))
		self.bind("<KeyPress-App>", self.__callback_menu_button)

		self.curcellx = None
		self.curcelly = None
		self.coordx = None
		self.coordy = None

		self.scrollbar = ttk.Scrollbar(self, command = self.__scrollallbar)
		self.framecontainer = ttk.Frame(self)
		self.framecontainer.grid_rowconfigure(0, weight = 1)
		self.framecontainer.grid_columnconfigure(tk.ALL, weight = 1)

		self.frames = [] # Each frame contains interface elements for display.
		self.columns = [] # Columns will provide data storage capability as
		#well as some metadata.

		self.length = 0

		self.options = _DEF_OPT.copy()
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
			# colopt["iniframe"] = index
			self.columns.append(Column(self, **colopt))
			self.columns[-1].setdisplay(index)

		self.ttkhookstyle = ttk.Style()
		self.bind("<<ThemeChanged>>", self.__themeupdate)
		self.__themeupdate(None)

		self.scrollbar.pack(fill = tk.Y, expand = 0, side = tk.RIGHT)
		self.framecontainer.pack(expand = 1, fill = tk.BOTH, side = tk.RIGHT)

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
			rcb = self.options["rightclickbtn"]
			self.frames[curindex].append(ttk.Frame(self.framecontainer))#, width = 0))

			self.frames[curindex][0].grid_rowconfigure(1, weight = 1)
			self.frames[curindex][0].grid_columnconfigure(0, weight = 1)

			self.frames[curindex].append(tk.Listbox(self.frames[curindex][0],
				exportselection = False, takefocus = False))
			self.frames[curindex].append(ttk.Label(self.frames[curindex][0],
				text = BLANK, anchor = tk.W, style = "MultiframeListTitle.TLabel"))
			self.frames[curindex].append(ttk.Label(self.frames[curindex][0],
				text = BLANK, anchor = tk.W, style = "MultiframeListSortInd.TLabel"))
			instance_name = self.frames[curindex][1].bindtags()[0]
			# REMOVE Listbox bindings from listboxes
			self.frames[curindex][1].bindtags((instance_name, '.', 'all'))
			def _handler_m1(event, self = self, button = 1, frameindex = curindex):
				return self.__setindex_lb(event, button, frameindex)
			def _handler_m3(event, self = self, button = rcb, frameindex = curindex):
				return self.__setindex_lb(event, button, frameindex)

			self.frames[curindex][1].bind("<Button-" + rcb + ">", _handler_m3)
			self.frames[curindex][1].bind("<Button-1>", _handler_m1)
			self.tk.eval("""if {{[tk windowingsystem] eq "aqua"}} {{
    bind {w} <MouseWheel> {{
        %W yview scroll [expr {{- (%D)}}] units
    }}
    bind {w} <Option-MouseWheel> {{
        %W yview scroll [expr {{-10 * (%D)}}] units
    }}
    bind {w} <Shift-MouseWheel> {{
        %W xview scroll [expr {{- (%D)}}] units
    }}
    bind {w} <Shift-Option-MouseWheel> {{
        %W xview scroll [expr {{-10 * (%D)}}] units
    }}
}} else {{
    bind {w} <MouseWheel> {{
        %W yview scroll [expr {{- (%D / 120) * 4}}] units
    }}
    bind {w} <Shift-MouseWheel> {{
        %W xview scroll [expr {{- (%D / 120) * 4}}] units
    }}
}}

if {{"x11" eq [tk windowingsystem]}} {{
    bind {w} <4> {{
	if {{!$tk_strictMotif}} {{
	    %W yview scroll -5 units
	}}
    }}
    bind {w} <Shift-4> {{
	if {{!$tk_strictMotif}} {{
	    %W xview scroll -5 units
	}}
    }}
    bind {w} <5> {{
	if {{!$tk_strictMotif}} {{
	    %W yview scroll 5 units
	}}
    }}
    bind {w} <Shift-5> {{
	if {{!$tk_strictMotif}} {{
	    %W xview scroll 5 units
	}}
    }}
}}""".format(w = self.frames[curindex][1]._w)) # *vomits*

			self.frames[curindex][1].config(yscrollcommand = self.__scrollalllistbox)
			self.frames[curindex][1].insert(tk.END, *(BLANK for _ in range(self.length)))

			self.frames[curindex][3].grid(row = 0, column = 1, sticky = "news")		#grid sort_indicator
			self.frames[curindex][2].grid(row = 0, column = 0, sticky = "news")		#grid label
			self.frames[curindex][1].grid(row = 1, column = 0, sticky = "news",		#grid listbox
				columnspan = 2)
			self.frames[curindex][0].grid(row = 0, column = curindex, sticky = "news")	#grid frame

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
		# old frame is now column-less, so the list itself has to revert it
		if old_frame is None:
			return
		old_frameobj = self.frames[old_frame]
		old_frameobj[3].configure(text = BLANK)
		old_frameobj[2].configure(text = BLANK)
		old_frameobj[2].unbind("<Button-1>")
		old_frameobj[1].delete(0, tk.END)
		old_frameobj[1].insert(0, *[BLANK
			for _ in range(self.length)])
		self.framecontainer.grid_columnconfigure(old_frame,
			weight = 1, minsize = 0)
		old_frameobj[1].configure(width = _DEF_LISTBOX_WIDTH)

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

	def format(self, targetcols = None, indices = None):
		'''Format the entire list based on the formatter functions in columns.
		Optionally, a list of columns to be formatted can be supplied by their
		id, which will leave all non-mentioned columns alone.
		Also, if index is specified, only the indices included in that list
		will be formatted.

		! Call this after all input has been performed !'''
		if indices is not None:
			for i in indices:
				tmp = self.length - 1
				if i > tmp:
					raise ValueError("Index is out of range.")
		if targetcols is None:
			for col in self.columns:
				col.format(exclusively = indices)
		else:
			for col_id in targetcols:
				self._get_col_by_id(col_id).format(exclusively = indices)
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
		'''Returns the absolute screen coordinates the last user interaction
		was made at as a tuple. May consist of int or None.
		This method can be used to get coordinates to open a popup window at.
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
			if self.curcellx is not None:
				if self.curcellx >= i:
					self.curcellx = i - 1
			self.frames[i][0].destroy()
			self.frames.pop(i)

	def removerow(self, index):
		'''Will delete the entire row at index, visible or not visible.'''
		if index > (self.length - 1):
			raise IndexError("Index to remove out of range.")
		for col in self.columns:
			col.data_pop(index)
		self.length -= 1
		self.__lengthmod_callback()

	def setcell(self, col_to_mod, y, data):
		'''Sets the cell in col_to_mod at y to data.'''
		col = self._get_col_by_id(col_to_mod)
		if y > (self.length - 1):
			raise IndexError("Cell index does not exist.")
		col.data_pop(y)
		col.data_insert(data, y)

	#==DATA MODIFICATION, ALL==

	def insertrow(self, data, insindex = None):
		'''Data should be supplied in the shape of a dict where a key is a
		column's id and the corresponding value is the element that should
		be appended to the column.
		If insindex is not specified, data will be appended, else inserted
			at the given position.
		'''
		for col in self.columns:
			if col.col_id in data:
				col.data_insert(data.pop(col.col_id), insindex)
			else:
				col.data_insert(BLANK, insindex)
		self.length += 1
		self.__lengthmod_callback()

	def setdata(self, data, reset_sortstate = True):
		'''Data has to be supplied as a dict where:
		key is a column id and value is a list of values the column targeted by
		key should be set to. If the lists are of differing lengths, an
		exception will be raised.
		The function takes a reset_sortstate parameter, that, when set to false,
		will not reset the sortstate on the columns.
		'''
		if not data:
			self.clear(); return
		ln = len(data[next(iter(data))])
		if reset_sortstate:
			for col in self.columns:
				col.set_sortstate(2)
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
		for col in self.columns:
			col.set_sortstate(2)
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
		new_sortstate = abs(int(sortstate) - 1)
		if new_sortstate:
			rev = True
		call_col.set_sortstate(new_sortstate)
		for col in self.getcolumns(): # reset sortstate of other columns
			if col != caller_id:
				self._get_col_by_id(col).set_sortstate(2)
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
		self.setdata(newdat, reset_sortstate = False)
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
		r = sorted([i for i in self.columns if i.assignedframe is not None],
			key = lambda col: col.assignedframe)
		return r

	def __callback_menu_button(self, _):
		'''User has pressed the menu button.
		This generates a <<MultiframeRightclick>> event and modifies
		self.coord[xy] to the currently selected index.
		'''
		if not self.frames:
			return
		if self.curcelly is None:
			return
		if self.curcellx is None:
			local_curcellx = 0
		else:
			local_curcellx = self.curcellx
		vtup = self.frames[0][1].yview()
		tmp_x = self.frames[local_curcellx][0].winfo_rootx() + 5
		tmp_y = ENTRYHEIGHT * (self.curcelly - (self.length * vtup[0])) + 20 + \
			self.frames[local_curcellx][0].winfo_rooty()
		tmp_x = int(round(tmp_x))
		tmp_y = int(round(tmp_y))
		if tmp_y < 0:
			tmp_y = 0
		tmp_y += 10
		self.coordx = tmp_x
		self.coordy = tmp_y
		self.event_generate("<<MultiframeRightclick>>", when = "tail")

	def __getemptyframes(self):
		'''Returns the indexes of all frames that are not assigned a column.'''
		existingframes = list(range(len(self.frames)))
		assignedframes = [col.assignedframe for col in self.columns]
		return [f for f in existingframes if not f in assignedframes]

	def __relay_focus(self, *_):
		'''Called by frames when they are clicked so focus is given to the
		MultiframeList Frame itself.
		'''
		self.focus()

	def __setindex_lb(self, event, button, frameindex):
		'''Called by listboxes; GENERATES EVENT, sets the current index.'''
		self.__relay_focus()
		if self.length == 0:
			return
		offset = event.widget.yview()[0] * self.length
		tosel = int(floor((event.y + - BORDERWIDTH) / ENTRYHEIGHT) + offset)
		if tosel < 0: return
		if tosel >= self.length: tosel = self.length - 1
		if tosel != self.curcelly:
			event.widget.selection_clear(0, tk.END)
			event.widget.selection_set(tosel)
		self.curcelly = tosel
		self.curcellx = frameindex
		self.__selectionmod_callback()
		self.coordx = self.frames[self.curcellx][0].winfo_rootx() + event.x
		self.coordy = self.frames[self.curcellx][0].winfo_rooty() + 20 + event.y
		self.master.event_generate("<<MultiframeSelect>>", when = "tail")
		if button == self.options["rightclickbtn"]:
			self.master.event_generate("<<MultiframeRightclick>>",
				when = "tail")

	def __setindex_arr(self, direction):
		'''Executed when the MultiframeList receives <Up> and <Down> events,
		triggered by the user pressing the arrow keys.
		'''
		if self.curcelly == None:
			tosel = 0
		else:
			tosel = self.curcelly
			tosel += direction
		if tosel < 0 or tosel > self.length - 1:
			return
		self.curcelly = tosel
		self.__selectionmod_callback()
		for i in self.frames:
			i[1].see(self.curcelly)
		self.master.event_generate("<<MultiframeSelect>>", when = "tail")

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
		occur via self.curcell()
		'''
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
		'''Called from event binding when the current theme changes.
		Changes Listbox look, as those are not available as ttk variants.
		'''
		conf = self._DEFAULT_LISTBOX_CONFIG.copy()
		for style in (".", "MultiframeList.Listbox", ):
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
	from random import randint, sample
	def test():
		def adddata():
			mf.insertrow({col_id: randint(0, 100)
				for col_id in mf.getcolumns()})
			mf.format()

		def add1col():
			if "newcol" in mf.getcolumns():
				if mf.getcolumns()["newcol"] != 6:
					print("Please return that column to frame 6, it's where it feels at home.")
					return
				mf.removecolumn("newcol")
			else:
				mf.addcolumns({"col_id":"newcol", "name":"added @ runtime; wide.",
				"w_width": 35, "minsize":30, "weight":3})
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

		def swap(first, second):
			_tmp = mf.getcolumns()
			f_frm = _tmp[first]
			s_frm = _tmp[second]
			mf.assigncolumn(first, None)
			mf.assigncolumn(second, f_frm)
			mf.assigncolumn(first, s_frm)
			
		def swap01():
			c_a = 1
			c_b = 0
			if mf.getcolumns()[0] == 0:
				c_a = 0
				c_b = 1
			swap(c_a, c_b)

		def swaprand():
			l = mf.getcolumns().keys()
			s_res = sample(l, 2)
			print("Swapping {}".format(" with ".join([str(i) for i in s_res])))
			swap(*s_res)

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
				{"text":"swp01", "command":swap01},
				{"text":"swprnd", "command":swaprand}, )
		root = tk.Tk()
		mf = MultiframeList(root, inicolumns=(
		{"name":"smol col", "w_width":10},
		{"name":"Sortercol", "col_id":"sorter", },
		{"name":"sickocol", "sort":True, "col_id":"sickocol"},
		{"name":"-100", "col_id":"sub_col", "formatter":lambda n: n-100},
		{"name":"Wide col", "w_width":30},
		{"name":"unconf name","col_id":"cnfcl"} ),
		listboxstyle = {"background":"#4E4E4E", "foreground":"#EEEEEE"})
		mf.configcolumn("sickocol", formatter = priceconv)
		mf.configcolumn("sorter", sort = True)
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
