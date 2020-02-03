'''Classes that add functionality to some tkinter widgets or combinations of
multiple widgets with the goal to collapse interface setup code.'''

from tkinter import (Text, Canvas)
from tkinter.ttk import Frame, Entry

class TtkText(Text):
	'''Text widget that will listen to the <<ThemeChanged>> event and
		attempts to apply configuration options to itself. The style name
		read from is "TtkHook.Text".

		__init__() Reroutes all args to tkinter.Text except for "styleobj"
	'''
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
		'''styleobj <tkinter.ttk.Style>: Style object used to access changing
		style database.
		'''
		self.styleobj = styleobj
		super().__init__(parent, *args, **kwargs)
		self.bind("<<ThemeChanged>>", self.__themeupdate)
		self.__themeupdate(None)

	def __themeupdate(self, _):
		'''Called from event binding. Changes look.'''
		conf = self._DEFAULT_CONFIG.copy()
		for style in (".", "TtkHook.Text", ):
			cur_style_cnf = self.styleobj.configure(style)
			if cur_style_cnf is not None:
				conf.update(cur_style_cnf)
		ok_values = self.configure()
		conf = {k: v for k, v in conf.items() if k in ok_values}
		self.configure(**conf)

# class TtkCanvas(Canvas):
	# '''A subclass widget of tkinter.Canvas that will listen to the
	# <<ThemeChanged>> event and that attempts to apply configuration
	# options to itself. The style name read from is "TtkHook.Canvas".

		# __init__() Reroutes all args to tkinter.Text except for "styleobj"
	# '''
	# _DEFAULT_CONFIG = {
		# "background": "#FFFFFF",
		# "borderwidth": 0,
		# "cursor": "",
		# "highlightbackground": "#FFFFFF",
		# "highlightcolor": "#B4B4B4",
		# "highlightthickness": 2,
		# "insertbackground": "SystemButtonText",
		# "insertofftime": 300,
		# "insertontime": 600,
		# "insertwidth": 2,
		# "relief": "flat",
		# "selectbackground": "SystemHighlight",
		# "selectborderwidth": 1,
		# "selectforeground": "#FFFFFF",
	# }

	# def __init__(self, parent, styleobj, *args, **kwargs):
		# '''styleobj <tkinter.ttk.Style>: Style object used to access changing
		# style database.
		# '''
		# self.styleobj = styleobj
		# super().__init__(parent, *args, **kwargs)
		# self.bind("<<ThemeChanged>>", self.__themeupdate)
		# self.__themeupdate(None)

	# def __themeupdate(self, _):
		# '''Called from event binding. Changes look.'''
		# conf = self._DEFAULT_CONFIG.copy()
		# for style in (".", "TtkHook.Canvas"):
			# cur_style_cnf = self.styleobj.configure(style)
			# if cur_style_cnf is not None:
				# conf.update(cur_style_cnf)
		# ok_values = self.configure()
		# conf = {k: v for k, v in conf.items() if k in ok_values}
		# self.configure(**conf)

# class MultiLabel(Frame):
	# '''A widget that packs a lines of labels into a Frame and provides some
	# methods to manipulate them. Budget version of the multiframe_list,
	# if you will.
	# '''
	# def __init__(self, parent, inilabels = None, *args, **kwargs):
		# if inilabels is None:
			# inilabels = ()

		# super().__init__(self, parent, *args, **kwargs)

		# self.labels = []
		# for lblcnf in inilabels:
			# self.addlabel(**lblcnf)

	# def addlabel(self, **opt):
		# pass
	# def removelabel(self, index):
		# pass
	# def modlabel(self, index, **opt):
		# pass
