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
else:
	shell32 = None

def open_explorer(dir, selected_files):
	if shell32 is None:
		raise OSError("Can not open Windows explorer on a non-Windows system.")

	if not os.path.exists(dir):
		raise FileNotFoundError("Directory does not exist!")

	dir_wchar_p = ctypes.c_wchar_p(os.path.normpath(dir))
	dir_item_id_list = shell32.ILCreateFromPath(dir_wchar_p)

	for file in selected_files:
		p = os.path.normpath(os.path.join(dir, file))
		pb = ctypes.c_wchar_p(p)
		print(p, pb)

	shell32.SHOpenFolderAndSelectItems(dir_item_id_list, 0, POINTER(POINTER(ITEMIDLIST))(), 0)

	shell32.ILFree(dir_item_id_list)



