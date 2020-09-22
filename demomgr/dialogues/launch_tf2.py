import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg

import os
from itertools import chain, cycle, repeat
import subprocess

import vdf

from demomgr.dialogues._base import BaseDialog
from demomgr.dialogues._diagresult import DIAGSIG

from demomgr import constants as CNST
from demomgr.helper_tk_widgets import TtkText
from demomgr.helpers import (frmd_label, tk_secure_str)
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, RCONThread

class ERR_IDX:
	STEAMDIR = 0
	STEAMDIR_DRIVE = 1
	DEMO_OUTSIDE_GAME = 2
	LAUNCHOPT = 3

class LaunchTF2(BaseDialog):
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
		1: Selected userprofile (str) (ignored when not existing)
	"""

	REMEMBER_DEFAULT = [False, ""]

	def __init__(self, parent, demopath, cfg, style, remember):
		"""
		parent: Parent widget, should be a `Tk` or `Toplevel` instance.
		demopath: Absolute file path to the demo to be played. (str)
		cfg: The program configuration. (dict)
		style: ttk.Style object
		remember: List of arbitrary values. See class docstring for details.
		"""
		super().__init__(parent, "Play demo / Launch TF2...")
		self.demopath = demopath
		self.steamdir_var = tk.StringVar()
		self.steamdir_var.set(cfg["steampath"])
		self.hlaedir_var = tk.StringVar()
		self.hlaedir_var.set(cfg["hlaepath"])
		self.usehlae_var = tk.BooleanVar()
		self.playdemoarg = tk.StringVar()
		self.userselectvar = tk.StringVar()
		self.launchoptionsvar = tk.StringVar()

		self._style = style
		self.cfg = cfg

		self.spinneriter = cycle((chain(
			*(repeat(sign, 100 // CNST.GUI_UPDATE_WAIT) for sign in ("|", "/", "-", "\\")),
		)))
		self.rcon_threadgroup = ThreadGroup(RCONThread, self)
		self.rcon_threadgroup.register_run_always_method(self._rcon_after_run_always)
		self.rcon_threadgroup.decorate_and_patch(self, self._rcon_after_callback)

		self.errstates = [False for _ in range(4)]
		# 0: Bad config/steamdir, 1: Steamdir on bad drive, 2: Demo outside /tf/,
		# 3: No launchoptions,

		u_r = self.validate_and_update_remember(remember)
		self.usehlae_var.set(u_r[0])
		self.remember_1_hackish = u_r[1] # Used at the end of body()

		self.shortdemopath = ""

	def body(self, master):
		"""UI"""
		self.protocol("WM_DELETE_WINDOW", self.done)

		master.grid_columnconfigure((0, 1), weight = 1)

		dir_sel_lblfrm = ttk.LabelFrame(master, padding = (10, 8, 10, 8), 
			labelwidget = frmd_label(master, "Paths"))
		dir_sel_lblfrm.grid_columnconfigure(0, weight = 1)
		ds_widgetframe = ttk.Frame(dir_sel_lblfrm, style = "Contained.TFrame")
		ds_widgetframe.grid_columnconfigure(1, weight = 1)
		for i, j in enumerate((("Steam:", self.steamdir_var),
					("HLAE:", self.hlaedir_var))):
			dir_label = ttk.Label(ds_widgetframe, style = "Contained.TLabel",
				text = j[0])
			dir_entry = ttk.Entry(ds_widgetframe, state = "readonly",
				textvariable = j[1])
			def tmp_handler(self = self, var = j[1]):
				return self._sel_dir(var)
			dir_btn = ttk.Button(ds_widgetframe,
				style = "Contained.TButton", command = tmp_handler,
				text = "Change path...")
			dir_label.grid(row = i, column = 0)
			dir_entry.grid(row = i, column = 1, sticky = "ew")
			dir_btn.grid(row = i, column = 2, padx = (3, 0))
		self.error_steamdir_invalid = ttk.Label(dir_sel_lblfrm, anchor = tk.N,
			justify = tk.CENTER, style = "Error.Contained.TLabel",
			text = ("Getting steam users failed! Please select the root folder"
			" called \"Steam\".\nEventually check for permission conflicts.") )
		self.warning_steamdir_mislocated = ttk.Label(dir_sel_lblfrm,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("The queried demo and the Steam directory are on"
			" seperate drives."))

		userselectframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8),
			labelwidget = frmd_label(master, "Select user profile if needed"))
		userselectframe.grid_columnconfigure(0, weight = 1)
		self.info_launchoptions_not_found = ttk.Label(userselectframe,
			anchor = tk.N, style = "Info.Contained.TLabel", text = ("Launch "
			"configuration not found, it likely does not exist.") )
		self.userselectbox = ttk.Combobox(userselectframe,
			textvariable = self.userselectvar, state = "readonly")
		# Once changed, observer callback triggered by self.userselectvar

		launchoptionsframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8),
			labelwidget = frmd_label(master, "Launch options:"))
		launchoptionsframe.grid_columnconfigure(0, weight = 1)
		launchoptwidgetframe = ttk.Frame(launchoptionsframe, borderwidth = 4,
			relief = tk.RAISED, padding = (5, 4, 5, 4), )
		launchoptwidgetframe.grid_columnconfigure((1, ), weight = 10)
		self.head_args_lbl = ttk.Label(launchoptwidgetframe,
			text = "[...]/hl2.exe -steam -game tf")
		self.launchoptionsentry = ttk.Entry(launchoptwidgetframe,
			textvariable = self.launchoptionsvar)
		pluslabel = ttk.Label(launchoptwidgetframe, text = "+")
		self.demo_play_arg_entry = ttk.Entry(launchoptwidgetframe,
			state = "readonly", textvariable = self.playdemoarg)
		self.end_q_mark_label = ttk.Label(launchoptwidgetframe, text = "")
		#launchoptwidgetframe.grid_propagate(False)

		self.use_hlae_checkbox = ttk.Checkbutton(launchoptionsframe,
			variable = self.usehlae_var, text = "Launch using HLAE",
			style = "Contained.TCheckbutton", command = self._toggle_hlae_cb)

		self.warning_not_in_tf_dir = ttk.Label(launchoptionsframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("The demo can not be played as it is not in"
			" Team Fortress\' file system (/tf/)"))
		# self.demo_play_arg_entry.config(width = len(self.playdemoarg.get()) + 2)

		rconlabelframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8),
			labelwidget = frmd_label(master, "RCON"))
		rconlabelframe.grid_columnconfigure(1, weight = 1)
		self.rcon_btn = ttk.Button(rconlabelframe, text = "Send command", command = self._rcon,
			width = 15, style = "Centered.TButton")
		self.rcon_btn.grid(row = 0, column = 0)
		self.rcon_txt = TtkText(rconlabelframe, self._style, height = 4, width = 42, wrap = tk.CHAR)
		self.rcon_txt.insert(tk.END, "Status: [.]\n\n\n")
		self.rcon_txt.mark_set("spinner", "1.9")
		self.rcon_txt.mark_gravity("spinner", tk.LEFT)
		#self.rcon_txt.configure(state = tk.DISABLED)
		self.rcon_txt.grid(row = 0, column = 1, sticky = "news", padx = (5, 0))

		# grid start
		# dir selection widgets are already gridded
		ds_widgetframe.grid(sticky = "news")
		self.error_steamdir_invalid.grid()
		self.warning_steamdir_mislocated.grid()
		dir_sel_lblfrm.grid(columnspan = 2, pady = 5, sticky = "news")

		self.userselectbox.grid(sticky = "we")
		self.info_launchoptions_not_found.grid()
		userselectframe.grid(columnspan = 2, pady = 5, sticky = "news")

		self.head_args_lbl.grid(row = 0, column = 0, columnspan = 3, sticky = "news")
		self.launchoptionsentry.grid(row = 1, column = 0, columnspan = 3, sticky = "news")
		pluslabel.grid(row = 2, column = 0)
		self.demo_play_arg_entry.grid(row = 2, column = 1, sticky = "news")
		self.end_q_mark_label.grid(row = 2, column = 2)
		launchoptwidgetframe.grid(sticky = "news")
		self.use_hlae_checkbox.grid(sticky = "w", pady = (5, 0), ipadx = 4)
		self.warning_not_in_tf_dir.grid()
		launchoptionsframe.grid(columnspan = 2, pady = (5, 10), sticky = "news")

		rconlabelframe.grid(columnspan = 2, pady = (5, 10), sticky = "news")

		self.btconfirm = ttk.Button(master, text = "Launch!", command = lambda: self.done(True))
		self.btcancel = ttk.Button(master, text = "Cancel", command = self.done)

		self.btconfirm.grid(row = 4, padx = (0, 3), sticky = "news")
		self.btcancel.grid(row = 4, column = 1, padx = (3, 0), sticky = "news")

		self._load_users_ui()
		self.userselectvar.trace("w", self.userchange)
		for i, t in enumerate(zip(self.users, self.users_str)):
			if self.remember_1_hackish == t[0][0]:
				self.userselectbox.current(i)
				del self.remember_1_hackish
				break
		else:
			if self.users:
				self.userselectbox.current(0)

		self._toggle_hlae_cb()

	def _showerrs(self):
		"""
		Go through all error conditions and update their respective error
		labels.
		"""
		for i, label in enumerate((
			self.error_steamdir_invalid,
			self.warning_steamdir_mislocated,
			self.warning_not_in_tf_dir,
			self.info_launchoptions_not_found,
		)):
			if self.errstates[i]:
				label.grid()
			else:
				label.grid_forget()

	def getusers(self):
		"""
		Retrieve users from the current steam directory. If vdf module is
		present, returns a list of tuples where
		([FOLDER_NAME], [USER_NAME]); if an error getting the user name
		occurs, the username will be None.

		Executed once by body(), by _sel_dir(), and used to insert value
		into self.userselectvar.
		"""
		toget = os.path.join(self.steamdir_var.get(), CNST.STEAM_CFG_PATH0)
		try:
			users = os.listdir(toget)
		except (OSError, PermissionError, FileNotFoundError):
			self.errstates[ERR_IDX.STEAMDIR] = True
			return []
		for index, user in enumerate(users):
			try:
				cnf_file = os.path.join(toget, user, CNST.STEAM_CFG_PATH1)
				with open(cnf_file, encoding = "utf-8") as h:
					vdfdata = vdf.load(h)
					username = eval(f"vdfdata{CNST.STEAM_CFG_USER_NAME}")
				username = tk_secure_str(username)
				users[index] = (users[index], username)
			except (OSError, PermissionError, FileNotFoundError, KeyError,
					SyntaxError):
				users[index] = (users[index], None)
		self.errstates[ERR_IDX.STEAMDIR] = False
		return users

	def _getlaunchoptions(self):
		try:
			tmp = self.userselectbox.current()
			if tmp == -1:
				raise KeyError("Bad or empty (?) steam folder")
			user_id = self.users[tmp][0]
			with open(os.path.join(self.steamdir_var.get(),
					CNST.STEAM_CFG_PATH0, user_id,
					CNST.STEAM_CFG_PATH1), encoding = "utf-8") as h:
				subelem = vdf.load(h)
			for i in CNST.LAUNCHOPTIONSKEYS:
				if i in subelem:
					subelem = subelem[i]
				elif i.lower() in subelem:
					subelem = subelem[i.lower()]
				else:
					raise KeyError("Could not find launch options in vdf.")
			self.errstates[ERR_IDX.LAUNCHOPT] = False
			return subelem
		except (KeyError, FileNotFoundError, OSError, PermissionError,
				SyntaxError) as e: #SyntaxError raised by vdf module
			self.errstates[ERR_IDX.LAUNCHOPT] = True
			return ""

	def _sel_dir(self, variable): #Triggered by user clicking on the Dir choosing btn
		"""
		Opens up a file selection dialog. If the changed variable was the
		steam dir one, updates related widgets.
		"""
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		variable.set(sel)
		if variable != self.steamdir_var:
			return
		self._load_users_ui()

	def _load_users_ui(self, init = False):
		"""
		Get users, store them in `self.users`, update related widgets.
		Also creates a list of strings as inserted into the combobox,
		stored in `self.users_str`

		init: If set to True, will not touch some interface elements
			which may not exist during initialization.
		"""
		self.users = self.getusers()
		self.users_str = ["{}{}".format(t[0],
			(" - " + t[1]) if t[1] is not None else "") for t in self.users]
		self.userselectbox.config(values = self.users_str)
		if self.users:
			self.userselectbox.current(0)
		else:
			self.userselectvar.set("") # if this is not the call in __init__,
				# will trigger self.userchange
		self._constructshortdemopath()
		self._showerrs()

	def _toggle_hlae_cb(self):
		"""Changes some labels."""
		if self.usehlae_var.get():
			self.head_args_lbl.configure(text = "[...]/hlae.exe [...] "
				"-cmdLine \" -steam -game tf -insecure +sv_lan 1")
			self.end_q_mark_label.configure(text = '"')
		else:
			self.head_args_lbl.configure(text = "[...]/hl2.exe -steam -game tf")
			self.end_q_mark_label.configure(text = "")

	def userchange(self, *_): # Triggered by observer on combobox variable.
		"""Callback to retrieve launch options and update error labels."""
		launchopt = self._getlaunchoptions()
		self.launchoptionsvar.set(launchopt)
		self._showerrs()

	def _constructshortdemopath(self):
		try:
			self.shortdemopath = os.path.relpath(self.demopath,
				os.path.join(self.steamdir_var.get(), CNST.TF2_HEAD_PATH))
			self.errstates[ERR_IDX.STEAMDIR_DRIVE] = False
		except ValueError:
			self.shortdemopath = ""
			self.errstates[ERR_IDX.STEAMDIR_DRIVE] = True
			self.errstates[ERR_IDX.DEMO_OUTSIDE_GAME] = True
		if ".." in self.shortdemopath:
			self.errstates[ERR_IDX.DEMO_OUTSIDE_GAME] = True
		else:
			self.errstates[ERR_IDX.DEMO_OUTSIDE_GAME] = False
		self.playdemoarg.set("playdemo " + self.shortdemopath)

	def _rcon_txt_set_line(self, n, content):
		"""
		Set line n (0-2) of rcon txt widget to content.
		"""
		self.rcon_txt.delete(f"{n + 2}.0", f"{n + 2}.{tk.END}")
		self.rcon_txt.insert(f"{n + 2}.0", content)

	def _rcon(self):
		self.rcon_btn.configure(text = "Cancel", command = self._cancel_rcon)
		self.rcon_txt.configure(state = tk.NORMAL)
		for i in range(3):
			self._rcon_txt_set_line(i, "")
		self.rcon_txt.configure(state = tk.DISABLED)
		self.rcon_threadgroup.start_thread(
			command = f"playdemo {self.shortdemopath}",
			password = self.cfg["rcon_pwd"],
			port = self.cfg["rcon_port"],
		)

	def _cancel_rcon(self):
		self.rcon_threadgroup.join_thread()

	def _rcon_after_callback(self, queue_elem):
		if queue_elem[0] < 0x100: # Finish
			self.rcon_btn.configure(text = "Send command", command = self._rcon)
			self.rcon_txt.configure(state = tk.NORMAL)
			self.rcon_txt.delete("spinner", "spinner + 1 chars")
			self.rcon_txt.insert("spinner", ".")
			self.rcon_txt.configure(state = tk.DISABLED)
			return THREADGROUPSIG.FINISHED
		elif queue_elem[0] == THREADSIG.INFO_IDX_PARAM:
			self.rcon_txt.configure(state = tk.NORMAL)
			self._rcon_txt_set_line(queue_elem[1], queue_elem[2])
			self.rcon_txt.configure(state = tk.DISABLED)
		return THREADGROUPSIG.CONTINUE

	def _rcon_after_run_always(self):
		self.rcon_txt.configure(state = tk.NORMAL)
		self.rcon_txt.delete("spinner", "spinner + 1 chars")
		self.rcon_txt.insert("spinner", next(self.spinneriter))
		self.rcon_txt.configure(state = tk.DISABLED)

	def done(self, launch=False):
		self._cancel_rcon()
		self.result.state = DIAGSIG.SUCCESS if launch else DIAGSIG.FAILURE
		if launch:
			USE_HLAE = self.usehlae_var.get()
			user_args = self.launchoptionsvar.get().split()
			tf2_launch_args = CNST.TF2_LAUNCHARGS + user_args + \
				["+playdemo", self.shortdemopath] # args for hl2.exe
			if USE_HLAE:
				tf2_launch_args.extend(CNST.HLAE_ADD_TF2_ARGS)
				executable = os.path.join(self.hlaedir_var.get(), CNST.HLAE_EXE)
				launch_args = CNST.HLAE_LAUNCHARGS0.copy() # hookdll required
				launch_args.append(os.path.join(self.hlaedir_var.get(),
					CNST.HLAE_HOOK_DLL))
				launch_args.extend(CNST.HLAE_LAUNCHARGS1) # hl2 exe path required
				launch_args.append(os.path.join(self.steamdir_var.get(),
					CNST.TF2_EXE_PATH))
				launch_args.extend(CNST.HLAE_LAUNCHARGS2)
				launch_args.append(" ".join(tf2_launch_args)) # has to be supplied as string
			else:
				executable = os.path.join(self.steamdir_var.get(), CNST.TF2_EXE_PATH)
				launch_args = tf2_launch_args
			final_launchoptions = [executable] + launch_args

			self.result.data = {"steampath": self.steamdir_var.get(), 
				"hlaepath": self.hlaedir_var.get()}

			try:
				subprocess.Popen(final_launchoptions)
				#-steam param may cause conflicts when steam is not open but what do I know?
				self.result.data["game_launched"] = True
			except FileNotFoundError:
				self.result.data["game_launched"] = False
				tk_msg.showerror("Demomgr - Error", "Executable not found.", parent = self)
			except (OSError, PermissionError) as error:
				self.result.data["game_launched"] = False
				tk_msg.showerror("Demomgr - Error",
					"Could not access executable :\n{}".format(str(error)), parent = self)

		self.result.remember = [self.usehlae_var.get(),
			self.users[self.userselectbox.current()][0] if self.userselectbox.current() != -1 else ""]

		self.destroy()
