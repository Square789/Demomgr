import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg

import os
import subprocess

try:
	import vdf
	VDF_PRESENT = True
except ImportError:
	VDF_PRESENT = False

from source.dialogues._base import BaseDialog

from source import constants as CNST
from source.helper_tk_widgets import TtkText
from source.helpers import (frmd_label, tk_secure_str)

class LaunchTF2(BaseDialog):
	'''Dialog that reads and displays TF2 launch arguments and steam profile
	information, offers ability to change those and launch tf2 with an
	additional command that plays the demo on the game's startup.
	'''
	def __init__(self, parent, demopath, cfg):
		'''Args:
		parent: Tkinter widget that is the parent of this dialog.
		demopath: Absolute file path to the demo to be played.
		cfg: The program configuration.
		'''

		self.parent = parent

		self.demopath = demopath
		self.steamdir_var = tk.StringVar()
		self.steamdir_var.set(cfg["steampath"])
		self.hlaedir_var = tk.StringVar()
		self.hlaedir_var.set(cfg["hlaepath"])
		self.usehlae_var = tk.BooleanVar()

		self.errstates = [False, False, False, False, False]
		# 0:Bad config, 1: Steamdir on bad drive, 2: VDF missing,
		# 3:Demo outside /tf/, 4:No launchoptions

		self.playdemoarg = tk.StringVar()
		self.userselectvar = tk.StringVar()
		try:
			self.userselectvar.set(self.getusers()[0])
		except: pass
		self.launchoptionsvar = tk.StringVar()

		self.shortdemopath = ""
		self.__constructshortdemopath()

		super().__init__(self.parent, "Play demo / Launch TF2...")

	def body(self, master):
		'''UI'''
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
			relief = tk.RAISED, padding = (5, 4, 5, 4), width = 450,
			height = 50)
		launchoptwidgetframe.grid_columnconfigure((1, 3), weight = 10)
		self.head_args_lbl = ttk.Label(launchoptwidgetframe,
			text = "[...]/hl2.exe -steam -game tf")
		self.launchoptionsentry = ttk.Entry(launchoptwidgetframe,
			textvariable = self.launchoptionsvar)
		pluslabel = ttk.Label(launchoptwidgetframe, text = "+")
		self.demo_play_arg_entry = ttk.Entry(launchoptwidgetframe,
			state = "readonly", textvariable = self.playdemoarg)
		self.end_q_mark_label = ttk.Label(launchoptwidgetframe, text = "")
		launchoptwidgetframe.grid_propagate(False)

		self.use_hlae_checkbox = ttk.Checkbutton(launchoptionsframe,
			variable = self.usehlae_var, text = "Launch using HLAE",
			style = "Contained.TCheckbutton", command = self._toggle_hlae_cb)

		self.warning_vdfmodule = ttk.Label(launchoptionsframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("Please install the vdf module in order to launch TF2 with"
			" your default settings.\n(\"pip install vdf\")"),
			justify = tk.CENTER)

		self.warning_not_in_tf_dir = ttk.Label(launchoptionsframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("The demo can not be played as it is not in"
			" Team Fortress\' file system (/tf/)"))
		# self.demo_play_arg_entry.config(width = len(self.playdemoarg.get()) + 2)

		# grid start
		# dir selection widgets are already gridded
		ds_widgetframe.grid(sticky = "news")
		self.error_steamdir_invalid.grid()
		self.warning_steamdir_mislocated.grid()
		dir_sel_lblfrm.grid(columnspan = 2, pady = 5, sticky = "news")

		self.userselectbox.grid(sticky = "we")
		self.info_launchoptions_not_found.grid()
		userselectframe.grid(columnspan = 2, pady = 5, sticky = "news")

		self.warning_vdfmodule.grid()
		self.head_args_lbl.grid(row = 0, column = 0)
		self.launchoptionsentry.grid(row = 0, column = 1, sticky = "news")
		pluslabel.grid(row = 0, column = 2)
		self.demo_play_arg_entry.grid(row = 0, column = 3, sticky = "news")
		self.end_q_mark_label.grid(row = 0, column = 4)
		launchoptwidgetframe.grid(sticky = "ew")
		self.use_hlae_checkbox.grid(sticky = "w", pady = (5, 0), ipadx = 4)
		self.warning_not_in_tf_dir.grid()
		launchoptionsframe.grid(columnspan = 2, pady = (5, 10), sticky = "news")

		self.btconfirm = ttk.Button(master, text = "Launch!",
			command = lambda: self.done(1))
		self.btcancel = ttk.Button(master, text = "Cancel",
			command = lambda: self.done(0))

		self.btconfirm.grid(padx = (0, 3), sticky = "news")
		self.btcancel.grid(row = 3, column = 1, padx = (3, 0), sticky = "news")

		# initialize some UI components
		users = self.getusers()
		self.userselectbox.config(values = users)
		if users:
			self.userselectvar.set(users[0])

		self.userchange()

		self.__showerrs()
		self._toggle_hlae_cb()
		self.userselectvar.trace("w", self.userchange) # If applied before,
		# method would be triggered and UI elements would be accessed that do not exist yet.

	def __showerrs(self):#NOTE: Could update that, do in case you ever change this dialog
		'''Update all error labels after looking at conditions'''
		if self.errstates[0]:
			self.error_steamdir_invalid.grid()
		else:
			self.error_steamdir_invalid.grid_forget()
		if self.errstates[1]:
			self.warning_steamdir_mislocated.grid()
		else:
			self.warning_steamdir_mislocated.grid_forget()
		if self.errstates[2]:
			self.warning_vdfmodule.grid()
		else:
			self.warning_vdfmodule.grid_forget()
		if self.errstates[3]:
			self.warning_not_in_tf_dir.grid()
		else:
			self.warning_not_in_tf_dir.grid_forget()
		if self.errstates[4]:
			self.info_launchoptions_not_found.grid()
		else:
			self.info_launchoptions_not_found.grid_forget()

	def getusers(self):
		'''Retrieve users from the current steam directory. If vdf module is
		present, returns a list of strings where "[FOLDER_NAME] // [USER_NAME]"
		, if an error getting the user name occurs or if the vdf module is
		missing, only "[FOLDER_NAME]".

		Executed once by body(), by _sel_dir(), and used to insert value
		into self.userselectvar.
		'''
		toget = os.path.join(self.steamdir_var.get(), CNST.STEAM_CFG_PATH0)
		try:
			users = os.listdir(toget)
		except (OSError, PermissionError, FileNotFoundError):
			self.errstates[0] = True
			return []
		if VDF_PRESENT:
			for index, user in enumerate(users):
				try:
					cnf_file = os.path.join(toget, user, CNST.STEAM_CFG_PATH1)
					with open(cnf_file, encoding = "utf-8") as h:
						vdfdata = vdf.load(h)
						username = eval("vdfdata" + CNST.STEAM_CFG_USER_NAME)
					username = tk_secure_str(username)
					users[index] = users[index] + " // " + username
				except (OSError, PermissionError, FileNotFoundError):
					pass
		self.errstates[0] = False
		return users

	def __getlaunchoptions(self):
		if not VDF_PRESENT:
			self.errstates[2] = True
			self.errstates[4] = False
			return ""
		try:
			self.errstates[2] = False
			user_id = self.userselectvar.get().split(" // ")[0]
			with open(os.path.join(self.steamdir_var.get(),
				CNST.STEAM_CFG_PATH0, user_id,
				CNST.STEAM_CFG_PATH1), encoding = "utf-8") as h:
				launchopt = vdf.load(h)
			for i in CNST.LAUNCHOPTIONSKEYS:
				try:
					launchopt = eval("launchopt" + i)
					break
				except KeyError:
					pass
			else: # Loop completed normally --> No break statement encountered -> No key found
				raise KeyError("No launch options key found.")
			self.errstates[4] = False
			return launchopt
		except (KeyError, FileNotFoundError, OSError, PermissionError,
				SyntaxError) as e: #SyntaxError raised by vdf module
			self.errstates[4] = True
			return ""

	def _sel_dir(self, variable): #Triggered by user clicking on the Dir choosing btn
		'''Opens up a file selection dialog. If the changed variable was the
		steam dir one, updates related widgets.
		'''
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		variable.set(sel)
		if variable != self.steamdir_var:
			return
		users = self.getusers()
		self.userselectbox.config(values = users)
		try:
			self.userselectvar.set(users[0])
		except IndexError:
			self.userselectvar.set("") # will trigger self.userchange
		self.__constructshortdemopath()
		# self.demo_play_arg_entry.config(width = len(self.playdemoarg.get()) + 2)
		self.__showerrs()

	def _toggle_hlae_cb(self):
		'''Changes some labels.'''
		if self.usehlae_var.get():
			self.head_args_lbl.configure(text = "[...]/hlae.exe [...] -cmdLine \" -steam -game tf -insecure +sv_lan 1")
			self.end_q_mark_label.configure(text = '"')
		else:
			self.head_args_lbl.configure(text = "[...]/hl2.exe -steam -game tf")
			self.end_q_mark_label.configure(text = "")

	def userchange(self, *_): # Triggered by observer on combobox variable.
		launchopt = self.__getlaunchoptions()
		self.launchoptionsvar.set(launchopt)
		self.__showerrs()

	def __constructshortdemopath(self):
		try:
			self.shortdemopath = os.path.relpath(self.demopath,
				os.path.join(self.steamdir_var.get(), CNST.TF2_HEAD_PATH))
			self.errstates[1] = False
		except ValueError:
			self.shortdemopath = ""
			self.errstates[1] = True
			self.errstates[3] = True
		if ".." in self.shortdemopath:
			self.errstates[3] = True
		else:
			self.errstates[3] = False
		self.playdemoarg.set("playdemo " + self.shortdemopath)

	def done(self, param):
		if param:
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
			try:
				subprocess.Popen(final_launchoptions) #Launch tf2; -steam param may cause conflicts when steam is not open but what do I know?
				self.result = {"success":True, "steampath":self.steamdir_var.get()}
			except FileNotFoundError:
				self.result = {"success":False, "steampath":self.steamdir_var.get()}
				tk_msg.showerror("Demomgr - Error", "Executable not found.", parent = self)
			except (OSError, PermissionError) as error:
				self.result = {"success":False, "steampath":self.steamdir_var.get()}
				tk_msg.showerror("Demomgr - Error",
					"Could not access executable :\n{}".format(str(error)), parent = self)
		self.destroy()
