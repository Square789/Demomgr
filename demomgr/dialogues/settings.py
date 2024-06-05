import os
import re
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import typing as t

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr import constants as CNST
from demomgr.helpers import convertunit, frmd_label
from demomgr.platforming import quote_cmdline_arg, split_cmdline
from demomgr.tk_widgets import DmgrEntry, DynamicLabel, PasswordButton

if t.TYPE_CHECKING:
	from demomgr.config import Config


_VALID_FILE_MANAGER_TEMPLATES = {"D", "S", "s"}
_RE_VALID_TEMPLATE = re.compile(
	r"(?<!%)(?:%%)*(%([" +
	''.join(map(re.escape, _VALID_FILE_MANAGER_TEMPLATES)) +
	r"]))"
)
_RE_UNBALANCED_PERCENT = re.compile(r"(?<!%)(?:%%)*%(?!%)")

def process_file_manager_args(args: str) -> t.Union[t.List[t.Tuple[str, bool]], str]:
	argl = split_cmdline(args)

	template: t.List[t.Tuple[str, bool]] = []
	for i, arg in enumerate(argl):
		template_match = _RE_VALID_TEMPLATE.search(arg)
		if template_match:
			if template_match.end(1) - template_match.start(1) != len(arg):
				return f"Argument {i} contained a template and additional characters."
			else:
				template.append((template_match.group(2), True))
		else:
			if _RE_UNBALANCED_PERCENT.search(arg):
				return f"Argument {i} contained unbalanced percent escapes."
			template.append((arg.replace("%%", "%"), False))

	return template


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

		#self.wm_resizable(False, False)
		# self.wm_attributes("-type", "dialog")

		label = ttk.Label(mainframe, text = (
			f"The values of the following settings are malformed:\n{self.malformed_str}"
		))
		label.grid(column = 0, row = 0, sticky = "ew", pady = (0, 8))
		warnlabel = ttk.Label(
			mainframe,
			text = "If you save now, they will be reset to their default values.",
			style = "Warning.TLabel",
		)
		warnlabel.grid(column = 0, row = 1, sticky = "ew")

		button_frame = ttk.Frame(mainframe, padding = 5)
		button_frame.grid_columnconfigure((0, 1), weight = 1)
		discard_button = ttk.Button(button_frame, text = "Reset and save", command = self._discard)
		go_back_button = ttk.Button(button_frame, text = "Go back", command = self._go_back)
		discard_button.grid(column = 0, row = 0, padx = (0, 5), sticky = "ew")
		go_back_button.grid(column = 1, row = 0, sticky = "ew")
		#mainframe.grid_columnconfigure(0, weight = 1)
		#mainframe.grid_rowconfigure(1, weight = 1)
		button_frame.grid(column = 0, row = 2, sticky = "ew")

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


# def _make_settings_labelframe(m, heading, *args, **kwargs) -> ttk.LabelFrame:
# 	kwargs.setdefault("padding", 8)
# 	kwargs.setdefault("labelwidget", frmd_label(m, heading))
# 	return ttk.LabelFrame(m, *args, **kwargs)


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
			200, 400, display_labelframe,
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

		# Crappy hack cause the text pushes away too much space otherwise
		tf_exe_frame = ttk.Frame(path_labelframe, style="Contained.TFrame")
		tf_exe_frame.grid_columnconfigure(1, weight = 1)

		self.path_entry_steam = DmgrEntry(path_labelframe, CNST.PATH_MAX)
		self.path_entry_hlae = DmgrEntry(path_labelframe, CNST.PATH_MAX)
		self.path_entry_hlae_tf2_exe_name = DmgrEntry(tf_exe_frame, CNST.FILENAME_MAX)
		self.path_entry_file_manager = DmgrEntry(path_labelframe, CNST.PATH_MAX)

		for i, (name, lframe, path_entry, dir_only) in enumerate((
			("Steam:", path_labelframe, self.path_entry_steam, True),
			("HLAE:", path_labelframe, self.path_entry_hlae, True),
			("HLAE TF2 executable:", tf_exe_frame, self.path_entry_hlae_tf2_exe_name, None),
			("File manager:", path_labelframe, self.path_entry_file_manager, False),
		)):
			desc_label = ttk.Label(lframe, style = "Contained.TLabel", text = name)

			if dir_only is not None:
				change_btn = ttk.Button(
					lframe,
					text = "Change...",
					command = (
						(lambda e=path_entry: self._sel_dir(e)) if dir_only
						else (lambda e=path_entry: self._sel_file(e))
					),
					style = "Contained.TButton",
				)
			else:
				change_btn = None

			desc_label.grid(row = i, column = 0, padx = (0, 3), sticky = "e")
			path_entry.grid(row = i, column = 1, pady = (0, 3 * (i != 3)), sticky = "ew")
			if change_btn is not None:
				change_btn.grid(row = i, column = 2, padx = (3, 0))

		tf_exe_frame.grid(row = 2, columnspan = 2, sticky = "ew")

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
			labelwidget = frmd_label(suboptions_pane, "Custom file manager launch arguments"),
		)
		custom_file_manager_arg_labelframe.grid_columnconfigure(0, weight = 1)
		self.file_manager_launchcmd_entry = ttk.Entry(
			custom_file_manager_arg_labelframe, style = "Contained.TEntry"
		)
		self.file_manager_launchcmd_entry.grid(column = 0, row = 0, sticky = "ew")
		file_manager_launchcmd_label = DynamicLabel(
			400, 500, custom_file_manager_arg_labelframe, style = "Contained.TLabel",
			justify = tk.LEFT, text = (
				"A few special arguments exist that will be replaced by 0, 1 or more actual "
				"arguments.\n"
				"These must be specified standalone (`as%Df` is invalid).\n"
				"- %D: The current directory as single argument\n"
				"- %S: All selected demos as separate arguments\n"
				"- %s: Like %s, but an explicit empty string for an empty selection.\n"
				"- %%: Becomes a single %, for when you want to include literal percents "
				"in your command line for whatever reason"
			)
		)
		file_manager_launchcmd_label.grid(column = 0, row = 1, sticky = "nesw")

		# Set up sidebar
		self._INTERFACE = {
			"Interface": (display_labelframe, date_format_labelframe),
			"Information reading": (datagrab_labelframe, eventread_labelframe),
			"Paths": (path_labelframe,),
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
		self.path_entry_hlae_tf2_exe_name.insert(0, self.cfg.hlae_tf2_exe_name)
		self.path_entry_file_manager.insert(0, self.cfg.file_manager_path or "")
		self.rcon_pwd_entry.insert(0, self.cfg.rcon_pwd or "")
		self.rcon_port_entry.insert(0, str(self.cfg.rcon_port))
		w = []
		for arg, is_template in self.cfg.file_manager_launchcmd:
			if is_template:
				w.append("%" + arg)
			else:
				w.append(quote_cmdline_arg(arg.replace("%", "%%")))
		self.file_manager_launchcmd_entry.insert(0, " ".join(w))

		# Trigger display of selected pane
		tmp_inibtn.invoke()

	def done(self, save=False) -> None:
		if save:
			config_dict = self._collect_settings_dict()
			bad_settings = []
			for k, v in config_dict.items():
				if isinstance(v, MalformedSetting):
					config_dict[k] = v.default
					bad_settings.append(v.info)

			if bad_settings:
				# NOTE: This will (at least on my windowing system) cause a new entry in the task bar
				# I have no idea how to prevent this, I guess only the first layer of transience
				# causes no extra entry.
				reminder = _MalformedSettingsReminder(self, bad_settings)
				reminder.show()
				# Extremely important to reacquire grab to self, otherwise main window becomes
				# responsive again
				try:
					# It's possible that the settings dialog/self is actually gone by this point,
					# in case the settings window was closed through the close button.
					# `done` and `destroy` have run already; stop immediately.
					self.grab_set()
				except tk.TclError as e:
					return

				if reminder.result.state != DIAGSIG.SUCCESS:
					return

			self.result.state = DIAGSIG.SUCCESS
			self.result.data = config_dict
		else:
			self.result.state = DIAGSIG.FAILURE

		self.result.remember = [self._selectedpane_var.get()]

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
			"rcon_pwd": self.rcon_pwd_entry.get() or None,
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
				result[key] = MalformedSetting(name + " (Path is not absolute.)", None)
			else:
				result[key] = v

		if not (v := self.path_entry_hlae_tf2_exe_name.get()):
			result["hlae_tf2_exe_name"] = MalformedSetting("HLAE TF2 exe name is empty", "tf.exe")
		else:
			result["hlae_tf2_exe_name"] = v

		try:
			fma = process_file_manager_args(self.file_manager_launchcmd_entry.get())
		except ValueError as e:
			fma = "".join(e.args)
		if isinstance(fma, str):
			result["file_manager_launchcmd"] = MalformedSetting(
				f"File manager argument template ({fma})", [],
			)
		else:
			result["file_manager_launchcmd"] = fma

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
