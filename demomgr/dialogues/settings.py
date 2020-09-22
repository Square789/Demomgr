import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr import constants as CNST
from demomgr.helper_tk_widgets import TtkText
from demomgr.helpers import convertunit, frmd_label, int_validator

_TK_VARTYPES = {
	"str": tk.StringVar,
	"int": tk.IntVar,
	"bool": tk.BooleanVar,
	"double": tk.DoubleVar,
}

class Settings(BaseDialog):
	"""
	Settings dialog that offers a bunch of configuration options.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if user hit OK, else FAILURE.
	`self.result.data` will be a dict with the following keys:
		"datagrabmode": How the demo information should be gathered.
			0 for None, 1 for _events.txt, 2 for .json .
		"previewdemos": Whether to preview demos in the main view. (bool)
		"steampath": Path to steam (str)
		"hlaepath": Path to HLAE (str)
		"evtblocksz": Chunk size _events.txt should be read in. (int)
		"ui_theme": Interface theme. Key of same name must be in
			constants. (str)
		"lazyreload": Whether to lazily refresh singular UI elements instead
			of reloading entire UI on changes as single demo deletion or
			bookmark setting. (bool)

	Widget state remembering:
		0: Last visited section 
	"""

	REMEMBER_DEFAULT = [0]

	def __init__(self, parent, cfg, remember):
		"""
		parent: Tkinter widget that is the parent of this dialog.
		cfg: Program configuration. (dict)
		remember: List of arbitrary values, see class docstring.
		"""
		super().__init__(parent, "Settings")

		self.cfg = cfg

		self._create_tk_var("int", "datagrabmode_var", cfg["datagrabmode"])
		self._create_tk_var("bool", "preview_var", cfg["previewdemos"])
		self._create_tk_var("str", "steampath_var", cfg["steampath"])
		self._create_tk_var("str", "hlaepath_var", cfg["hlaepath"])
		self._create_tk_var("str", "ui_style_var", cfg["ui_theme"])
		self._create_tk_var("bool", "lazyreload_var", cfg["lazyreload"])
		self._create_tk_var("str", "rcon_pwd_var", cfg["rcon_pwd"])
		self._create_tk_var("int", "rcon_port_var", cfg["rcon_port"])

		self._selected_pane = None
		self.ui_remember = self.validate_and_update_remember(remember)

		self.blockszvals = {convertunit(i, "B"): i
			for i in [2**pw for pw in range(12, 28)]}

	def body(self, master):
		"""UI setup."""
		self.protocol("WM_DELETE_WINDOW", self.done)

		master.grid_columnconfigure((0, 1), weight = 1)
		mainframe = ttk.Frame(master)
		mainframe.grid_columnconfigure(1, weight = 1)
		mainframe.grid_rowconfigure(0, weight = 1)
		suboptions_pane = ttk.Frame(mainframe)
		suboptions_pane.grid_columnconfigure(0, weight = 1)

		display_labelframe = ttk.LabelFrame(suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "Display"))
		display_labelframe.grid_columnconfigure(0, weight = 1)
		ttk.Checkbutton(display_labelframe, variable = self.preview_var,
			text = "Preview demos?", style = "Contained.TCheckbutton").grid(
			sticky = "w", ipadx = 4) # Preview
		lazyreload_btn = ttk.Checkbutton(display_labelframe,
			variable = self.lazyreload_var, text = "Lazy reload of main demo view",
			style = "Contained.TCheckbutton")
		lazyreload_txt = ttk.Label(display_labelframe,
			text = "Will not reload the entire directory on minor\n" \
				"changes such as bookmark modification.",
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

		path_labelframe = ttk.LabelFrame(suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "Paths"))
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

		datagrab_labelframe = ttk.LabelFrame(suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "Get demo information via..."))
		datagrab_labelframe.grid_columnconfigure(0, weight = 1)
		for i, j in ((".json files", 2), (CNST.EVENT_FILE, 1), ("None", 0)):
			b = ttk.Radiobutton(datagrab_labelframe, value = j,
				variable = self.datagrabmode_var, text = i,
				style = "Contained.TRadiobutton")
			b.grid(sticky = "w", ipadx = 4)

		eventread_labelframe = ttk.LabelFrame(suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "Read _events.txt in chunks of size..."))
		eventread_labelframe.grid_columnconfigure(0, weight = 1)
		self.blockszselector = ttk.Combobox(eventread_labelframe,
			state = "readonly", values = [k for k in self.blockszvals])
		self.blockszselector.grid(sticky = "ew")

		rcon_pwd_labelframe = ttk.LabelFrame(suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "RCON password"))
		rcon_pwd_labelframe.grid_columnconfigure(0, weight = 1)
		rcon_entry = ttk.Entry(rcon_pwd_labelframe, textvariable = self.rcon_pwd_var, show = "\u25A0")
		rcon_entry.grid(column = 0, row = 0, sticky = "ew")
		entry_visibility_toggle = ttk.Button(rcon_pwd_labelframe, text = "Show", takefocus = False)
		entry_visibility_toggle.bind("<Button-1>", lambda _: rcon_entry.configure(show = ""))
		entry_visibility_toggle.bind("<ButtonRelease-1>", lambda _: rcon_entry.configure(show = "\u25A0"))
		entry_visibility_toggle.grid(column = 1, row = 0)

		int_val_id = master.register(int_validator)
		rcon_port_labelframe = ttk.LabelFrame(suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "RCON port"))
		rcon_port_labelframe.grid_columnconfigure(0, weight = 1)
		self.rcon_port_entry = ttk.Entry(rcon_port_labelframe, validate = "key",
			validatecommand = (int_val_id, "%S", "%P"))
		self.rcon_port_entry.insert(0, str(self.cfg["rcon_port"]))
		self.rcon_port_entry.grid(column = 0, row = 0, sticky = "ew")

		try:
			self.blockszvals[convertunit(self.cfg["evtblocksz"], "B")]
			self.blockszselector.set(convertunit(self.cfg["evtblocksz"], "B"))
		except KeyError:
			self.blockszselector.set(next(iter(self.blockszvals)))

		self._interface = {
			"Interface": (display_labelframe, ),
			"Information reading": (datagrab_labelframe, eventread_labelframe),
			"Paths": (path_labelframe, ),
			"RCON": (rcon_pwd_labelframe, rcon_port_labelframe),
		}
		self._create_tk_var("int", "_selectedpane_var", 0)
		self._selected_pane = next(iter(self._interface)) # Yields first key
		# Only useful so deleting widgets for the first time in
		# self._reload_options_panel will not throw AttributeErrors

		sidebar_outerframe = ttk.Frame(mainframe, style = "Border.TFrame")
		sidebar_outerframe.grid_columnconfigure(0, weight = 1)
		sidebar_outerframe.grid_rowconfigure(0, weight = 1)
		sidebar = ttk.Frame(sidebar_outerframe, style = "Contained.TFrame")

		for i, k, v in zip(
			range(len(self._interface)),
			self._interface.keys(),
			self._interface.values()
		):
			def _handler(self = self, k = k):
				self._reload_options_pane(k)
			curbtn = ttk.Radiobutton(sidebar, text = k, value = i, command = _handler,
				variable = self._selectedpane_var, style = "Contained.TRadiobutton")
			curbtn.grid(column = 0, row = i, sticky = "w", ipadx = 4, padx = 4)
			if i == self.ui_remember[0]:
				tmp_inibtn = curbtn

		tmp_inibtn.invoke() # To invoke filling command

		sidebar.grid(column = 0, row = 0, sticky = "nesw", padx = 1, pady = 1)
		sidebar_outerframe.grid(column = 0, row = 0, sticky = "nesw")
		suboptions_pane.grid(column = 1, row = 0, sticky = "nesw")
		mainframe.grid(column = 0, row = 0, columnspan = 2, sticky = "news")

		btconfirm = ttk.Button(master, text = "Save", command = lambda: self.done(1))
		btcancel = ttk.Button(master, text = "Cancel", command = lambda: self.done(0))

		btconfirm.grid(column = 0, row = 1, padx = (0, 3), pady = (3, 0),  sticky = "news")
		btcancel.grid(column = 1, row = 1, padx = (3, 0), pady = (3, 0), sticky = "news")

	def _create_tk_var(self, type_, name, inivalue):
		"""Creates a tkinter variable of type "str", "int", "bool", "double",
		registers it as an attribute of the dialog with name name and sets
		it to inivalue.
		"""
		try:
			getattr(self, name)
			raise ValueError(f"Variable {name} already exists.")
		except AttributeError:
			pass
		setattr(self, name, _TK_VARTYPES[type_]())
		getattr(self, name).set(inivalue)

	def done(self, save=False):
		self.withdraw()
		self.update_idletasks()
		self.result.remember = [self._selectedpane_var.get()]
		if save:
			self.result.state = DIAGSIG.SUCCESS
			self.result.data = {
				"datagrabmode": self.datagrabmode_var.get(),
				"previewdemos": self.preview_var.get(),
				"steampath": self.steampath_var.get(),
				"hlaepath": self.hlaepath_var.get(),
				"evtblocksz": self.blockszvals[self.blockszselector.get()],
				"ui_theme": self.ui_style_var.get(),
				"lazyreload": self.lazyreload_var.get(),
				"rcon_pwd": self.rcon_pwd_var.get(),
				"rcon_port": int(self.rcon_port_entry.get()),
			}
		else:
			self.result.state = DIAGSIG.FAILURE
		self.destroy()

	def _sel_dir(self, variable):
		"""Prompt the user to select a directory, then modify the tkinter
		variable variable with the selected value.
		"""
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		variable.set(sel)

	def _reload_options_pane(self, key):
		"""
		Clears and repopulates right pane with the widgets in
		self._interface[key]
		"""
		for widget in self._interface[self._selected_pane]:
			widget.grid_forget()
		self._selected_pane = key
		for i, widget in enumerate(self._interface[key]):
			pady = (
				3 * (i != 0),
				3 * (i != len(self._interface[key]) - 1),
			)
			widget.grid(column = 0, row = i, sticky = "nesw",
				padx = (3, 0), pady = pady)
