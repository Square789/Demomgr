"""
Functionality that needs different implementations
based on the platform Demomgr is run on.
"""

import ctypes
from ctypes import wintypes
from ctypes import Structure, POINTER
import os
from pathlib import Path
import platform

import demomgr.constants as CNST

_system = platform.system().lower()

if _system == "windows":
	kernel32 = ctypes.windll.Kernel32

	# This should be good:
	# https://superuser.com/questions/305901/possible-values-of-processor-architecture
	BITNESS = 64 if "64" in os.environ["PROCESSOR_ARCHITECTURE"] else 32
	INVALID_HANDLE_VALUE = 2**BITNESS - 1

	class BY_HANDLE_FILE_INFORMATION(Structure):
		_fields_ = [
			("dwFileAttributes", wintypes.DWORD),
			("ftCreationTime", wintypes.FILETIME),
			("ftLastAccessTime", wintypes.FILETIME),
			("ftLastWriteTime", wintypes.FILETIME),
			("dwVolumeSerialNumber", wintypes.DWORD),
			("nFileSizeHigh", wintypes.DWORD),
			("nFileSizeLow", wintypes.DWORD),
			("nNumberOfLinks", wintypes.DWORD),
			("nFileIndexHigh", wintypes.DWORD),
			("nFileIndexLow", wintypes.DWORD),
		]

	kernel32.GetFileInformationByHandle.argtypes = [
		wintypes.HANDLE, POINTER(BY_HANDLE_FILE_INFORMATION)
	]
	kernel32.GetFileInformationByHandle.restype = wintypes.BOOL

	kernel32.CreateFileW.argtypes = [
		wintypes.LPCWSTR,
		wintypes.DWORD,
		wintypes.DWORD,
		ctypes.c_void_p,
		wintypes.DWORD,
		wintypes.DWORD,
		wintypes.HANDLE,
	]
	kernel32.CreateFileW.restype = wintypes.HANDLE

	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	kernel32.CloseHandle.restype = wintypes.BOOL

	kernel32.GetLastError.argtypes = []
	kernel32.GetLastError.restype = wintypes.DWORD

	# Taken from https://stackoverflow.com/questions/29213106/
	# 	how-to-securely-escape-command-line-arguments-for-the-cmd-exe-shell-on-windows,
	# except i kinda didn't need it so it shall remain as an empty comment.
	# RE_METACHARS = re.compile('(' + '|'.join(re.escape(c) for c in '()%!^"<>&|') + ')')
	# def quote(s):
	# 	if re.search(r'["\s]', s):
	# 		s = '"' + s.replace('"', '\\"') + '"'
	# 	return RE_METACHARS.sub(lambda match: '^' + match[1], s)

else:
	kernel32 = None
	# quote = shlex.quote


def get_cfg_storage_path():
	if _system == "windows":
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
	if _system == "windows":
		return "App"
	elif _system == "linux":
		return "Menu"
	return None

def should_use_windows_explorer():
	"""
	Returns whether the windows explorer should be used aka the system
	is windows.
	"""
	return _system == "windows"

def get_rightclick_btn():
	"""
	Returns the identifier for the right mouse button used by tkinter
	as a string.
	"""
	if _system == "linux":
		return "3"
	elif _system == "darwin":
		return "2"
	elif _system == "windows":
		return "3"
	return "3" # best guess

def get_steam_exe():
	"""
	Returns the steam executable name.
	"""
	if _system == "windows":
		return CNST.STEAM_EXE
	else:
		return CNST.STEAM_SH

def _win_create_file(p):
	# OPEN_EXISTING is 3
	# FILE_ATTRIBUTE_NORMAL is 128
	# FILE_FLAG_BACKUP_SEMANTICS is 0x02000000, required for directories
	# for some reason. This works, don't question it
	h = kernel32.CreateFileW(p, 0, 0, None, 3, 128 | 0x0200_0000, None)
	if h == INVALID_HANDLE_VALUE:
		raise OSError("CreateFile returned invalid handle.")
	return h

def is_same_path(a, b):
	"""
	Compares the paths a and b given as strings and returns whether
	they lead to the same location.
	To be honest, I have no idea whether it works for files,
	(on windows). Should work for directories and files on linux.
	If one of the paths does not exist, a `FileNotFoundError` is
	raised.
	May raise `OSError` on other failures.
	"""
	a = os.path.abspath(os.path.normcase(os.path.normpath(a)))
	b = os.path.abspath(os.path.normcase(os.path.normpath(b)))
	if _system == "windows":
		# Using this answer:
		# https://stackoverflow.com/questions/562701/
		# 	best-way-to-determine-if-two-path-reference-to-same-file-in-windows

		for path in (a, b):
			if not os.path.exists(path):
				raise FileNotFoundError(f"Path {path} did not exist.")

		# Yes, the OS may pause python right here to delete the
		# previous files and then fail due to different reasons below.
		# Who cares, different exception type then

		# Fueling my desire to switch to Linux, this shit is.
		ah = _win_create_file(a)
		try:
			bh = _win_create_file(b)
		except OSError as e:
			kernel32.CloseHandle(ah)
			raise e from None

		ai = BY_HANDLE_FILE_INFORMATION()
		bi = BY_HANDLE_FILE_INFORMATION()
		if (
			kernel32.GetFileInformationByHandle(ah, ctypes.byref(ai)) == 0 or
			kernel32.GetFileInformationByHandle(bh, ctypes.byref(bi)) == 0
		):
			kernel32.CloseHandle(ah)
			kernel32.CloseHandle(bh)
			raise OSError("GetFileInformation failed.")

		res = (
			ai.dwVolumeSerialNumber == bi.dwVolumeSerialNumber and
			ai.nFileIndexLow == bi.nFileIndexLow and
			ai.nFileIndexHigh == bi.nFileIndexHigh
		)

		kernel32.CloseHandle(ah)
		kernel32.CloseHandle(bh)

		return res
	else:
		return os.path.samefile(a, b)
