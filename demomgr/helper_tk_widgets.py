"""
Classes that add functionality to some tkinter widgets or combinations of
multiple widgets with the goal to collapse interface setup code.
"""

import tkinter as tk
from tkinter import ttk

def crunch_window_path(path):
	"""
	Returns the input window name void of all periods and exclamation points.
	"""
	return path.replace("!", "").replace(".", "")

def prepend_bindtags(widget, elem):
	"""
	Prepends elem to the bindtags of widget
	"""
	tmp = [elem]
	tmp.extend(widget.bindtags())
	widget.bindtags(tuple(tmp))

# Format using w as targeted bindtag, tw as widget to scroll.
scrollcommand = """
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

class TtkText(tk.Text):
	"""
	Text widget that will listen to the <<ThemeChanged>> event and
	attempts to apply configuration options to itself. The style name
	read from is "TtkHook.Text".

	__init__() Reroutes all args to tkinter.Text except for "styleobj"
	"""
	_DEFAULT_CONFIG = {
		"autoseparators": 1,
		"background": "#FFFFFF",
		"blockcursor": 0,
		"borderwidth": 1,
		"cursor": "xterm",
		"font": "TkFixedFont",
		"foreground": "#000000",
		"highlightbackground": "#FFFFFF",
		"highlightcolor": "#B4B4B4",
		"highlightthickness": 0,
		"inactiveselectbackground": "",
		"insertbackground": "#000000",
		"insertofftime": 300,
		"insertontime": 600,
		"insertwidth": 2,
		"relief": "sunken",
		"selectbackground": "#3366FF",
		"selectforeground": "#FFFFFF",
		"wrap": "word",
	}

	def __init__(self, parent, styleobj, *args, **kwargs):
		"""
		styleobj <tkinter.ttk.Style>: Style object used to access changing
			style database.

		Any other args and kwargs will be routed to the Text.
		"""
		self.styleobj = styleobj
		super().__init__(parent, *args, **kwargs)
		self.bind("<<ThemeChanged>>", self.__themeupdate)
		self.__themeupdate(None)

	def __themeupdate(self, _):
		"""Called from event binding. Changes look"""
		conf = self._DEFAULT_CONFIG.copy()
		for style in (".", "TtkHook.Text", ):
			cur_style_cnf = self.styleobj.configure(style)
			if cur_style_cnf is not None:
				conf.update(cur_style_cnf)
		ok_values = self.configure()
		conf = {k: v for k, v in conf.items() if k in ok_values}
		self.configure(**conf)

class TtkCanvas(tk.Canvas):
	"""
	A subclass widget of tkinter.Canvas that will listen to the
	<<ThemeChanged>> event and that attempts to apply configuration
	options to itself. The style name read from is "TtkHook.Canvas".

	__init__() Reroutes all args to tkinter.Canvas except for "styleobj"
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

# Thanks: https://stackoverflow.com/questions/3085696/
# adding-a-scrollbar-to-a-group-of-widgets-in-tkinter
class KeyValueDisplay(ttk.Frame):
	"""
	Frame wrapped in a ttkCanvas wrapped in a Frame in order to
	display parameters (keys) and a value associated with them as a
	combination of labels and readonly entries.
	"""
	def __init__(self, parent, styleobj, inikeys = None, *args, **kwargs):
		"""
		parent: Parent tk widget
		styleobj: <tkinter.ttk.Style> : Style object to access styling
			database.
		inikeys: <List|Tuple<Str>> : Keys that should be added to the widget
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

		self.canv_scrollbar.pack(side = tk.RIGHT, fill = tk.Y, expand = 1)
		self.canvas.pack(side = tk.LEFT, fill = tk.BOTH, expand = 1)
		self.innerframe_id = self.canvas.create_window((0, 0),
			window = self.innerframe, anchor = tk.NW, tags = "self.innerframe")

		self.tk.eval(scrollcommand.format(w = f"scroll{crunch_window_path(self._w)}",
			tw = self.canvas._w))
		prepend_bindtags(self.canvas, f"scroll{crunch_window_path(self._w)}")
		prepend_bindtags(self.canv_scrollbar, f"scroll{crunch_window_path(self._w)}")

		self.canvas.bind("<Configure>", self._canvas_cnf_callback)

		self.innerframe.bind("<Configure>", self._frame_cnf_callback)
		self.innerframe.grid_columnconfigure((0, 1), weight = 1, pad = 50)

		self.length = 0
		self.registered_keys = {}

		if inikeys is not None:
			for i in inikeys:
				self.add_key_raw(i)

	def _frame_cnf_callback(self, _):
		self.canvas.configure(scrollregion = self.canvas.bbox(tk.ALL))

	def _canvas_cnf_callback(self, evt):
		if self.canvas.winfo_height() > self.innerframe.winfo_reqheight():
			self.canvas.itemconfigure(self.innerframe_id, width = evt.width,
				height = self.canvas.winfo_height())
		else:
			self.canvas.itemconfigure(self.innerframe_id, width = evt.width)

	def add_key_raw(self, key):
		"""
		Add a label and entry to the widget, registering it internally as well.
		"""
		if key in self.registered_keys:
			raise ValueError(f"Name {key} already in use.")

		label = ttk.Label(self.innerframe, text = key)
		entry = ttk.Entry(self.innerframe, state = "readonly")

		self.registered_keys[key] = (label, entry)

		for w in (label, entry):
			prepend_bindtags(w, "scroll{}".format(crunch_window_path(self._w)))

		label.grid(column = 0, row = self.length, sticky = "news")
		entry.grid(column = 1, row = self.length, sticky = "news")

		self.length += 1

	def clear(self):
		"""
		Clears every value entry.
		"""
		for pair_widgets in self.registered_keys.values():
			pair_widgets[1].configure(state = tk.NORMAL)
			pair_widgets[1].delete(0, tk.END)
			pair_widgets[1].configure(state = "readonly")

	def set_value(self, key, value):
		"""
		Set the value of key to value.
		"""
		if key not in self.registered_keys:
			raise KeyError(f"Key {key} not found.")
		self.registered_keys[key][1].configure(state = tk.NORMAL)
		self.registered_keys[key][1].delete(0, tk.END)
		self.registered_keys[key][1].insert(0, value)
		self.registered_keys[key][1].configure(state = "readonly")

if __name__ == "__main__":
	root = tk.Tk()
	kvd = KeyValueDisplay(root, ttk.Style())
	kvd.pack(side="top", fill="both", expand=True)

	for _ in range(50):
		kvd.add_key_raw(f"Key{_}")
	kvd.change_value("Key4", "lol")

	root.mainloop()
