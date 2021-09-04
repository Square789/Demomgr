"""
Module to return values loosely based on the platform demomgr is run on.
"""

import os
from pathlib import Path
import platform

import demomgr.constants as CNST

def get_cfg_storage_path():
	if os.name == "nt": # Windows
		appdata_path = Path(os.environ["APPDATA"])
		if (
			str(appdata_path.parent.name).lower() == "appdata" and
			appdata_path.name.lower() == "roaming"
		):
			appdata_path = appdata_path.parent
		return str(Path(appdata_path, "Local", CNST.CFG_FOLDER, CNST.CFG_NAME))
	else:
		return str(Path("~/.config", CNST.CFG_FOLDER, CNST.CFG_NAME).expanduser())
		# No clue if this works, especially on apple.

def get_contextmenu_btn():
	"""
	Returns the name of the contextmenu button, dependent on the system.
	May return None, in which case it's probably best to create no binding.
	"""
	if os.name == "nt":
		return "App"
	elif os.name == "posix":
		return "Menu"
	return None

def should_use_windows_explorer():
	"""
	Returns whether the windows explorer should be used aka the system
	is windows.
	"""
	system = platform.system().lower()
	return system == "windows"

def get_rightclick_btn():
	"""
	Returns the identifier for the right mouse button used by tkinter
	as a string.
	"""
	system = platform.system().lower()
	if system == "linux":
		return "2"
	elif system  == "darwin":
		return "2"
	elif system == "windows":
		return "3"
	return "3" # best guess
