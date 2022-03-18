
import tkinter as tk

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
	}

	def __init__(self, parent, styleobj, *args, **kwargs):
		"""
		styleobj <tkinter.ttk.Style>: Style object used to access changing
			style database.

		This widget can be used in a context guard where it will be
		configured to tk.NORMAL while in the guard, then back to
		tk.DISABLED.

		Any other args and kwargs will be routed to the Text.
		"""
		self.styleobj = styleobj
		super().__init__(parent, *args, **kwargs)
		self.bind("<<ThemeChanged>>", self.__themeupdate)
		self.__themeupdate(None)

	def __enter__(self):
		self.configure(state = tk.NORMAL)

	def __exit__(self, *_):
		self.configure(state = tk.DISABLED)

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
