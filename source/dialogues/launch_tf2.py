import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg

import os
import subprocess

from ._base import BaseDialog

from .. import constants as CNST
from ..helper_tk_widgets import TtkText
from ..helpers import (frmd_label)

class LaunchTF2(BaseDialog):
	'''Dialog that reads and displays TF2 launch arguments and steam profile
	information, offers ability to change those and launch tf2 with an
	additional command that plays the demo on the game's startup.
	'''
	def __init__(self, parent, demopath, steamdir):
		'''Args:
		parent: Tkinter widget that is the parent of this dialog.
		demopath: Absolute file path to the demo to be played.
		steamdir: A directory that should be referring to an installation
			of Steam, but bad values are handled.
		'''
		self.result_ = {}

		self.parent = parent

		self.demopath = demopath
		self.steamdir = tk.StringVar()
		self.steamdir.set(steamdir)

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
		steamdirframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8), 
			labelwidget = frmd_label(master, "Steam install path") )
		widgetframe = ttk.Frame(steamdirframe)
		self.steamdirentry = ttk.Entry(widgetframe, state = "readonly",
			textvariable = self.steamdir)
		self.steamdirbtn = ttk.Button(widgetframe,
			style = "Contained.TButton", command = self.askfordir,
			text = "Select Steam install path")
		widgetframe.pack(side = tk.TOP, expand = 1, fill = tk.X)
		self.error_steamdir_invalid = ttk.Label(steamdirframe, anchor = tk.N,
			justify = tk.CENTER, style = "Error.Contained.TLabel",
			text = ("Getting steam users failed! Please select the root folder"
			" called \"Steam\".\nEventually check for permission conflicts.") )
		self.warning_steamdir_mislocated = ttk.Label(steamdirframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("The queried demo and the Steam directory are on"
			" seperate drives.") )

		userselectframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8),
			labelwidget = frmd_label(master, "Select user profile if needed"))
		self.info_launchoptions_not_found = ttk.Label(userselectframe,
			anchor = tk.N, style = "Info.Contained.TLabel", text = ("Launch "
			"configuration not found, it likely does not exist.") )
		self.userselectbox = ttk.Combobox(userselectframe,
			textvariable = self.userselectvar, values = self.getusers(),
			state = "readonly")#Once changed, observer callback triggered by self.userselectvar

		launchoptionsframe = ttk.LabelFrame(master, padding = (10, 8, 10, 8),
			labelwidget = frmd_label(master, "Launch options:") )
		launchoptwidgetframe = ttk.Frame(launchoptionsframe, borderwidth = 4,
			relief = tk.RAISED, padding = (5, 4, 5, 4), width = 450,
			height = 50)
		self.launchlabel1 = ttk.Label(launchoptwidgetframe,
			text = "[...]/hl2.exe -steam -game tf")
		self.launchoptionsentry = ttk.Entry(launchoptwidgetframe,
			textvariable = self.launchoptionsvar)
		pluslabel = ttk.Label(launchoptwidgetframe, text = "+")
		self.launchlabelentry = ttk.Entry(launchoptwidgetframe,
			state = "readonly", textvariable = self.playdemoarg)
		launchoptwidgetframe.pack_propagate(False)

		self.warning_vdfmodule = ttk.Label(launchoptionsframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("Please install the vdf module in order to launch TF2 with"
			" your default settings.\n(Run cmd in admin mode; type "
			"\"python -m pip install vdf\")"), justify = tk.CENTER)

		self.warning_not_in_tf_dir = ttk.Label(launchoptionsframe,
			anchor = tk.N, style = "Warning.Contained.TLabel",
			text = ("The demo can not be played as it is not in"
			" Team Fortress\' file system (/tf/)") )
		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)

		#pack start
		self.steamdirentry.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		self.steamdirbtn.pack(side = tk.LEFT, fill = tk.X)
		self.error_steamdir_invalid.pack()
		self.warning_steamdir_mislocated.pack()
		steamdirframe.pack(fill = tk.BOTH, expand = 1, pady = 5)

		self.userselectbox.pack(fill = tk.X)
		self.info_launchoptions_not_found.pack()
		userselectframe.pack(fill = tk.BOTH, expand = 1, pady = 5)

		self.warning_vdfmodule.pack()
		self.launchlabel1.pack(side = tk.LEFT, fill = tk.Y)
		self.launchoptionsentry.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		pluslabel.pack(side = tk.LEFT)
		self.launchlabelentry.pack(side = tk.LEFT, fill = tk.X, expand = 1)
		launchoptwidgetframe.pack(side = tk.TOP, expand = 1, fill = tk.X)
		self.warning_not_in_tf_dir.pack()
		launchoptionsframe.pack(fill = tk.BOTH, expand = 1, pady = (5, 10))

		self.btconfirm = ttk.Button(master, text = "Launch!",
			command = lambda: self.done(1))
		self.btcancel = ttk.Button(master, text = "Cancel",
			command = lambda: self.done(0))

		self.btconfirm.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (0, 3))
		self.btcancel.pack(side = tk.LEFT, expand = 1, fill = tk.X, anchor = tk.S,
			padx = (3, 0))
		self.userchange()

		self.__showerrs()
		self.userselectvar.trace("w", self.userchange) # If applied before,
		# method would be triggered and UI elements would be accessed that do not exist yet.

	def __showerrs(self):#NOTE: Could update that, do in case you ever change this dialog
		'''Update all error labels after looking at conditions'''
		if self.errstates[0]:
			self.error_steamdir_invalid.pack(side = tk.BOTTOM)
		else:
			self.error_steamdir_invalid.pack_forget()
		if self.errstates[1]:
			self.warning_steamdir_mislocated.pack(side = tk.BOTTOM)
		else:
			self.warning_steamdir_mislocated.pack_forget()
		if self.errstates[2]:
			self.warning_vdfmodule.pack(side = tk.TOP)
		else:
			self.warning_vdfmodule.pack_forget()
		if self.errstates[3]:
			self.warning_not_in_tf_dir.pack(side = tk.BOTTOM, anchor = tk.S,
				fill = tk.BOTH)
		else:
			self.warning_not_in_tf_dir.pack_forget()
		if self.errstates[4]:
			self.info_launchoptions_not_found.pack(fill = tk.BOTH)
		else:
			self.info_launchoptions_not_found.pack_forget()

	def getusers(self):
		'''Executed once by body(), by askfordir(), and used to insert value
		into self.userselectvar.
		'''
		toget = os.path.join(self.steamdir.get(), CNST.STEAM_CFG_PATH0)
		try:
			users = os.listdir(toget)
		except (OSError, PermissionError, FileNotFoundError):
			self.errstates[0] = True
			return []
		self.errstates[0] = False
		return users

	def __getlaunchoptions(self):
		try:
			import vdf
			self.errstates[2] = False
			with open(os.path.join( self.steamdir.get(),
				CNST.STEAM_CFG_PATH0, self.userselectvar.get(),
				CNST.STEAM_CFG_PATH1) ) as h:
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
		except ModuleNotFoundError:
			self.errstates[2] = True
			self.errstates[4] = False
			return ""
		except (KeyError, FileNotFoundError, OSError, PermissionError,
			SyntaxError): #SyntaxError raised by vdf module
			self.errstates[4] = True
			return ""

	def askfordir(self): #Triggered by user clicking on the Dir choosing btn
		'''Opens up a file selection dialog and sets the steam directory to
		the selected directory, updating related widgets.
		'''
		sel = tk_fid.askdirectory()
		if sel == "":
			return
		self.steamdir.set(sel)
		self.userselectbox.config(values = self.getusers())
		try:
			self.userselectvar.set(self.getusers()[0])
		except Exception:
			self.userselectvar.set("") # will trigger self.userchange
		self.__constructshortdemopath()
		self.launchlabelentry.config(width = len(self.playdemoarg.get()) + 2)
		self.__showerrs()

	def userchange(self, *_): # Triggered by observer on combobox variable.
		launchopt = self.__getlaunchoptions()
		self.launchoptionsvar.set(launchopt)
		self.__showerrs()

	def __constructshortdemopath(self):
		try:
			self.shortdemopath = os.path.relpath(self.demopath,
				os.path.join(self.steamdir.get(), CNST.TF2_HEAD_PATH))
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
			executable = os.path.join(self.steamdir.get(), CNST.TF2_EXE_PATH)
			launchopt = self.launchoptionsvar.get()
			launchopt = launchopt.split()
			launchoptions = ([executable] + CNST.TF2_LAUNCHARGS +
				launchopt + ["+playdemo", self.shortdemopath])
			try:
				subprocess.Popen(launchoptions) #Launch tf2; -steam param may cause conflicts when steam is not open but what do I know?
				self.result_ = {"success":True, "steampath":self.steamdir.get()}
			except FileNotFoundError:
				self.result_ = {"success":False, "steampath":self.steamdir.get()}
				tk_msg.showerror("Demomgr - Error", "hl2 executable not found.", parent = self)
			except (OSError, PermissionError) as error:
				self.result_ = {"success":False, "steampath":self.steamdir.get()}
				tk_msg.showerror("Demomgr - Error",
					"Could not access hl2.exe :\n{}".format(str(error)), parent = self)
		self.destroy()
