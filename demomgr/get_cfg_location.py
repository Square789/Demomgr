"""
Module to return a configuration storage location, which should
be the same on each operating system.
"""

import getpass
import os
from pathlib import Path
import platform

import demomgr.constants as CNST

def get_cfg_storage_path():
	if os.name == "nt": # Windows
		appdata_path = Path(os.environ["APPDATA"])
		if (str(appdata_path.parent.name).lower() == "appdata" and
				appdata_path.name.lower() == "roaming"):
			appdata_path = appdata_path.parent
		return str(Path(appdata_path, "Local", CNST.CFG_FOLDER, CNST.CFG_NAME))
	else:
		return str(Path("~/.config", CNST.CFG_FOLDER, CNST.CFG_NAME).expanduser())
		# No clue if this works, too lazy to install linux to test.
