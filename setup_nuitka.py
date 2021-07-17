from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess

# files that the program still runs without (according
# to ProcessExplorer) and that are relatively large in size.
PROBABLY_UNUSED_FILES = (
	"_asyncio.pyd",
	"_bz2.pyd",
	"_ctypes.pyd",
	"_decimal.pyd",
	"_elementtree.pyd",
	"_hashlib.pyd",
	"_msi.pyd",
	"_multiprocessing.pyd",
	"_overlapped.pyd",
	"_lzma.pyd",
	"_sqlite3.pyd",
	"_ssl.pyd",
	# This one is used but also available in System32; seems to fluctuate and requires
	# an exact version, keeping it
	### "comctl32.dll",
	"libcrypto-1_1.dll",
	"libffi-7.dll",
	"libssl-1_1.dll",
	"pyexpat.pyd",
	"sqlite3.dll",
)

PROBABLY_UNUSED_DIRS = (
	"lib2to3",
)

cur_path = Path.cwd()
build_dir = cur_path / "nuitka_build"
dist_dir = build_dir / "demomgr.dist"
run_py = cur_path / "demomgr"

def main():
	if build_dir.exists():
		shutil.rmtree(build_dir)

	nuitka_process = subprocess.run((
		"py", "-m", "nuitka",
		"--mingw64", "--standalone", "--follow-imports",
		"--plugin-enable=tk-inter",
		f"--output-dir={build_dir}", run_py
	))

	# Copy over ui resources, can't figure out the nuitka switch
	os.makedirs(str(dist_dir / "demomgr" / "ui_themes"))
	shutil.copytree(
		cur_path / "demomgr" / "ui_themes",
		dist_dir / "demomgr" / "ui_themes",
		dirs_exist_ok = True
	)

	for file in PROBABLY_UNUSED_FILES:
		to_delete = dist_dir / file
		if not to_delete.exists():
			continue
		to_delete.unlink()

	for dir in PROBABLY_UNUSED_DIRS:
		to_delete = dist_dir / dir
		if not to_delete.exists():
			continue
		shutil.rmtree(str(to_delete))

	with (cur_path / "LICENSE").open("r") as license_fp:
		license = license_fp.read()
	with (dist_dir / "LICENSE").open("w") as license_fp:
		license_fp.write(re.sub(r"\(c\) \d+", datetime.now().strftime("(c) %Y"), license))

if __name__ == "__main__":
	main()
