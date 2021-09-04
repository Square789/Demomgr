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
from demomgr.tk_widgets import PasswordButton, TtkText
from demomgr.helpers import frmd_label, tk_secure_str, int_validator
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
	Dialog that reads and displays TF2 launch arguments and steam
	profile information, offers ability to change those and launch TF2
	with an additional command that plays the demo on the game's
	startup, or directly hook HLAE into the game.

	After the dialog is closed:
		`self.result.state` will be SUCCESS if user hit launch, else
			FAILURE.

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

		self.launch_commands = []
		self.users = []

		self.spinner = cycle(
			chain(*(
				repeat(sign, max(100 // CNST.GUI_UPDATE_WAIT, 1))
				for sign in ("|", "/", "-", "\\")
			))
		)
		self.rcon_threadgroup = ThreadGroup(RCONThread, self)
		self.rcon_threadgroup.register_run_always_method_pre(self._rcon_run_always)
		self.rcon_threadgroup.decorate_and_patch(self, self._rcon_after_callback)
		self.animate_spinner = False
		self.rcon_in_queue = queue.Queue()

		self.error_steamdir_invalid = ErrorLabel()
		self.warning_not_in_tf_dir = ErrorLabel()
		self.info_launch_options_not_found = ErrorLabel()

		self.rcon_password_var.set(self.cfg.rcon_pwd or "")

		self.remember = self.validate_and_update_remember(remember)

	def body(self, master):
		"""UI"""
		self.protocol("WM_DELETE_WINDOW", self.done)

		master.grid_columnconfigure((0, 1), weight = 1)

		rcon_labelframe = ttk.LabelFrame(
			master, padding = (10, 0, 10, 10), labelwidget = frmd_label(master, "RCON")
		)
		rcon_connect_frame = ttk.Frame(rcon_labelframe, style = "Contained.TFrame")
		rcon_password_label = ttk.Label(
			rcon_connect_frame, text = "Password", style = "Contained.TLabel"
		)
		rcon_password_entry = ttk.Entry(
			rcon_connect_frame, style = "Contained.TEntry", textvariable = self.rcon_password_var,
			show = "\u25A0"
		)
		pwd_entry_show_toggle = PasswordButton(rcon_connect_frame, text = "Show")
		self.rcon_connect_button = ttk.Button(
			rcon_connect_frame, style = "Contained.TButton",  text = "Connect",
			command = self._rcon_start
		)
		rcon_text_frame = ttk.Frame(rcon_labelframe, style = "Contained.TFrame")
		self.rcon_text = TtkText(rcon_text_frame, self._style, height = 4, width = 48)
		rcon_text_scrollbar = ttk.Scrollbar(
			rcon_text_frame, orient = tk.HORIZONTAL, command = self.rcon_text.xview
		)

		play_labelframe = ttk.LabelFrame(
			master, padding = (10, 0, 10, 10), labelwidget = frmd_label(master, "Play")
		)
		launch_config_frame = ttk.Frame(play_labelframe, style = "Contained.TFrame")
		user_select_label = ttk.Label(
			launch_config_frame, text = "User profile to get launch options from:",
			style = "Contained.TLabel"
		)
		self.error_steamdir_invalid.label = ttk.Label(
			launch_config_frame, style = "Error.Contained.TLabel",
			text = (
				"Failed listing users, Steam directory is malformed. \n"
				"Make sure you selected the root directory ending in \"Steam\" "
				"in the Settings > Paths section."
			)
		)
		self.info_launch_options_not_found.label = ttk.Label(
			launch_config_frame, style = "Info.Contained.TLabel",
			text = "(No launch options found for this user)"
		)
		self.user_select_combobox = ttk.Combobox(
			launch_config_frame, textvariable = self.user_select_var, state = "readonly"
		)
		use_hlae_checkbox = ttk.Checkbutton(
			launch_config_frame, variable = self.usehlae_var, text = "Use HLAE",
			style = "Contained.TCheckbutton"
		)

		arg_region = ttk.Frame(play_labelframe, style = "Contained.TFrame")
		launch_options_entry = ttk.Entry(
			arg_region, style = "Contained.TEntry", textvariable = self.launch_options_var
		)
		launch_commands_entry = ttk.Entry(
			arg_region, style = "Contained.TEntry", textvariable = self.launch_commands_var,
			state = "readonly"
		)
		self.rcon_send_commands_button = ttk.Button(
			arg_region, style = "Contained.TButton", text = "[RCON] Send launch commands",
			state = tk.DISABLED, command = self._rcon_send_commands
		)

		bookmark_region = ttk.Frame(play_labelframe, style = "Contained.TFrame")
		self.tick_mfl = MultiframeList(
			bookmark_region,
			[
				{"name": "Type", "col_id": "col_type"},
				{"name": "Tick", "col_id": "col_tick"},
				{"name": "Value", "col_id": "col_val"},
			],
			selection_type = SELECTION_TYPE.SINGLE,
			resizable = True,
		)
		tick_options_frame = ttk.Frame(bookmark_region, style = "Contained.TFrame")
		self.gototick_launchcmd_checkbox = ttk.Checkbutton(
			tick_options_frame, style = "Contained.TCheckbutton",
			text = "Go to tick in launch commands?", command = self._update_launch_commands_var,
			variable = self.gototick_launchcmd_var
		)
		int_val_id = master.register(int_validator)
		self.tick_entry = ttk.Entry(
			tick_options_frame, style = "Contained.TEntry",
			validate = "key", validatecommand = (int_val_id, "%S", "%P")
		)
		self.rcon_send_gototick_button = ttk.Button(
			tick_options_frame, style = "Contained.TButton", text = "[RCON] Go to tick",
			state = tk.DISABLED, command = self._rcon_send_gototick
		)

		self.warning_not_in_tf_dir.label = ttk.Label(
			play_labelframe, style = "Warning.Contained.TLabel",
			text = "Demo can not be played as it is not in TF2's filesystem."
		)
		launch_button = ttk.Button(
			play_labelframe, style = "Contained.TButton", text = "Launch TF2",
			command = self._launch
		)

		# the griddening
		master.grid_rowconfigure((0, 1), weight = 1)
		master.grid_columnconfigure(0, weight = 1)

		# = RCON frame
		rcon_labelframe.grid_columnconfigure(0, weight = 1)
		rcon_connect_frame.grid_columnconfigure(1, weight = 1)
		rcon_password_label.grid(row = 0, column = 0, pady = (0, 0), padx = (0, 5), sticky = "w")
		rcon_password_entry.grid(row = 0, column = 1, padx = (0, 5), pady = (0, 5), sticky = "ew")
		pwd_entry_show_toggle.grid(row = 0, column = 2, pady = (0, 5), sticky = "e")

		self.rcon_connect_button.grid(row = 1, column = 0, columnspan = 3, ipadx = 20)
		rcon_connect_frame.grid(row = 0, column = 0, sticky = "ew")

		self.rcon_text.grid(row = 0, column = 0, sticky = "nesw")
		rcon_text_scrollbar.grid(row = 1, column = 0, sticky = "ew")
		rcon_text_frame.grid(row = 0, column = 1, rowspan = 2, padx = (5, 0))

		rcon_labelframe.grid(row = 0, column = 0, pady = (0, 5), sticky = "nesw")

		# = Play frame
		play_labelframe.grid_columnconfigure(0, weight = 1)
		# Launch config region
		launch_config_frame.grid_columnconfigure(1, weight = 1)
		user_select_label.grid(row = 0, column = 0, pady = (0, 5), sticky = "e")
		self.user_select_combobox.grid(row = 0, column = 1, pady = (0, 5), sticky = "ew")
		self.error_steamdir_invalid.set_grid_options(
			row = 1, column = 0, columnspan = 2, pady = (0, 5), sticky = "ew"
		)
		self.info_launch_options_not_found.set_grid_options(
			row = 2, column = 0, columnspan = 2, pady = (0, 5), sticky = "ew"
		)
		use_hlae_checkbox.grid(row = 3, column = 0, ipadx = 2, sticky = "w")
		launch_config_frame.grid(row = 0, column = 0, pady = (0, 5), sticky = "nesw")

		# Launch arg region
		arg_region.grid_columnconfigure(0, weight = 1)
		launch_options_entry.grid(row = 1, column = 0, pady = (0, 5), sticky = "ew")
		launch_commands_entry.grid(row = 2, column = 0, pady = (0, 5), sticky = "ew")
		self.rcon_send_commands_button.grid(
			row = 2, column = 1, padx = (5, 0), pady = (0, 5), sticky = "e"
		)
		arg_region.grid(row = 1, column = 0, sticky = "nesw")

		# Event tick region
		tick_options_frame.grid_columnconfigure(0, weight = 1)
		self.gototick_launchcmd_checkbox.grid(
			row = 0, column = 0, columnspan = 2, pady = (0, 5), sticky = "w"
		)
		self.tick_entry.grid(row = 1, column = 0, padx = (0, 5))
		self.rcon_send_gototick_button.grid(row = 1, column = 1)
		tick_options_frame.grid(row = 0, column = 1)

		bookmark_region.grid_columnconfigure(0, weight = 1)
		self.tick_mfl.grid(row = 0, column = 0, padx = (0, 5), sticky = "ew")
		bookmark_region.grid(row = 2, column = 0, pady = (0, 5), sticky = "nesw")

		self.warning_not_in_tf_dir.set_grid_options(row = 3, column = 0, sticky = "ew")
		launch_button.grid(row = 4, column = 0, ipadx = 40)

		play_labelframe.grid(row = 1, column = 0, sticky = "nesw")

		pwd_entry_show_toggle.bind_to_entry(rcon_password_entry)
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
		except (TypeError, OSError, PermissionError, FileNotFoundError):
			# TypeError for when steam_path is None.
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
		self.launch_commands.clear()
		try:
			shortdemopath = os.path.relpath(
				self.demopath, os.path.join(self.cfg.steam_path, CNST.TF2_HEAD_PATH)
			)
			if ".." in os.path.normpath(shortdemopath).split(os.sep):
				raise ValueError("Can't exit game directory")
			self.launch_commands.append(f"playdemo {shortdemopath}")
		except (TypeError, ValueError):
			# TypeError for when steam_path is None.
			self.warning_not_in_tf_dir.set(True)

		tick = 0
		if self.tick_mfl.selection:
			tick = self.tick_mfl.get_cell("col_tick", self.tick_mfl.get_selection())
		if self.gototick_launchcmd_var.get():
			self.launch_commands.append(f"demo_gototick {str(tick)}")
		self.tick_entry.delete(0, tk.END)
		self.tick_entry.insert(0, str(tick))
		self.launch_commands_var.set(" ".join("+" + cmd for cmd in self.launch_commands))

	def _rcon_txt_set_line(self, n, content):
		"""
		Sets line n (0-2) of rcon txt widget to content.
		"""
		self.rcon_text.replace(f"{n + 2}.0", f"{n + 2}.{tk.END}", content)

	def _rcon_start(self):
		self.animate_spinner = True
		self.rcon_connect_button.configure(text = "Cancel", command = self._rcon_cancel)
		with self.rcon_text:
			for i in range(3):
				self._rcon_txt_set_line(i, "")
		self.rcon_threadgroup.start_thread(
			queue_in = self.rcon_in_queue,
			password = self.rcon_password_var.get(),
			port = self.cfg.rcon_port,
		)

	def _rcon_cancel(self):
		self.animate_spinner = True
		self.rcon_send_commands_button.config(state = tk.DISABLED)
		self.rcon_send_gototick_button.config(state = tk.DISABLED)
		self.rcon_threadgroup.join_thread()

	def _rcon_after_callback(self, sig, *args):
		if sig.is_finish_signal():
			self._rcon_on_finish(sig)
			return THREADGROUPSIG.FINISHED
		elif sig is THREADSIG.CONNECTED:
			self._rcon_on_connect()
		elif sig is THREADSIG.INFO_IDX_PARAM:
			with self.rcon_text:
				self._rcon_txt_set_line(args[0], args[1])
		return THREADGROUPSIG.CONTINUE

	def _rcon_run_always(self):
		if not self.animate_spinner:
			return
		with self.rcon_text:
			self.rcon_text.delete("spinner", "spinner + 1 chars")
			self.rcon_text.insert("spinner", next(self.spinner))

	def _rcon_on_finish(self, sig):
		self.animate_spinner = False
		self.rcon_connect_button.configure(text = "Connect", command = self._rcon_start)
		self.rcon_send_commands_button.config(state = tk.DISABLED)
		self.rcon_send_gototick_button.config(state = tk.DISABLED)
		with self.rcon_text:
			self.rcon_text.replace("status0", "status1", "Disconnected")
			self.rcon_text.replace("spinner", "spinner + 1 chars", ".")
			if sig is not THREADSIG.FAILURE:
				for i in range(3):
					self._rcon_txt_set_line(i, "")

	def _rcon_on_connect(self):
		self.animate_spinner = False
		self.rcon_connect_button.configure(text = "Disconnect")
		self.rcon_send_commands_button.config(state = tk.NORMAL)
		self.rcon_send_gototick_button.config(state = tk.NORMAL)
		with self.rcon_text:
			self.rcon_text.replace("status0", "status1", "Connected")
			self.rcon_text.replace("spinner", "spinner + 1 chars", ".")

	def _rcon_send_commands(self):
		for cmd in self.launch_commands:
			self.rcon_in_queue.put(cmd.encode("utf-8"))

	def _rcon_send_gototick(self):
		if self.tick_entry.get() == "":
			return
		cmd = f"demo_gototick {self.tick_entry.get()}".encode("utf-8")
		self.rcon_in_queue.put(cmd)

	def _launch(self):
		for cond, name in (
			(self.cfg.steam_path is None, "Steam"),
			(self.usehlae_var.get() and self.cfg.hlae_path is None, "HLAE")
		):
			if cond:
				tk_msg.showerror(
					"Demomgr - Error",
					f"{name} path not specified. Please do so in Settings > Paths.",
					parent = self,
				)
				return

		user_args = self.launch_options_var.get().split()
		tf2_launch_args = (
			CNST.TF2_LAUNCHARGS +
			user_args +
			["+" + cmd for cmd in self.launch_commands]
		)
		if self.usehlae_var.get():
			tf2_launch_args.extend(CNST.HLAE_ADD_TF2_ARGS)
			executable = os.path.join(self.cfg.hlae_path, CNST.HLAE_EXE)
			launch_args = CNST.HLAE_LAUNCHARGS0.copy() # hookdll required
			launch_args.append(os.path.join(self.cfg.hlae_path, CNST.HLAE_HOOK_DLL))
			# hl2 exe path required
			launch_args.extend(CNST.HLAE_LAUNCHARGS1)
			launch_args.append(os.path.join(self.cfg.steam_path, CNST.TF2_EXE_PATH))
			launch_args.extend(CNST.HLAE_LAUNCHARGS2)
			# has to be supplied as string
			launch_args.append(" ".join(tf2_launch_args))
		else:
			executable = os.path.join(self.cfg.steam_path, CNST.TF2_EXE_PATH)
			launch_args = tf2_launch_args
		final_launchoptions = [executable] + launch_args

		try:
			subprocess.Popen(final_launchoptions)
			# -steam param may cause conflicts when steam is not open but what do I know?
		except FileNotFoundError:
			tk_msg.showerror("Demomgr - Error", "Executable not found.", parent = self)
		except (OSError, PermissionError) as error:
			tk_msg.showerror(
				"Demomgr - Error",
				f"Could not access executable :\n{error}",
				parent = self
			)

	def done(self):
		self._rcon_cancel()
		self.result.state = DIAGSIG.SUCCESS

		user_idx = self.user_select_combobox.current()
		self.result.remember = [
			self.usehlae_var.get(),
			self.gototick_launchcmd_var.get(),
			self.users[user_idx].dir_name if user_idx != -1 else None
		]

		self.destroy()
