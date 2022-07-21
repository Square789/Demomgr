import os
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import typing as t

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr import constants as CNST
from demomgr.helpers import convertunit, frmd_label
from demomgr.tk_widgets import DmgrEntry, DynamicLabel, PasswordButton

if t.TYPE_CHECKING:
	from demomgr.config import Config


class _MalformedSettingsReminder(BaseDialog):
	"""
	Dialog popping up a warning to the user that settings are
	malformed and will be restored to their the default on exit.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if user chose to exit anyways
		and FAILURE if they decided to go back.
	"""

	def __init__(self, parent: tk.Wm, malformed_ones: t.List[str]) -> None:
		super().__init__(parent, "Malformed Settings")

		self.malformed_str = "- " + "\n- ".join(malformed_ones)

	def body(self, mainframe: tk.Widget) -> None:
		self.protocol("WM_DELETE_WINDOW", self._go_back)
		# self.overrideredirect(1)

		self.wm_resizable(False, False)
		self.wm_attributes("-type", "dialog")

		label = ttk.Label(mainframe, text = (
			f"The values of the following settings are malformed:\n{self.malformed_str}\n"
			f"If you save now, they will be reset to their default values."
		))
		label.grid(column = 0, row = 0, sticky = "nesw")

		button_frame = ttk.Frame(mainframe, padding = 5)
		button_frame.grid_rowconfigure(0, weight = 1)
		discard_button = ttk.Button(button_frame, text = "Reset and save", command = self._discard)
		go_back_button = ttk.Button(button_frame, text = "Go back", command = self._go_back)
		discard_button.grid(column = 0, row = 0, padx = (0, 5), sticky = "ew")
		go_back_button.grid(column = 1, row = 0, sticky = "ew")
		button_frame.grid(column = 0, row = 1, sticky = "ew")

	def _discard(self) -> None:
		self.result.state = DIAGSIG.SUCCESS
		self.destroy()

	def _go_back(self) -> None:
		self.result.state = DIAGSIG.FAILURE
		self.destroy()


class MalformedSetting():
	__slots__ = ("info", "default")

	def __init__(self, info: str, default: object) -> None:
		self.info = info
		self.default = default


class Settings(BaseDialog):
	"""
	Settings dialog that offers a bunch of configuration options.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if user hit OK, else FAILURE.
	`self.result.data` will be a dict with the following keys:
		"data_grab_mode": (DATA_GRAB_MODE)
		"file_manager_mode": (FILE_MANAGER_MODE)
		"preview_demos": Whether to preview demos in the main view. (bool)
		"steam_path": Path to steam (str | None)
		"hlae_path": Path to HLAE (str | None)
		"file_manager_path": Path to file manager (str | None)
		"events_blocksize": Chunk size _events.txt should be read in. (int)
		"ui_theme": Interface theme. Key of same name must be in
			constants. (str)
		"lazy_reload": Whether to lazily refresh singular UI elements instead
			of reloading entire UI on changes as single demo deletion or
			bookmark setting. (bool)
		"rcon_pwd": Password to use for RCON connections. (str | None)
		"rcon_port": Port to use for RCON connections. (int)

	Widget state remembering:
		0: Last visited section
	"""

	def __init__(self, parent: tk.Wm, cfg: "Config", remember: t.List) -> None:
		"""
		parent: Tkinter widget that is the parent of this dialog.
		cfg: Program configuration
		remember: List of arbitrary values, see class docstring.
		"""
		super().__init__(parent, "Settings")

		self.cfg = cfg

		self._selected_pane: t.Optional[str] = None
		self.ui_remember = remember

		self.blockszvals = {convertunit(i, "B"): i for i in (2**pw for pw in range(12, 28))}

	def body(self, master: tk.Widget) -> None:
		"""UI setup."""
		self.protocol("WM_DELETE_WINDOW", self.done)

		self.datagrabmode_var = tk.IntVar(value = self.cfg.data_grab_mode.value)
		self.file_manager_mode_var = tk.IntVar(value = self.cfg.file_manager_mode.value)
		self.preview_var = tk.BooleanVar(value = self.cfg.preview_demos)
		self.ui_style_var = tk.StringVar(value = self.cfg.ui_theme)
		self.lazyreload_var = tk.BooleanVar(value = self.cfg.lazy_reload)
		self._selectedpane_var = tk.IntVar()

		master.grid_columnconfigure((0, 1), weight = 1)
		mainframe = ttk.Frame(master)
		mainframe.grid_columnconfigure(1, weight = 1)
		mainframe.grid_rowconfigure(0, weight = 1)
		suboptions_pane = ttk.Frame(mainframe)
		suboptions_pane.grid_columnconfigure(0, weight = 1)

		# === Display Pane ===
		display_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8, labelwidget = frmd_label(suboptions_pane, "Display")
		)
		display_labelframe.grid_columnconfigure(0, weight = 1)
		ttk.Checkbutton(
			display_labelframe, variable = self.preview_var, text = "Show demo header information",
			style = "Contained.TCheckbutton"
		).grid(sticky = "w", ipadx = 4) # Preview
		lazyreload_btn = ttk.Checkbutton(
			display_labelframe, variable = self.lazyreload_var, text = "Lazy reload of main demo view",
			style = "Contained.TCheckbutton"
		)
		lazyreload_txt = DynamicLabel(
			200, 300, display_labelframe,
			text = (
				"Will not reload the entire directory on minor changes such as "
				"bookmark modification."
			), justify = tk.LEFT, style = "Contained.TLabel"
		)
		lazyreload_btn.grid(sticky = "w", ipadx = 4, pady = (2, 0))
		lazyreload_txt.grid(sticky = "w", padx = (8, 0)) # Lazy reload

		ui_style_labelframe = ttk.Labelframe(
			display_labelframe, style = "Contained.TLabelframe", padding = 8,
			labelwidget = frmd_label(display_labelframe, "UI Style")
		) # Style LF
		for i in CNST.THEME_PACKAGES.keys():
			b = ttk.Radiobutton(
				ui_style_labelframe, variable = self.ui_style_var, text = i, value = i,
				style = "Contained.TRadiobutton"
			)
			b.grid(ipadx = 4, sticky = "w") # Style btns
		ttk.Radiobutton(
			ui_style_labelframe, variable = self.ui_style_var, text = "Default", value = "_DEFAULT",
			style = "Contained.TRadiobutton"
		).grid(ipadx = 4, sticky = "w") # Default style
		ui_style_labelframe.grid(sticky = "news", pady = 4)

		date_format_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8, labelwidget = frmd_label(suboptions_pane, "Date format")
		)
		date_format_labelframe.grid_columnconfigure(0, weight = 1)
		self.date_fmt_combobox = ttk.Combobox(
			date_format_labelframe, state = "readonly", values = CNST.DATE_FORMATS
		)
		self.date_fmt_combobox.grid(sticky = "ew")

		# === Path pane ===
		path_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8, labelwidget = frmd_label(suboptions_pane, "Paths")
		)
		path_labelframe.grid_columnconfigure(1, weight = 1)

		self.path_entry_steam = DmgrEntry(path_labelframe, CNST.PATH_MAX)
		self.path_entry_hlae = DmgrEntry(path_labelframe, CNST.PATH_MAX)
		self.path_entry_file_manager = DmgrEntry(path_labelframe, CNST.PATH_MAX)

		for i, (name, path_entry, dir_only) in enumerate((
			("Steam:", self.path_entry_steam, True),
			("HLAE:", self.path_entry_hlae, True),
			("File manager:", self.path_entry_file_manager, False),
		)):
			desc_label = ttk.Label(path_labelframe, style = "Contained.TLabel", text = name)
			if dir_only:
				# ugly parameter binding
				def _tmp_handler(e = path_entry):
					return self._sel_dir(e)
			else:
				def _tmp_handler(e = path_entry):
					return self._sel_file(e)
			change_btn = ttk.Button(
				path_labelframe, text = "Change...", command = _tmp_handler, style = "Contained.TButton"
			)
			desc_label.grid(row = i, column = 0, sticky = "e")
			path_entry.grid(row = i, column = 1, padx = (3, 0), sticky = "ew")
			change_btn.grid(row = i, column = 2, padx = (3, 0))

		# === Data retrieval pane ===
		datagrab_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8, labelwidget = frmd_label(suboptions_pane, "Get demo information via...")
		)
		datagrab_labelframe.grid_columnconfigure(0, weight = 1)
		for enum_attr in (
			CNST.DATA_GRAB_MODE.NONE,
			CNST.DATA_GRAB_MODE.EVENTS,
			CNST.DATA_GRAB_MODE.JSON,
		):
			b = ttk.Radiobutton(
				datagrab_labelframe, value = enum_attr.value, variable = self.datagrabmode_var,
				text = enum_attr.get_display_name(), style = "Contained.TRadiobutton"
			)
			b.grid(sticky = "w", ipadx = 4)

		eventread_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "Read _events.txt in chunks of size...")
		)
		eventread_labelframe.grid_columnconfigure(0, weight = 1)
		self.blockszselector = ttk.Combobox(
			eventread_labelframe, state = "readonly", values = tuple(self.blockszvals.keys())
		)
		self.blockszselector.grid(sticky = "ew")

		# === RCON pane ===
		rcon_pwd_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8, labelwidget = frmd_label(suboptions_pane, "RCON password")
		)
		rcon_pwd_labelframe.grid_columnconfigure(0, weight = 1)
		self.rcon_pwd_entry = DmgrEntry(rcon_pwd_labelframe, CNST.RCON_PWD_MAX, show = "\u25A0")
		self.rcon_pwd_entry.grid(column = 0, row = 0, sticky = "ew")
		entry_visibility_toggle = PasswordButton(rcon_pwd_labelframe, text = "Show")
		entry_visibility_toggle.bind_to_entry(self.rcon_pwd_entry)
		entry_visibility_toggle.grid(column = 1, row = 0)

		rcon_port_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8, labelwidget = frmd_label(suboptions_pane, "RCON port")
		)
		rcon_port_labelframe.grid_columnconfigure(0, weight = 1)
		self.rcon_port_entry = DmgrEntry(rcon_port_labelframe, -1)
		self.rcon_port_entry.grid(column = 0, row = 0, sticky = "ew")

		# === File manager pane ===
		file_manager_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8, labelwidget = frmd_label(suboptions_pane, "File manager")
		)
		for name, enum_attr in (
			("Windows explorer", CNST.FILE_MANAGER_MODE.WINDOWS_EXPLORER),
			("Custom (Paths > File manager)", CNST.FILE_MANAGER_MODE.USER_DEFINED),
		):
			b = ttk.Radiobutton(
				file_manager_labelframe, value = enum_attr.value,
				variable = self.file_manager_mode_var, text = name,
				style = "Contained.TRadiobutton"
			)
			b.grid(sticky = "w", ipadx = 4)

		custom_file_manager_arg_labelframe = ttk.LabelFrame(
			suboptions_pane, padding = 8,
			labelwidget = frmd_label(suboptions_pane, "Custom file manager arguments"),
		)
		custom_file_manager_arg_labelframe.grid_columnconfigure(0, weight = 1)
		self.file_manager_arg_template_entry = DmgrEntry(
			custom_file_manager_arg_labelframe, CNST.CMDLINE_MAX, style = "Contained.TEntry"
		)
		self.file_manager_arg_template_entry.grid(column = 0, row = 0, sticky = "ew")
		file_manager_arg_template_label = DynamicLabel(
			200, 300, custom_file_manager_arg_labelframe, style = "Contained.TLabel",
			justify = tk.LEFT, text = (
				"Lorem ipsum dolor sit amet."
			)
		)
		file_manager_arg_template_label.grid(column = 0, row = 1, sticky = "nesw")


		# Set up sidebar
		self._INTERFACE = {
			"Interface": (display_labelframe, date_format_labelframe),
			"Information reading": (datagrab_labelframe, eventread_labelframe),
			"Paths": (path_labelframe, ),
			"RCON": (rcon_pwd_labelframe, rcon_port_labelframe),
			"File manager": (file_manager_labelframe, custom_file_manager_arg_labelframe),
		}

		sidebar_outerframe = ttk.Frame(mainframe, style = "Border.TFrame")
		sidebar_outerframe.grid_columnconfigure(0, weight = 1)
		sidebar_outerframe.grid_rowconfigure(0, weight = 1)
		sidebar = ttk.Frame(sidebar_outerframe, style = "Contained.TFrame")

		tmp_inibtn = None
		for i, k in enumerate(self._INTERFACE):
			def _handler(self = self, k = k):
				self._reload_options_pane(k)
			curbtn = ttk.Radiobutton(
				sidebar, text = k, value = i, command = _handler,
				variable = self._selectedpane_var, style = "Contained.TRadiobutton"
			)
			curbtn.grid(column = 0, row = i, sticky = "w", ipadx = 4, padx = 4)
			# Fallback to 0 if remember value is scuffed
			if i == 0 or i == self.ui_remember[0]:
				tmp_inibtn = curbtn

		sidebar.grid(column = 0, row = 0, sticky = "nesw", padx = 1, pady = 1)
		sidebar_outerframe.grid(column = 0, row = 0, sticky = "nesw")
		suboptions_pane.grid(column = 1, row = 0, sticky = "nesw")
		mainframe.grid(column = 0, row = 0, columnspan = 2, sticky = "news")

		btconfirm = ttk.Button(master, text = "Save", command = lambda: self.done(1))
		btcancel = ttk.Button(master, text = "Cancel", command = lambda: self.done(0))

		btconfirm.grid(column = 0, row = 1, padx = (0, 3), pady = (3, 0), sticky = "news")
		btcancel.grid(column = 1, row = 1, padx = (3, 0), pady = (3, 0), sticky = "news")

		# Set comboboxes
		tmp = convertunit(self.cfg.events_blocksize, "B")
		if tmp in self.blockszvals:
			self.blockszselector.set(tmp)
		else:
			self.blockszselector.set(next(iter(self.blockszvals)))

		tmp = self.cfg.date_format
		if tmp in CNST.DATE_FORMATS:
			self.date_fmt_combobox.set(tmp)
		else:
			self.date_fmt_combobox.set(CNST.DATE_FORMATS[0])

		# Set entries
		self.path_entry_steam.insert(0, self.cfg.steam_path or "")
		self.path_entry_hlae.insert(0, self.cfg.hlae_path or "")
		self.path_entry_file_manager.insert(0, self.cfg.file_manager_path or "")
		self.rcon_pwd_entry.insert(0, self.cfg.rcon_pwd or "")
		self.rcon_port_entry.insert(0, str(self.cfg.rcon_port))

		# Trigger display of selected pane
		tmp_inibtn.invoke()

	def done(self, save=False) -> None:
		config_dict = self._collect_settings_dict()
		bad_settings = []
		for k, v in config_dict.items():
			if isinstance(v, MalformedSetting):
				config_dict[k] = v.default
				bad_settings.append(v.info)

		if save and bad_settings:
			# NOTE: This will (at least on my windowing system) cause a new entry in the task bar
			# I have no idea how to prevent this, I guess only the first layer of transience
			# causes no extra entry.
			reminder = _MalformedSettingsReminder(self, bad_settings)
			reminder.show()
			# Extremely important to reacquire grab to self, otherwise
			# main window becomes responsive again
			self.grab_set()
			if reminder.result.state != DIAGSIG.SUCCESS:
				return

		# Settings dialog closed for sure at this point #

		self.result.remember = [self._selectedpane_var.get()]
		if save:
			self.result.state = DIAGSIG.SUCCESS
			self.result.data = config_dict
		else:
			self.result.state = DIAGSIG.FAILURE
		self.destroy()

	def _collect_settings_dict(self) -> t.Dict[str, t.Any]:
		result = {
			"data_grab_mode": CNST.DATA_GRAB_MODE(self.datagrabmode_var.get()),
			"file_manager_mode": CNST.FILE_MANAGER_MODE(self.file_manager_mode_var.get()),
			"preview_demos": self.preview_var.get(),
			"date_format": self.date_fmt_combobox.get(),
			"events_blocksize": self.blockszvals[self.blockszselector.get()],
			"ui_theme": self.ui_style_var.get(),
			"lazy_reload": self.lazyreload_var.get(),
			"rcon_pwd": self.rcon_port_entry.get() or None,
			"rcon_port": int(self.rcon_port_entry.get() or 0),
		}

		for key, e, name in (
			("steam_path", self.path_entry_steam, "Steam path"),
			("hlae_path", self.path_entry_hlae, "HLAE path"),
			("file_manager_path", self.path_entry_file_manager, "File manager path"),
		):
			v = e.get()
			if not v:
				result[key] = None
			elif not os.path.isabs(v):
				result[key] = MalformedSetting(name, None)
			else:
				result[key] = v

		if self.file_manager_arg_template_entry.get():
			result["file_manager_arg_template"] = (
				MalformedSetting("File manager argument template", [])
				if self.file_manager_arg_template_entry.get()
				else []
			)

		return result

	def _sel_dir(self, entry: tk.Entry) -> None:
		"""
		Prompts the user to select a directory, then modifies the
		tkinter entry `entry` with the selected value, unless the
		selection was aborted.
		"""
		res = tk_fid.askdirectory()
		if type(res) is not str or not res:
			return
		entry.delete(0, tk.END)
		entry.insert(0, res)

	def _sel_file(self, entry: tk.Entry) -> None:
		"""
		Same as `_sel_dir`, just with a file.
		"""
		res = tk_fid.askopenfilename()
		if type(res) is not str or not res:
			return
		entry.delete(0, tk.END)
		entry.insert(0, res)

	def _reload_options_pane(self, key: str) -> None:
		"""
		Clears and repopulates right pane with the widgets in
		`self._INTERFACE[key]`
		"""
		if self._selected_pane == key:
			return

		# When the user resizes the window, other panes will produce an ugly
		# amount of empty space. This resets user-requested width.
		self.wm_geometry("")

		if self._selected_pane is not None:
			for widget in self._INTERFACE[self._selected_pane]:
				widget.grid_forget()

		self._selected_pane = key
		for i, widget in enumerate(self._INTERFACE[key]):
			pady = (
				3 * (i != 0),
				3 * (i != len(self._INTERFACE[key]) - 1),
			)
			widget.grid(column = 0, row = i, sticky = "nesw", padx = (3, 0), pady = pady)
