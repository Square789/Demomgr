import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid

from demomgr.dialogues._base import BaseDialog

from demomgr import constants as CNST
from demomgr.helper_tk_widgets import TtkText
from demomgr.helpers import (frmd_label, convertunit)

_TK_VARTYPES = {
	"str": tk.StringVar,
	"int": tk.IntVar,
	"bool": tk.BooleanVar,
	"double": tk.DoubleVar,
}

class Settings(BaseDialog):
	'''Settings dialog that offers a bunch of configuration options.'''
	def __init__(self, parent, cfg):
		'''Args:
		parent: Tkinter widget that is the parent of this dialog.
		cfg: Program configuration.
		'''
		self.cfg = cfg

		self._create_tk_var("int", "datagrabmode_var", cfg["datagrabmode"])
		self._create_tk_var("bool", "preview_var", cfg["previewdemos"])
		self._create_tk_var("str", "steampath_var", cfg["steampath"])
		self._create_tk_var("str", "hlaepath_var", cfg["hlaepath"])
		self._create_tk_var("str", "ui_style_var", cfg["ui_theme"])
		self._create_tk_var("bool", "lazyreload_var", cfg["lazyreload"])

		self.blockszvals = {convertunit(i, "B"): i
			for i in [2**pw for pw in range(12, 28)]}
		self.result = None

		super().__init__(parent, "Settings")

	def body(self, master):
		'''UI setup.'''
		master.grid_columnconfigure((0, 1), weight = 1)

		display_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Display"))
		display_labelframe.grid_columnconfigure(0, weight = 1)
		ttk.Checkbutton(display_labelframe, variable = self.preview_var,
			text = "Preview demos?", style = "Contained.TCheckbutton").grid(
			sticky = "w", ipadx = 4) # Preview
		lazyreload_btn = ttk.Checkbutton(display_labelframe,
			variable = self.lazyreload_var, text = "Lazy reload of main demo view",
			style = "Contained.TCheckbutton")
		lazyreload_txt = ttk.Label(display_labelframe,
			text = "Will not reload the entire directory\non minor" \
				" changes such as bookmark modification.",
			justify = tk.LEFT, style = "Contained.TLabel")
		lazyreload_btn.grid(sticky = "w", ipadx = 4, pady = (2, 0))
		lazyreload_txt.grid(sticky = "w", padx = (8, 0)) # Lazy reload
		ui_style_labelframe = ttk.Labelframe(display_labelframe,
			style = "Contained.TLabelframe", padding = 8,
			labelwidget = frmd_label(display_labelframe, "UI Style")) #Style LF
		for i in CNST.THEME_PACKAGES.keys():
			b = ttk.Radiobutton(ui_style_labelframe, variable = self.ui_style_var,
				text = i, value = i, style = "Contained.TRadiobutton")
			b.grid(ipadx = 4, sticky = "w") # Style btns
		ttk.Radiobutton(ui_style_labelframe, variable = self.ui_style_var,
			text = "Default", value = "_DEFAULT", style =
			"Contained.TRadiobutton").grid(ipadx = 4, sticky = "w") # Default style
		ui_style_labelframe.grid(sticky = "news", pady = 4)

		path_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Paths"))
		path_labelframe.grid_columnconfigure(1, weight = 1)
		for i, j in enumerate((("Steam:", self.steampath_var),
					("HLAE:", self.hlaepath_var))):
			desc_label = ttk.Label(path_labelframe,
				style = "Contained.TLabel", text = j[0])
			path_entry = ttk.Entry(path_labelframe, state = "readonly",
				textvariable = j[1])
			def _tmp_handler(self = self, var = j[1]): # that's a no from me dawg
				return self._sel_dir(var)
			change_btn = ttk.Button(path_labelframe, text = "Change...",
				command = _tmp_handler, style = "Contained.TButton")
			desc_label.grid(row = i, column = 0, sticky = "w")
			path_entry.grid(row = i, column = 1, sticky = "ew")
			change_btn.grid(row = i, column = 2, padx = (3, 0))

		datagrab_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Get bookmark information via..."))
		datagrab_labelframe.grid_columnconfigure(0, weight = 1)
		for i, j in ((".json files", 2), (CNST.EVENT_FILE, 1), ("None", 0)):
			b = ttk.Radiobutton(datagrab_labelframe, value = j,
				variable = self.datagrabmode_var, text = i,
				style = "Contained.TRadiobutton")
			b.grid(sticky = "w", ipadx = 4)

		eventread_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Read _events.txt in chunks of size..."))
		eventread_labelframe.grid_columnconfigure(0, weight = 1)
		self.blockszselector = ttk.Combobox(eventread_labelframe,
			state = "readonly", values = [k for k in self.blockszvals])
		self.blockszselector.grid(sticky = "ew")

		try:
			self.blockszvals[convertunit(self.cfg["evtblocksz"], "B")]
			self.blockszselector.set(convertunit(self.cfg["evtblocksz"], "B"))
		except KeyError:
			self.blockszselector.set(next(iter(self.blockszvals)))

		display_labelframe.grid(columnspan = 2, pady = 3, sticky = "news")
		path_labelframe.grid(columnspan = 2, pady = 3, sticky = "news")
		datagrab_labelframe.grid(columnspan = 2, pady = 3, sticky = "news")
		eventread_labelframe.grid(columnspan = 2, pady = 3, sticky = "news")

		btconfirm = ttk.Button(master, text = "Ok", command = lambda: self.done(1))
		btcancel = ttk.Button(master, text = "Cancel", command = lambda: self.done(0))

		btconfirm.grid(padx = (0, 3), sticky = "news")
		btcancel.grid(row = 4, column = 1, padx = (3, 0), sticky = "news")

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		if param:
			self.result = {
				"datagrabmode": self.datagrabmode_var.get(),
				"previewdemos": self.preview_var.get(),
				"steampath": self.steampath_var.get(),
				"hlaepath": self.hlaepath_var.get(),
				"evtblocksz": self.blockszvals[self.blockszselector.get()],
				"ui_theme": self.ui_style_var.get(),
				"lazyreload": self.lazyreload_var.get(),
			}
		else:
			self.result = None
		self.destroy()

	def _sel_dir(self, variable):
		'''Prompt the user to select a directory, then modify the tkinter
		variable variable with the selected value.
		'''
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		variable.set(sel)

	def _create_tk_var(self, type_, name, inivalue):
		'''Creates a tkinter variable of type "str", "int", "bool", "double",
		registers it as an attribute of the dialog with name name and sets
		it to inivalue.
		'''
		try:
			getattr(self, name)
			raise ValueError("Variable {} already exists.".format(name))
		except AttributeError:
			pass
		setattr(self, name, _TK_VARTYPES[type_]())
		getattr(self, name).set(inivalue)
