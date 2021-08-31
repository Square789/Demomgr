from itertools import chain, cycle, repeat
import os
import queue
import subprocess
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as tk_msg

from multiframe_list import MultiframeList
from multiframe_list.multiframe_list import SELECTION_TYPE
import vdf

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG
from demomgr import constants as CNST
from demomgr.tk_widgets import TtkText
from demomgr.helpers import frmd_label, tk_secure_str
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, RCONThread

def follow_vdf_keys(vdf_data, keys, key_case_sensitive = True):
	"""
	Resolves a sequence of vdf keys through a given dict representing
	a vdf file and returns the last value resulted from following the
	keys.
	Keys can be processed case insensitively where they will be compared
	to the vdf data keys one-by-one case-agnostically and the first
	matching one returned. Since dict order is stable post-3.6 but icky,
	this is really ugly if a vdf file should contain two keys that
	-ignoring case- are equal.
	Returns None if no dict was present yet there were keys to be
	resolved or when a key was not found in a dictionary.
	"""
	for key in keys:
		if not isinstance(vdf_data, dict):
			return None
		elif key in vdf_data:
			vdf_data = vdf_data[key]
		elif not key_case_sensitive:
			lwr = key.lower()
			for test_key in vdf_data:
				if test_key.lower() == lwr:
					vdf_data = vdf_data[key.lower()]
					break
			else:
				return None
		else:
			return None
	return vdf_data

class User():
	__slots__ = ("dir_name", "name", "launch_opt")

	def __init__(self, dir_name, name = None, launch_opt = None):
		self.dir_name = dir_name
		self.name = name
		self.launch_opt = launch_opt

	def get_display_str(self):
		return self.dir_name + (f" - {self.name}" if self.name is not None else '')

class ErrorLabel():
	__slots__ = ("label", "grid_options", "is_set")

	def __init__(self):
		self.label = None
		self.grid_options = {}
		self.is_set = False

	def set(self, val):
		if val == self.is_set or self.label is None:
			return
		self.is_set = val
		if val:
			self.label.grid(**self.grid_options)
		else:
			self.label.grid_forget()

	def set_grid_options(self, **kw):
		self.grid_options = kw

class ERR_IDX:
	STEAMDIR = 0
	STEAMDIR_DRIVE = 1
	DEMO_OUTSIDE_GAME = 2
	LAUNCHOPT = 3

class Play(BaseDialog):
	"""
	Dialog that reads and displays TF2 launch arguments and steam profile
	information, offers ability to change those and launch TF2 with an
	additional command that plays the demo on the game's startup, or
	directly hook HLAE into the game.

	After the dialog is closed:
	`self.result.state` will be SUCCESS if user hit launch, else FAILURE.
	`self.result.data` will be a dict where:
		"game_launched": Whether tf2 was launched (bool)
		"steampath": The text in the steampath entry, may have been
			changed by the user. (str)
		"hlaepath": The text in the hlaepath entry, may have been changed
			by the user. (str)

	Widget state remembering:
		0: HLAE launch checkbox state (bool)
		1: Gototick in launch commands checkbox state (bool)
		2: Selected userprofile (str) (ignored when not existing)
	"""

	REMEMBER_DEFAULT = [False, True, ""]

	def __init__(self, parent, demo_dir, info, cfg, style, remember):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		demo_dir: Demo directory the demo is located in (str)
		info: Information about the demo. (DemoInfo)
		cfg: The program configuration. (dict)
		style: ttk.Style object
		remember: List of arbitrary values. See class docstring for details.
		"""
		super().__init__(parent, "Play demo / Launch TF2...")
		self.demopath = os.path.join(demo_dir, info.demo_name)
		self.info = info
		self._style = style
		self.cfg = cfg

		self.rcon_password_var = tk.StringVar()
		self.user_select_var = tk.StringVar()
		self.gototick_launchcmd_var = tk.BooleanVar()
		self.usehlae_var = tk.BooleanVar()
		self.launch_options_var = tk.StringVar()
		self.launch_commands_var = tk.StringVar()
		self.tick_entry_var = tk.IntVar()

		self.launch_commands = []
		self.users = []

		self.spinner = cycle((chain(
			*(repeat(sign, 100 // CNST.GUI_UPDATE_WAIT) for sign in ("|", "/", "-", "\\")),
		)))
		self.rcon_threadgroup = ThreadGroup(RCONThread, self)
		self.rcon_threadgroup.register_run_always_method_pre(self._rcon_run_always)
		self.rcon_threadgroup.decorate_and_patch(self, self._rcon_after_callback)
		self.animate_spinner = False
		self.rcon_in_queue = queue.Queue()

		self.error_steamdir_invalid = ErrorLabel()
		self.warning_not_in_tf_dir = ErrorLabel()
		self.info_launch_options_not_found = ErrorLabel()

		if self.cfg.rcon_pwd is not None:
			self.rcon_password_var.set(self.cfg.rcon_pwd)

		self.remember = self.validate_and_update_remember(remember)

	def body(self, master):
		"""UI"""
		self.protocol("WM_DELETE_WINDOW", self.done)

		master.grid_columnconfigure((0, 1), weight = 1)

		rcon_labelframe = ttk.LabelFrame(
			master, padding = (10, 8, 10, 8), labelwidget = frmd_label(master, "RCON")
		)
		rcon_password_frame = ttk.Frame(rcon_labelframe, style = "Contained.TFrame")
		rcon_password_label = ttk.Label(
			rcon_password_frame, text = "Password", style = "Contained.TLabel"
		)
		rcon_password_entry = ttk.Entry(
			rcon_password_frame, style = "Contained.TEntry", textvariable = self.rcon_password_var,
			show = "\u25A0"
		)
		self.rcon_connect_button = ttk.Button(
			rcon_labelframe, style = "Contained.TButton",  text = "Connect", command = self._rcon
		)
		rcon_text_frame = ttk.Frame(rcon_labelframe, style = "Contained.TFrame")
		self.rcon_text = TtkText(rcon_text_frame, self._style, height = 4, width = 48)
		rcon_text_scrollbar = ttk.Scrollbar(
			rcon_text_frame, orient = tk.HORIZONTAL, command = self.rcon_text.xview
		)

		play_frame = ttk.LabelFrame(
			master, padding = (10, 8, 10, 8), labelwidget = frmd_label(master, "Play")
		)
		launch_config_frame = ttk.Frame(play_frame, style = "Contained.TFrame")
		user_select_label = ttk.Label(
			launch_config_frame, text = "User profile to get launch options from:",
			style = "Contained.TLabel"
		)
		self.error_steamdir_invalid.label = ttk.Label(launch_config_frame, text = "bad steamdir")
		self.info_launch_options_not_found.label = ttk.Label(
			launch_config_frame, text = "launch options not found"
		)
		self.user_select_combobox = ttk.Combobox(
			launch_config_frame, textvariable = self.user_select_var, state = "readonly"
		)
		self.use_hlae_checkbox = ttk.Checkbutton(
			launch_config_frame, variable = self.usehlae_var, text = "Use HLAE",
			style = "Contained.TCheckbutton"
		)

		arg_region = ttk.Frame(play_frame, style = "Contained.TFrame")
		launch_options_entry = ttk.Entry(
			arg_region, style = "Contained.TEntry", textvariable = self.launch_options_var
		)
		launch_commands_entry = ttk.Entry(
			arg_region, style = "Contained.TEntry", textvariable = self.launch_commands_var,
			state = "readonly"
		)
		self.rcon_send_commands_button = ttk.Button(
			arg_region, style = "Contained.TButton", text = "[RCON] Send Commands",
			state = tk.DISABLED
		)

		bookmark_region = ttk.Frame(play_frame, style = "Contained.TFrame")
		self.tick_mfl = MultiframeList(
			bookmark_region,
			[
				{"name": "Type", "col_id": "col_type"},
				{"name": "Tick", "col_id": "col_tick"},
				{"name": "Value", "col_id": "col_val"},
			],
			selection_type = SELECTION_TYPE.SINGLE,
		)
		self.gototick_launchcmd_checkbox = ttk.Checkbutton(
			bookmark_region, style = "Contained.TCheckbutton",
			text = "Go to tick in launch options?", command = self._update_launch_commands_var,
			variable = self.gototick_launchcmd_var
		)
		self.tick_entry = ttk.Entry(
			bookmark_region, style = "Contained.TEntry", textvariable = self.tick_entry_var
		)
		self.rcon_send_gototick_button = ttk.Button(
			bookmark_region, style = "Contained.TButton", text = "[RCON] Go to tick",
			state = tk.DISABLED
		)

		self.warning_not_in_tf_dir.label = ttk.Label(play_frame, text = "Demo not in tf dir")
		launch_button = ttk.Button(play_frame, text = "Launch TF2", style = "Contained.TButton")

		master.grid_rowconfigure((0, 1), weight = 1)
		master.grid_columnconfigure((0, 1), weight = 1)
		# = RCON frame
		rcon_password_label.grid(row = 0, column = 0, sticky = "w")
		rcon_password_entry.grid(row = 0, column = 1, sticky = "e")
		self.rcon_connect_button.grid(row = 1, column = 0)
		rcon_password_frame.grid(row = 0, column = 0, sticky = "nesw")

		self.rcon_text.grid(row = 0, column = 0, sticky = "nesw")
		rcon_text_scrollbar.grid(row = 1, column = 0, sticky = "ew")
		rcon_text_frame.grid(row = 0, column = 1, rowspan = 2, padx = (5, 0))

		rcon_labelframe.grid(row = 0, column = 0, pady = (0, 5), sticky = "nesw")

		# = Play frame
		play_frame.grid_columnconfigure(0, weight = 1)
		# Launch config region
		launch_config_frame.grid_columnconfigure(1, weight = 1)
		user_select_label.grid(row = 0, column = 0, sticky = "e")
		self.user_select_combobox.grid(row = 0, column = 1, sticky = "ew")
		self.error_steamdir_invalid.set_grid_options(
			row = 1, column = 0, columnspan = 2, sticky = "ew"
		)
		self.info_launch_options_not_found.set_grid_options(
			row = 2, column = 0, columnspan = 2, sticky = "ew"
		)
		self.use_hlae_checkbox.grid(row = 3, column = 0, sticky = "w")
		launch_config_frame.grid(row = 0, column = 0, sticky = "nesw")

		# Launch arg region
		arg_region.grid_columnconfigure(0, weight = 1)
		launch_options_entry.grid(row = 1, column = 0, sticky = "ew")
		launch_commands_entry.grid(row = 2, column = 0, sticky = "ew")
		self.rcon_send_commands_button.grid(row = 2, column = 1, sticky = "e")
		arg_region.grid(row = 1, column = 0, sticky = "nesw")

		# Event tick region
		bookmark_region.grid_columnconfigure(0, weight = 1)
		self.tick_mfl.grid(row = 0, column = 0, rowspan = 3, sticky = "ew")
		self.gototick_launchcmd_checkbox.grid(row = 0, column = 1)
		self.tick_entry.grid(row = 1, column = 1)
		self.rcon_send_gototick_button.grid(row = 2, column = 1)
		bookmark_region.grid(row = 2, column = 0, sticky = "nesw")

		self.warning_not_in_tf_dir.set_grid_options(row = 3, column = 0, sticky = "ew")
		launch_button.grid(row = 4, column = 0)

		play_frame.grid(row = 1, column = 0, pady = (0, 5), sticky = "nesw")

		self.tick_mfl.bind("<<MultiframeSelect>>", lambda _: self._update_launch_commands_var())

		self.rcon_text.insert(tk.END, "Status: Disconnected [.]\n\n\n")
		self.rcon_text.mark_set("status0", "1.8")
		self.rcon_text.mark_set("status1", "1.20")
		self.rcon_text.mark_set("spinner", "1.22")
		self.rcon_text.mark_gravity("status0", tk.LEFT)
		self.rcon_text.mark_gravity("status1", tk.RIGHT)
		self.rcon_text.mark_gravity("spinner", tk.LEFT)
		self.rcon_text.configure(xscrollcommand = rcon_text_scrollbar.set, state = tk.DISABLED)

		events = []
		if self.info.killstreaks is not None:
			events += [("Killstreak", t, v) for v, t in self.info.killstreaks]
		if self.info.bookmarks is not None:
			events += [("Bookmark", t, v) for v, t in self.info.bookmarks]
		events.sort(key = lambda x: x[1])
		data = {"col_type": [], "col_tick": [], "col_val": []}
		for type, tick, val in events:
			data["col_type"].append(type)
			data["col_tick"].append(tick)
			data["col_val"].append(val)
		self.tick_mfl.set_data(data)
		self.tick_mfl.format()

		# dir_sel_lblfrm = ttk.LabelFrame(
		# 	master, padding = (10, 8, 10, 8), labelwidget = frmd_label(master, "Paths")
		# )
		# dir_sel_lblfrm.grid_columnconfigure(0, weight = 1)
		# ds_widgetframe = ttk.Frame(dir_sel_lblfrm, style = "Contained.TFrame")
		# ds_widgetframe.grid_columnconfigure(1, weight = 1)
		# for i, j in enumerate((
		# 	("Steam:", self.steamdir_var), ("HLAE:", self.hlaedir_var),
		# )):
		# 	dir_label = ttk.Label(ds_widgetframe, style = "Contained.TLabel", text = j[0])
		# 	dir_entry = ttk.Entry(ds_widgetframe, state = "readonly", textvariable = j[1])
		# 	def tmp_handler(self = self, var = j[1]):
		# 		return self._sel_dir(var)
		# 	dir_btn = ttk.Button(
		# 		ds_widgetframe, style = "Contained.TButton", command = tmp_handler,
		# 		text = "Change path..."
		# 	)
		# 	dir_label.grid(row = i, column = 0)
		# 	dir_entry.grid(row = i, column = 1, sticky = "ew")
		# 	dir_btn.grid(row = i, column = 2, padx = (3, 0))
		# self.error_steamdir_invalid = ttk.Label(
		# 	dir_sel_lblfrm, anchor = tk.N, justify = tk.CENTER, style = "Error.Contained.TLabel",
		# 	text = "Getting steam users failed! Please select the root folder called " \
		# 		"\"Steam\".\nEventually check for permission conflicts."
		# )
		# self.warning_steamdir_mislocated = ttk.Label(
		# 	dir_sel_lblfrm, anchor = tk.N, style = "Warning.Contained.TLabel",
		# 	text = "The queried demo and the Steam directory are on seperate drives."
		# )

		# userselectframe = ttk.LabelFrame(
		# 	master, padding = (10, 8, 10, 8),
		# 	labelwidget = frmd_label(master, "Select user profile if needed")
		# )
		# userselectframe.grid_columnconfigure(0, weight = 1)
		# self.info_launchoptions_not_found = ttk.Label(
		# 	userselectframe, anchor = tk.N, style = "Info.Contained.TLabel",
		# 	text = "Launch configuration not found, it likely does not exist."
		# )
		# self.user_select_combobox = ttk.Combobox(
		# 	userselectframe, textvariable = self.user_select_var, state = "readonly"
		# )
		# # Once changed, observer callback triggered by self.user_select_var

		# launchoptionsframe = ttk.LabelFrame(
		# 	master, padding = (10, 8, 10, 8), labelwidget = frmd_label(master, "Launch options")
		# )
		# launchoptionsframe.grid_columnconfigure(0, weight = 1)
		# launchoptwidgetframe = ttk.Frame(
		# 	launchoptionsframe, borderwidth = 4, relief = tk.RAISED, padding = (5, 4, 5, 4)
		# )
		# launchoptwidgetframe.grid_columnconfigure((1, ), weight = 10)
		# self.head_args_lbl = ttk.Label(launchoptwidgetframe, text = "[...]/hl2.exe -steam -game tf")
		# self.launchoptionsentry = ttk.Entry(launchoptwidgetframe, textvariable = self.launch_options_var)
		# pluslabel = ttk.Label(launchoptwidgetframe, text = "+")
		# self.demo_play_arg_entry = ttk.Entry(
		# 	launchoptwidgetframe, state = "readonly", textvariable = self.playdemoarg
		# )
		# self.end_q_mark_label = ttk.Label(launchoptwidgetframe, text = "")
		# #launchoptwidgetframe.grid_propagate(False)

		# self.use_hlae_checkbox = ttk.Checkbutton(
		# 	launchoptionsframe, variable = self.usehlae_var, text = "Launch using HLAE",
		# 	style = "Contained.TCheckbutton", command = self._toggle_hlae_cb
		# )

		# self.warning_not_in_tf_dir = ttk.Label(
		# 	launchoptionsframe, anchor = tk.N, style = "Warning.Contained.TLabel",
		# 	text = "The demo can not be played as it is not in Team Fortress' file system (/tf)"
		# )
		# # self.demo_play_arg_entry.config(width = len(self.playdemoarg.get()) + 2)

		# rconlabelframe = ttk.LabelFrame(
		# 	master, padding = (10, 8, 10, 8), labelwidget = frmd_label(master, "RCON")
		# )
		# rconlabelframe.grid_columnconfigure(1, weight = 1)
		# self.rcon_btn = ttk.Button(
		# 	rconlabelframe, text = "Send command", command = self._rcon,
		# 	width = 15, style = "Centered.TButton"
		# )
		# self.rcon_btn.grid(row = 0, column = 0)
		# self.rcon_txt = TtkText(
		# 	rconlabelframe, self._style, height = 4, width = 48, wrap = tk.CHAR
		# )
		# rcon_text_scrollbar = ttk.Scrollbar(
		# 	rconlabelframe, orient = tk.HORIZONTAL, command = self.rcon_txt.xview
		# )
		# self.rcon_txt.insert(tk.END, "Status: [.]\n\n\n")
		# self.rcon_txt.mark_set("spinner", "1.9")
		# self.rcon_txt.mark_gravity("spinner", tk.LEFT)
		# self.rcon_txt.configure(xscrollcommand = rcon_text_scrollbar.set, state = tk.DISABLED)
		# self.rcon_txt.grid(row = 0, column = 1, sticky = "news", padx = (5, 0))
		# rcon_text_scrollbar.grid(row = 1, column = 1, sticky = "ew", padx = (5, 0))

		# # grid start
		# # dir selection widgets are already gridded
		# ds_widgetframe.grid(sticky = "news")
		# self.error_steamdir_invalid.grid()
		# self.warning_steamdir_mislocated.grid()
		# dir_sel_lblfrm.grid(columnspan = 2, pady = 5, sticky = "news")

		# self.user_select_combobox.grid(sticky = "we")
		# self.info_launchoptions_not_found.grid()
		# userselectframe.grid(columnspan = 2, pady = 5, sticky = "news")

		# self.head_args_lbl.grid(row = 0, column = 0, columnspan = 3, sticky = "news")
		# self.launchoptionsentry.grid(row = 1, column = 0, columnspan = 3, sticky = "news")
		# pluslabel.grid(row = 2, column = 0)
		# self.demo_play_arg_entry.grid(row = 2, column = 1, sticky = "news")
		# self.end_q_mark_label.grid(row = 2, column = 2)
		# launchoptwidgetframe.grid(sticky = "news")
		# self.use_hlae_checkbox.grid(sticky = "w", pady = (5, 0), ipadx = 4)
		# self.warning_not_in_tf_dir.grid()
		# launchoptionsframe.grid(columnspan = 2, pady = (5, 10), sticky = "news")

		# rconlabelframe.grid(columnspan = 2, pady = (5, 10), sticky = "news")

		# self.btconfirm = ttk.Button(master, text = "Launch!", command = lambda: self.done(True))
		# self.btcancel = ttk.Button(master, text = "Cancel", command = self.done)

		# self.btconfirm.grid(row = 4, padx = (0, 3), sticky = "news")
		# self.btcancel.grid(row = 4, column = 1, padx = (3, 0), sticky = "news")

		self.user_select_var.trace("w", self.on_user_select)
		self._ini_load_users(self.remember[2])

		self.usehlae_var.set(self.remember[0])
		self.gototick_launchcmd_var.set(self.remember[1])

		del self.remember

		self._update_launch_commands_var()

	def get_user_data(self, user_dir):
		"""
		Retrieves a user's information.
		Returns a two-element tuple where [0] is the user's name, safe for
		display in tkinter and [1] is the user's TF2 launch configuration.

		If an error getting the respective user data occurs, the last
		two values may be None. Does not set any error states.
		"""
		cnf_file_path = os.path.join(
			self.cfg.steam_path, CNST.STEAM_CFG_PATH0, user_dir, CNST.STEAM_CFG_PATH1
		)
		try:
			with open(cnf_file_path, encoding = "utf-8") as h:
				vdf_data = vdf.load(h)
			launch_options = follow_vdf_keys(vdf_data, CNST.STEAM_CFG_LAUNCH_OPTIONS, False)
			username = follow_vdf_keys(vdf_data, CNST.STEAM_CFG_USER_NAME)
			return (
				None if username is None else tk_secure_str(username),
				launch_options,
			)
		except (OSError, PermissionError, FileNotFoundError, KeyError, SyntaxError):
			return (None, None)

	def _ini_load_users(self, set_if_present = None):
		"""
		Lists the users based on the passed config's steam directory,
		saves them in `self.users` and configures the `user_select_var`
		with either the user associated with the passed in
		`set_if_present` directory or, if it is `None`, the first user
		present in `self.users`, or `""` if `self.users` is empty.
		Sets errstates.
		"""
		try:
			raw_list = os.listdir(os.path.join(self.cfg.steam_path, CNST.STEAM_CFG_PATH0))
		except (OSError, PermissionError, FileNotFoundError):
			self.error_steamdir_invalid.set(True)
		else:
			self.error_steamdir_invalid.set(False)
			self.users = [User(x, *self.get_user_data(x)) for x in raw_list]

		self.users_str = [user.get_display_str() for user in self.users]
		self.user_select_combobox.config(values = self.users_str)

		tgt = self.users[0].dir_name if self.users else ""
		if set_if_present is not None:
			for display_str, user in zip(self.users_str, self.users):
				if set_if_present == user.dir_name:
					tgt = display_str
					break

		self.user_select_var.set(tgt)

	def on_user_select(self, *_):
		"""
		Callback to retrieve launch options and update error labels.
		"""
		try:
			# For some reason, self.user_select_combobox.current()
			# returns -1 if called right at the start here despite
			# all values being present. Hacky alternative through
			# python
			user_idx = self.users_str.index(self.user_select_var.get())
		except ValueError:
			# Should only happen when the directory is empty/bad or
			# someone messed with the config.
			return

		user = self.users[user_idx]
		self.launch_options_var.set(user.launch_opt or "")
		self.info_launch_options_not_found.set(user.launch_opt is None)

	def _update_launch_commands_var(self):
		try:
			shortdemopath = os.path.relpath(
				self.demopath, os.path.join(self.cfg.steam_path, CNST.TF2_HEAD_PATH)
			)
			if ".." in os.path.normpath(shortdemopath).split(os.sep):
				raise ValueError("Can't exit game directory")
			self.launch_commands = ["+playdemo", shortdemopath]
		except ValueError:
			self.warning_not_in_tf_dir.set(True)
			self.launch_commands = []

		tick = 0
		if self.tick_mfl.selection:
			tick = self.tick_mfl.get_cell("col_tick", next(iter(self.tick_mfl.selection)))
		if self.gototick_launchcmd_var.get():
			self.launch_commands += ["+demo_gototick", str(tick)]
		self.tick_entry_var.set(tick)
		self.launch_commands_var.set(" ".join(self.launch_commands))

	def _rcon_txt_set_line(self, n, content):
		"""
		Sets line n (0-2) of rcon txt widget to content.
		"""
		self.rcon_text.replace(f"{n + 2}.0", f"{n + 2}.{tk.END}", content)

	def _rcon(self):
		self.animate_spinner = True
		self.rcon_connect_button.configure(text = "Cancel", command = self._rcon_cancel)
		with self.rcon_text:
			for i in range(3):
				self._rcon_txt_set_line(i, "")
		self.rcon_threadgroup.start_thread(
			queue_in = self.rcon_in_queue,
			password = self.cfg.rcon_pwd,
			port = self.cfg.rcon_port,
		)

	def _rcon_cancel(self):
		self.animate_spinner = True
		self.rcon_threadgroup.join_thread()

	def _rcon_after_callback(self, sig, *args):
		if sig.is_finish_signal():
			self.animate_spinner = False
			self.rcon_connect_button.configure(text = "Connect", command = self._rcon)
			with self.rcon_text:
				self.rcon_text.replace("status0", "status1", "Disconnected")
				self.rcon_text.replace("spinner", "spinner + 1 chars", ".")
				if sig is THREADSIG.ABORTED:
					for i in range(3):
						self._rcon_txt_set_line(i, "")
			return THREADGROUPSIG.FINISHED
		elif sig is THREADSIG.CONNECTED:
			self.animate_spinner = False
			self.rcon_connect_button.configure(text = "Disconnect", command = self._rcon_cancel)
			with self.rcon_text:
				self.rcon_text.replace("status0", "status1", "Connected")
				self.rcon_text.replace("spinner", "spinner + 1 chars", ".")
		elif sig is THREADSIG.INFO_IDX_PARAM:
			with self.rcon_text:
				self._rcon_txt_set_line(args[0], args[1])
		return THREADGROUPSIG.CONTINUE

	def _rcon_run_always(self):
		if self.animate_spinner:
			with self.rcon_text:
				self.rcon_text.delete("spinner", "spinner + 1 chars")
				self.rcon_text.insert("spinner", next(self.spinner))

	def _rcon_on_finish(self):
		pass

	def done(self, launch = False):
		self._rcon_cancel()
		self.result.state = DIAGSIG.SUCCESS if launch else DIAGSIG.FAILURE
		if launch:
			user_args = self.launch_options_var.get().split()
			tf2_launch_args = CNST.TF2_LAUNCHARGS + user_args + self.launch_commands
			if self.usehlae_var.get():
				tf2_launch_args.extend(CNST.HLAE_ADD_TF2_ARGS)
				executable = os.path.join(self.hlaedir_var.get(), CNST.HLAE_EXE)
				launch_args = CNST.HLAE_LAUNCHARGS0.copy() # hookdll required
				launch_args.append(os.path.join(self.hlaedir_var.get(), CNST.HLAE_HOOK_DLL))
				# hl2 exe path required
				launch_args.extend(CNST.HLAE_LAUNCHARGS1)
				launch_args.append(os.path.join(self.steamdir_var.get(), CNST.TF2_EXE_PATH))
				launch_args.extend(CNST.HLAE_LAUNCHARGS2)
				# has to be supplied as string
				launch_args.append(" ".join(tf2_launch_args))
			else:
				executable = os.path.join(self.steamdir_var.get(), CNST.TF2_EXE_PATH)
				launch_args = tf2_launch_args
			final_launchoptions = [executable] + launch_args

			try:
				subprocess.Popen(final_launchoptions)
				#-steam param may cause conflicts when steam is not open but what do I know?
				self.result.data["game_launched"] = True
			except FileNotFoundError:
				self.result.data["game_launched"] = False
				tk_msg.showerror("Demomgr - Error", "Executable not found.", parent = self)
			except (OSError, PermissionError) as error:
				self.result.data["game_launched"] = False
				tk_msg.showerror(
					"Demomgr - Error", f"Could not access executable :\n{error}", parent = self
				)

		user_idx = self.user_select_combobox.current()
		self.result.remember = [
			self.usehlae_var.get(),
			self.gototick_launchcmd_var.get(),
			self.users[user_idx].dir_name if user_idx != -1 else None
		]

		self.destroy()
