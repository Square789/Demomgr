from itertools import product
import os
from pathlib import Path
import sys
import pkg_resources
import shutil
import subprocess

ASSUME_YES = os.getenv("NUITKA_ASSUME_YES") is not None
COMPILER_USE_DEFAULT = os.getenv("NUITKA_COMPILER_USE_DEFAULT") is not None


# files that the program still runs without (according
# to ProcessExplorer) and that are relatively large in size.
PROBABLY_UNUSED_FILES = (
	"_asyncio.pyd",
	"_bz2.pyd",
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

def copy_license(package_name, target_dir, license_suffix, license_names = None):
	license_text = None
	filename = None
	module = pkg_resources.get_distribution(package_name)
	names = (
		map("".join, product(("LICENSE", "LICENCE"), ("", ".txt")))
		if license_names is None else license_names
	)
	for _name in names:
		try:
			# Look, I know this var would persist after the loop anyways,
			# but it's mega clunky
			filename = _name
			license_text = module.get_metadata(filename)
			break
		except FileNotFoundError:
			pass
	else:
		raise FileNotFoundError(f"Could not find license for module {package_name!r}")
	with (target_dir / (filename + license_suffix)).open("w") as license_fp:
		license_fp.write(license_text)


cur_path = Path.cwd()
build_dir = cur_path / "nuitka_build"
dist_dir = build_dir / "demomgr.dist"
regex_dist_dir = dist_dir / "regex"
run_py = cur_path / "demomgr"

def main():
	if build_dir.exists():
		shutil.rmtree(build_dir)

	options = [sys.executable, "-m", "nuitka"]
	if ASSUME_YES:
		options.append("--assume-yes-for-downloads")
	if COMPILER_USE_DEFAULT is None:
		options.extend("--mingw64")
	options.extend((
		"--standalone",
		"--follow-imports",
		"--plugin-enable=tk-inter",
		f"--output-dir={build_dir}",
		run_py,
	))

	nuitka_process = subprocess.run(options)
	if nuitka_process.returncode != 0:
		raise RuntimeError("Nuitka failed.")

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

	# Copy licenses
	with (cur_path / "LICENSE").open("r") as license_fp:
		license = license_fp.read()
	with (dist_dir / "LICENSE").open("w") as license_fp:
		license_fp.write(license)

	copy_license("regex", regex_dist_dir, "")
	copy_license("vdf", dist_dir, "-ValvePython_vdf")
	copy_license("schema", dist_dir, "-keleshev_schema", ("LICENSE-MIT",))


if __name__ == "__main__":
	main()
