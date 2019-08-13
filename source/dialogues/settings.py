import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid

from ._base import BaseDialog

from .. import constants as CNST
from ..helper_tk_widgets import TtkText
from ..helpers import (frmd_label, convertunit)

class Settings(BaseDialog):
	'''Settings dialog that offers a bunch of configuration options.'''
	def __init__(self, parent, cfg):
		'''Args:
		parent: Tkinter widget that is the parent of this dialog.
		cfg: Program configuration.
		'''
		self.cfg = cfg

		self.datagrabmode_var = tk.IntVar()
		self.datagrabmode_var.set(cfg["datagrabmode"])
		self.preview_var = tk.BooleanVar()
		self.preview_var.set(cfg["previewdemos"])
		self.steampath_var = tk.StringVar()
		self.steampath_var.set(cfg["steampath"])
		self.ui_style_var = tk.StringVar()
		self.ui_style_var.set(cfg["ui_theme"])

		self.blockszvals = {convertunit(i, "B"): i
			for i in [2**pw for pw in range(12, 28)]}
		self.result = None

		super().__init__( parent, "Settings")

	def body(self, master):
		'''UI setup.'''
		display_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Display"))
		ttk.Checkbutton(display_labelframe, variable = self.preview_var,
			text="Preview demos?", style = "Contained.TCheckbutton").pack(
			ipadx = 4, anchor = tk.NW)
		ui_style_labelframe = ttk.Labelframe(display_labelframe,
			style = "Contained.TLabelframe", padding = 8,
			labelwidget = frmd_label(display_labelframe, "UI Style") )
		radiobtnframe = ttk.Frame(ui_style_labelframe, style = "Contained.TFrame")
		for i in CNST.THEME_PACKAGES.keys():
			b = ttk.Radiobutton(radiobtnframe, variable = self.ui_style_var,
				text = i, value = i, style = "Contained.TRadiobutton")
			b.pack(side = tk.TOP, anchor = tk.W, ipadx = 4)
		ttk.Radiobutton(radiobtnframe, variable = self.ui_style_var,
			text = "Default", value = "_DEFAULT", style =
			"Contained.TRadiobutton").pack(side = tk.TOP, anchor = tk.W, ipadx = 4)
		radiobtnframe.pack(side = tk.TOP, fill = tk.X)
		ui_style_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 4)

		steampath_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Steam path"))
		self.steampathentry = ttk.Entry(steampath_labelframe, state = "readonly",
			textvariable = self.steampath_var)
		steampath_choosebtn = ttk.Button(steampath_labelframe, text = "Change...",
			command = self.choosesteampath, style = "Contained.TButton")
		self.steampathentry.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.N)
		steampath_choosebtn.pack(side = tk.RIGHT, expand = 0, fill = tk.X, anchor = tk.N)

		datagrab_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Get bookmark information via..."))
		radiobtnframe = ttk.Frame(datagrab_labelframe, style = "Contained.TFrame")
		for i, j in ((".json files", 2), (CNST.EVENT_FILE, 1), ("None", 0)):
			b = ttk.Radiobutton(radiobtnframe, value = j,
				variable = self.datagrabmode_var, text = i,
				style = "Contained.TRadiobutton")
			b.pack(side = tk.TOP, anchor = tk.W, ipadx = 4)
		radiobtnframe.pack(side = tk.TOP, fill = tk.X)
		del radiobtnframe

		eventread_labelframe = ttk.LabelFrame(master, padding = 8,
			labelwidget = frmd_label(master, "Read _events.txt in chunks of size...") )
		self.blockszselector = ttk.Combobox(eventread_labelframe,
			state = "readonly", values = [k for k in self.blockszvals])
		self.blockszselector.pack(side = tk.TOP, expand = 1, fill = tk.X, anchor = tk.N)

		try:
			self.blockszvals[convertunit(self.cfg["evtblocksz"], "B")]
			self.blockszselector.set(convertunit(self.cfg["evtblocksz"], "B"))
		except KeyError:
			self.blockszselector.set(next(iter(self.blockszvals)))

		display_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)
		steampath_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)
		datagrab_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)
		eventread_labelframe.pack(expand = 1, fill = tk.BOTH, pady = 3)

		btconfirm = ttk.Button(master, text = "Ok", command = lambda: self.done(1))
		btcancel = ttk.Button(master, text = "Cancel", command = lambda: self.done(0))

		btconfirm.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (0, 3))
		btcancel.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (3, 0))

	def done(self, param):
		self.withdraw()
		self.update_idletasks()
		if param:
			self.result = {	"datagrabmode":self.datagrabmode_var.get(),
							"previewdemos":self.preview_var.get(),
							"steampath":self.steampath_var.get(),
							"evtblocksz":self.blockszvals[self.blockszselector.get()],
							"ui_theme":self.ui_style_var.get()}
		else:
			self.result = None
		self.destroy()

	def choosesteampath(self):
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steampath_var.set(sel)
