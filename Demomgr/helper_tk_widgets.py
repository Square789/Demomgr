'''Classes that add functionality to some tkinter widgets or combinations of
multiple widgets with the goal to collapse interface setup code.'''

from tkinter import Text
from tkinter.ttk import Frame, Entry

popupentry_options = {
}

class TtkText(Text):
	def __init__(self, parent, styleobj, *args, **kwargs):
		'''Text widget that will listen to the <<ThemeChanged>> event and
		attempts to apply configuration options to itself. The style name
		read from is "TtkHook.Text".

		__init__() Reroutes all args to tkinter.Text except for the second
		argument:
		styleobj <tkinter.ttk.Style>: Style object used to access changing
		style database.
		'''
		self.styleobj = styleobj
		super().__init__(parent, *args, **kwargs)
		self.bind("<<ThemeChanged>>", self.__themeupdate)
		self.__themeupdate(None)

	def __themeupdate(self, _):
		'''Called from event binding. Changes look.'''
		conf = {}
		for style in (".", "TtkHook.Text"):
			cur_style_cnf = self.styleobj.configure(style)
			if cur_style_cnf is not None:
				conf.update(cur_style_cnf)
		ok_values = self.configure()
		conf = {k: v for k, v in conf.items() if k in ok_values}
		self.configure(**conf)

#class TtkPopupEntry(Entry):
#	def __init__(self, parent, popupdef = None, *args, **kwargs):
#		super().__init__(self, parent, *args, **kwargs)

#class MultiLabel(Frame):
#	'''A widget that packs a lines of labels into a Frame and provides some
#	useful methods to manipulate them. Budget version of the multiframe_list,
#	if you will.
#	'''
#	def __init__(self, parent, *args, **kwargs):
#		super().__init__(self, parent, *args, **kwargs)
