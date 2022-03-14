"""
Hosts functionality to open windows explorer with any amount
of files selected via the SHOpenFolderAndSelectItems function.
"""

import ctypes
from ctypes import wintypes
from ctypes import Structure, POINTER

import os

# Thanks: https://stackoverflow.com/questions/3018002/
# 	c-how-to-use-shopenfolderandselectitems/12262552#12262552

if os.name == "nt":
	shell32 = ctypes.windll.shell32

	class SHITEMID(Structure):
		_fields_ = [
			("cb", wintypes.USHORT),
			("abID", wintypes.BYTE * 1),
		]

	class ITEMIDLIST(Structure):
		_fields_ = [
			("mkid", SHITEMID)
		]

	shell32.ILFree.argtypes = [POINTER(ITEMIDLIST)]
	shell32.ILFree.restype = None

	shell32.ILCreateFromPath.argtypes = [wintypes.PWCHAR]
	shell32.ILCreateFromPath.restype = POINTER(ITEMIDLIST)

	shell32.SHOpenFolderAndSelectItems.argtypes = [
		POINTER(ITEMIDLIST), wintypes.UINT, POINTER(POINTER(ITEMIDLIST)), wintypes.DWORD
	]
	shell32.SHOpenFolderAndSelectItems.restype = ctypes.HRESULT

	shell32.ShellExecuteW.argtypes = [
		wintypes.HWND,
		wintypes.LPCWSTR,
		wintypes.LPCWSTR,
		wintypes.LPCWSTR,
		wintypes.LPCWSTR,
		wintypes.INT,
	]
	shell32.ShellExecuteW.restype = wintypes.BOOL
else:
	shell32 = None

def _open_explorer_selection(directory, files):
	"""
	Opens explorer at the given directory with the given files selected.
	If the directory or the files do not exist, an OSError will be raised.
	"""
	dir_wchar_p = ctypes.c_wchar_p(os.path.normpath(directory))

	dir_item_id_list = shell32.ILCreateFromPath(dir_wchar_p)
	if not dir_item_id_list:
		raise OSError("Directory ITEMIDLIST was NULL!")

	selection_pidl_array = (POINTER(ITEMIDLIST) * len(files))()
	try:
		for i, file in enumerate(files):
			p = os.path.normpath(os.path.join(directory, file))
			selection_pidl_array[i] = shell32.ILCreateFromPath(ctypes.c_wchar_p(p))
			if not selection_pidl_array[i]:
				raise OSError(f"PITEMIDLIST {i} for {p!r} was NULL!")

		shell32.SHOpenFolderAndSelectItems(
			dir_item_id_list,
			len(files),
			selection_pidl_array,
			0,
		)
	finally:
		for sel_pidl in selection_pidl_array:
			if sel_pidl:
				shell32.ILFree(sel_pidl)

		shell32.ILFree(dir_item_id_list)

def _open_explorer_dir_only(directory):
	"""
	Opens a windows explorer window at the given directory.
	If the command fails, an OSError is raised.
	"""
	r = shell32.ShellExecuteW(
		wintypes.HWND(0),
		"explore",
		directory,
		wintypes.LPCWSTR(0),
		wintypes.LPCWSTR(0),
		1, # SW_SHOWNORMAL
	)
	if r <= 32:
		raise OSError(f"ShellExecuteW failed: {r}")

def open_explorer(directory, selected_files):
	"""
	Opens windows explorer at the given directory with all files in
	`selected_files` selected. `selected_files` may also be empty.
	"""
	if shell32 is None:
		raise OSError("Can not open Windows explorer on a non-Windows system.")

	if not os.path.exists(directory):
		raise FileNotFoundError("Directory does not exist!")

	if selected_files:
		_open_explorer_selection(directory, selected_files)
	else:
		_open_explorer_dir_only(directory)
