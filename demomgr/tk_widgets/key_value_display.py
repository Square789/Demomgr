"""
KeyValueDisplay, a collection of labels and entry pairs that functions like
a budget MultiframeList.
"""

import tkinter as tk
from tkinter import ttk

# Format using w as targeted bindtag, tw as widget to scroll.
SCROLLCOMMAND = """
if {{[tk windowingsystem] eq "aqua"}} {{
	bind {w} <MouseWheel> {{
		{tw} yview scroll [expr {{- (%D)}}] units
	}}
	bind {w} <Option-MouseWheel> {{
		{tw} yview scroll [expr {{-5 * (%D)}}] units
	}}
	bind {w} <Shift-MouseWheel> {{
		{tw} xview scroll [expr {{- (%D)}}] units
	}}
	bind {w} <Shift-Option-MouseWheel> {{
		{tw} xview scroll [expr {{-5 * (%D)}}] units
	}}
}} else {{
	bind {w} <MouseWheel> {{
		{tw} yview scroll [expr {{- (%D / 120) * 2}}] units
	}}
	bind {w} <Shift-MouseWheel> {{
		{tw} xview scroll [expr {{- (%D / 120) * 2}}] units
	}}
}}
if {{"x11" eq [tk windowingsystem]}} {{
	bind {w} <4> {{
	if {{!$tk_strictMotif}} {{
		{tw} yview scroll -2 units
	}}
	}}
	bind {w} <Shift-4> {{
	if {{!$tk_strictMotif}} {{
		{tw} xview scroll -2 units
	}}
	}}
	bind {w} <5> {{
	if {{!$tk_strictMotif}} {{
		{tw} yview scroll 2 units
	}}
	}}
	bind {w} <Shift-5> {{
	if {{!$tk_strictMotif}} {{
		{tw} xview scroll 2 units
	}}
	}}
}}
"""

def crunch_window_path(path):
	"""
	Returns the input window name void of all periods and exclamation points.
	"""
	return path.replace("!", "").replace(".", "")

def prepend_bindtags(widget, elem):
	"""
	Prepends elem to the bindtags of widget
	"""
	widget.bindtags((elem, *widget.bindtags()))

class TtkCanvas(tk.Canvas):
	"""
	A subclass widget of tkinter.Canvas that will listen to the
	<<ThemeChanged>> event and that attempts to apply configuration
	options to itself. The style name read from is "TtkHook.Canvas".

	__init__() Reroutes all args and kwargs to tkinter.Canvas except
		for "styleobj"
	"""
	_DEFAULT_CONFIG = {
		"background": "#FFFFFF",
		"borderwidth": 0,
		"cursor": "",
		"highlightbackground": "#FFFFFF",
		"highlightcolor": "#B4B4B4",
		"highlightthickness": 2,
		"insertbackground": "#000000",
		"insertofftime": 300,
		"insertontime": 600,
		"insertwidth": 2,
		"relief": "flat",
		"selectbackground": "#3366FF",
		"selectborderwidth": 1,
		"selectforeground": "#FFFFFF",
	}

	def __init__(self, parent, styleobj, *args, **kwargs):
		"""
		styleobj <tkinter.ttk.Style>: Style object used to access changing
			style database.

		Any other args and kwargs will be routed to the Canvas.
		"""
		self.styleobj = styleobj
		super().__init__(parent, *args, **kwargs)
		self.bind("<<ThemeChanged>>", self.__themeupdate)
		self.__themeupdate(None)

	def __themeupdate(self, _):
		"""Called from event binding. Changes look."""
		conf = self._DEFAULT_CONFIG.copy()
		for style in (".", "TtkHook.Canvas"):
			cur_style_cnf = self.styleobj.configure(style)
			if cur_style_cnf is not None:
				conf.update(cur_style_cnf)
		ok_values = self.configure()
		conf = {k: v for k, v in conf.items() if k in ok_values}
		self.configure(**conf)


class _KVDLine():
	"""
	Class to hold attributes of the line of a KeyValueDisplay.
	Should only be used internally.
	"""
	class Config():
		__slots__ = ("name", "formatter")
		def __init__(self, name = "", formatter = None):
			self.name = name
			self.formatter = formatter

	def __init__(self, kvd, id_, **kwargs):
		"""
		Initialize a KVD line and display its widgets in the parent.

		Required arguments:
		kvd: <KeyValueDisplay> : Parent KVD; Used to access innerframe as well as
			window path name.
		id_: <Str> : Id to reference the line by.

		Optional arguments:
		name: <Str> : Name to display on the label.
		formatter: <func> : Function to display other string
			than what the data is.
		"""
		self.id = id_
		self._truevalue = 0

		for k in kwargs:
			if k not in self.Config.__slots__:
				raise ValueError(f"Unrecognized option {k!r}")
		self.cfg = self.Config(**kwargs)

		self.label = ttk.Label(kvd.innerframe, text = self.cfg.name)
		self.entry = ttk.Entry(kvd.innerframe, state = "readonly")

		for w in (self.label, self.entry):
			prepend_bindtags(w, f"scroll{format(crunch_window_path(kvd._w))}")

		self.label.grid(column = 0, row = kvd.length, sticky = "w")
		self.entry.grid(column = 1, row = kvd.length, sticky = "ew")

	def clear(self):
		"""
		Wipes the entry.
		"""
		self.entry.configure(state = tk.NORMAL)
		self.entry.delete(0, tk.END)
		self.entry.configure(state = "readonly")

	def set_value(self, value):
		"""
		Sets the value of the entry to `value`, applying formatter if it is specified.
		"""
		self._truevalue = value
		self.entry.configure(state = tk.NORMAL)
		self.entry.delete(0, tk.END)
		if self.cfg.formatter is not None:
			self.entry.insert(0, self.cfg.formatter(self._truevalue))
		else:
			self.entry.insert(0, self._truevalue)
		self.entry.configure(state = "readonly")


# Thanks: https://stackoverflow.com/questions/3085696/
# adding-a-scrollbar-to-a-group-of-widgets-in-tkinter
class KeyValueDisplay(ttk.Frame):
	"""
	Frame wrapped in a ttkCanvas wrapped in a Frame in order to
	display parameters (keys) and a value associated with them as a
	combination of labels and readonly entries.
	"""
	def __init__(self, parent, styleobj, inipairs = None, *args, **kwargs):
		"""
		parent: Parent tk widget
		styleobj: <tkinter.ttk.Style> : Style object to access styling
			database.
		inipairs: <List|Dict> : Keys that should be added to the widget
			initially. Default is None.

		Any other args and kwargs will be passed to the underlying Canvas.
		"""
		super().__init__(parent)
		self.canvas = TtkCanvas(self, styleobj, *args, **kwargs)
		self.innerframe = ttk.Frame(self.canvas)
		self.canv_scrollbar = ttk.Scrollbar(self, orient = tk.VERTICAL,
			command = self.canvas.yview)

		self.canvas.configure(yscrollcommand = self.canv_scrollbar.set)
		self.canvas.grid_columnconfigure(0, weight = 1)
		self.canvas.grid_rowconfigure(0, weight = 1)

		self.canv_scrollbar.pack(side = tk.RIGHT, fill = tk.Y, expand = 0)
		self.canvas.pack(side = tk.LEFT, fill = tk.BOTH, expand = 1)
		self.innerframe_id = self.canvas.create_window((0, 0),
			window = self.innerframe, anchor = tk.NW, tags = "self.innerframe")

		self.canvas.bind("<Configure>", self._canvas_cnf_callback)

		self.innerframe.bind("<Configure>", self._frame_cnf_callback)
		self.innerframe.grid_columnconfigure((0, 1), weight = 1, pad = 50)

		self.tk.eval(SCROLLCOMMAND.format(w = f"scroll{crunch_window_path(self._w)}",
			tw = self.canvas._w))
		prepend_bindtags(self.innerframe, f"scroll{crunch_window_path(self._w)}")
		prepend_bindtags(self.canv_scrollbar, f"scroll{crunch_window_path(self._w)}")

		self.length = 0
		self._registered_lines = {}

		if inipairs is not None:
			for kwd in inipairs:
				self.add_key(**kwd)

	def _frame_cnf_callback(self, _):
		self.canvas.configure(scrollregion = self.canvas.bbox(tk.ALL))

	def _canvas_cnf_callback(self, evt):
		if self.canvas.winfo_height() > self.innerframe.winfo_reqheight():
			self.canvas.itemconfigure(self.innerframe_id, width = evt.width,
				height = self.canvas.winfo_height())
		else:
			self.canvas.itemconfigure(self.innerframe_id, width = evt.width)

	def add_key(self, **kwargs):
		"""
		Add a label and entry to the widget, checking for duplicate ids
		and registering it internally.
		"""
		if "id_" in kwargs:
			id_ = kwargs.pop("id_")
			if id_ in self._registered_lines:
				raise ValueError(f"Id \"{id_}\" already in use.")
		else:
			id_ = 0
			while id_ in self._registered_lines:
				id_ += 1

		self._registered_lines[id_] = _KVDLine(self, id_, **kwargs)
		self.length += 1

	def clear(self):
		"""
		Clears every line.
		"""
		for line in self._registered_lines.values():
			line.clear()

	def get_value(self, key):
		"""
		Retrieve the actual non-formatted value currently stored in key.
		"""
		return self._get_line_by_id(key)._truevalue

	def set_value(self, key, value):
		"""
		Set the value of key to value.
		"""
		self._get_line_by_id(key).set_value(value)

	def _get_line_by_id(self, id_):
		"""
		Returns line by id. Meant for internal use.
		"""
		if id_ in self._registered_lines:
			return self._registered_lines[id_]
		else:
			raise KeyError(f"Key {id_} not found.")
