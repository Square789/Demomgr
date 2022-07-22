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
import typing as t

import demomgr.constants as CNST

_system = platform.system().lower()


_SPACE_CHARS = {' ', '\t', '\v', '\n'}
_QUOTE_NEEDING_CHARS = _SPACE_CHARS | {'"'}

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


	# Stolen together from all over
	# https://stackoverflow.com/questions/29213106/
	# 	how-to-securely-escape-command-line-arguments-for-the-cmd-exe-shell-on-windows,
	# https://docs.microsoft.com/en-us/cpp/cpp/main-function-command-line-args
	# 	#parsing-c-command-line-arguments
	# https://docs.microsoft.com/en-us/cpp/c-language/parsing-c-command-line-arguments
	# https://docs.microsoft.com/en-us/archive/blogs/twistylittlepassagesallalike/
	# 	everyone-quotes-command-line-arguments-the-wrong-way
	# https://github.com/mesonbuild/meson/blob/master/mesonbuild/mesonlib/universal.py
	# https://github.com/python/cpython/blob/3.8/Lib/subprocess.py
	def split_cmdline(args: str) -> t.List[str]:
		if not args:
			return []

		res = []
		cur_arg = []
		in_string = False
		backslash_run = 0
		i = 0
		while i < len(args):
			c = args[i]
			if c == '\\':
				backslash_run += 1
				i += 1
				continue

			if c == '"':
				if backslash_run & 1:
					# odd amount of backslashes, escaped quote
					cur_arg.append('\\' * (backslash_run // 2) + '"')
				else:
					# Regular quote, you may be thinking? Ha, surprise!
					# "A pair of double quotes inside a string is interpreted as a
					# single literal quote" because screw you i guess.
					if in_string and i < len(args) - 1 and args[i + 1] == '"':
						cur_arg.append('"')
						i += 1
					else:
						# Regular quote, starts or ends a string.
						# However, a string is not an argument, so don't finalize cur_arg here.
						# Yes, strings may be embedded in other arguments. I really hope they
						# can not nest cause this function does not care for that.
						# This still halves any preceding backslash count, cause it's a double
						# quote and who am i to speak against microsoft legacy garbage?
						cur_arg.append('\\' * (backslash_run // 2))
						in_string = not in_string

			elif not in_string and c in _SPACE_CHARS:
				# Cool, argument terminated. If at the start, cur_arg may not contain
				# anything, check for that.
				if cur_arg or backslash_run > 0:
					res.append(''.join(cur_arg) + ('\\' * backslash_run))
					cur_arg.clear()
				# Skip other whitespace while we're at it.
				# (i += 1 at loop end does the missing jump)
				while i < len(args) - 1 and args[i + 1] in _SPACE_CHARS:
					i += 1

			else:
				# Backslashes not preceding '"' are interpreted literally, add them as-is
				cur_arg += ('\\' * backslash_run) + c

			i += 1
			backslash_run = 0

		if cur_arg or backslash_run > 0:
			res.append(''.join(cur_arg) + ('\\' * backslash_run))

		return res

	def quote_cmdline_arg(arg: str) -> str:
		if not any(x in _QUOTE_NEEDING_CHARS for x in arg):
			return arg
		return '"' + arg.replace('"', "\\\"") + '"'

else:
	kernel32 = None

	from shlex import split as split_cmdline
	from shlex import quote as quote_cmdline_arg


# Poor decisions. Why did i not want to roam a config file?
# Also the `.demomgr` sticks out like a sore thumb alongside all other dirs in `.config`
# that are not prefixed with a dot
def get_old_cfg_storage_path() -> str:
	if _system == "windows":
		appdata_path = Path(os.environ["APPDATA"])
		if (
			str(appdata_path.parent.name).lower() == "appdata" and
			appdata_path.name.lower() == "roaming"
		):
			appdata_path = appdata_path.parent
		return str(Path(appdata_path, "Local", ".demomgr", "config.cfg"))
	else:
		return str(Path("~/.config", ".demomgr", "config.cfg").expanduser())
		# No clue if this works, especially on apple.

def get_cfg_storage_path() -> str:
	if _system == "windows":
		return str(Path(os.environ["APPDATA"], "Demomgr", "config.json"))
	else:
		cfg_dir = os.getenv("XDG_CONFIG_HOME", os.path.join(os.environ["HOME"], ".config/"))
		return str(Path(cfg_dir, "Demomgr", "config.json"))
		# Still unsure about this on darwin, since there's also a Library/Application Support/ dir
		# there but A: i don't really care about that platform and B: i have no way of testing
		# this as a direct consequence of A.

def get_contextmenu_btn() -> t.Optional[str]:
	"""
	Returns the name of the contextmenu button, dependent on the system.
	May return None, in which case it's probably best to create no binding.
	"""
	if _system == "windows":
		return "App"
	elif _system == "linux":
		return "Menu"
	return None

def should_use_windows_explorer() -> bool:
	"""
	Returns whether the windows explorer should be used aka the system
	is windows.
	"""
	return _system == "windows"

def get_rightclick_btn() -> str:
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

def get_steam_exe() -> str:
	"""
	Returns the steam executable name.
	"""
	if _system == "windows":
		return CNST.STEAM_EXE
	else:
		return CNST.STEAM_SH

def _win_create_file(p: str) -> int:
	# OPEN_EXISTING is 3
	# FILE_ATTRIBUTE_NORMAL is 128
	# FILE_FLAG_BACKUP_SEMANTICS is 0x02000000, required for directories
	# for some reason. This works, don't question it
	h = kernel32.CreateFileW(p, 0, 0, None, 3, 128 | 0x0200_0000, None)
	if h == INVALID_HANDLE_VALUE:
		raise OSError("CreateFile returned invalid handle.")
	return h

def is_same_path(a: str, b: str) -> bool:
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
