
import os
import re
import sys

if __name__ == "__main__":
	RE_SEMVER = re.compile(
		r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
		r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
		r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))"
		r"?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
	)

	arch = sys.argv[1]
	# should be something like `refs/tags/v1.2.3`
	raw_ref = os.getenv("GITHUB_REF", "unknown")

	if (ref := RE_SEMVER.search(raw_ref)) is None:
		print("Semver not found in GITHUB_REF, using last segment!")
		ref = raw_ref.split("/")[-1]
	else:
		ref = ref[0]
	ref = ref.replace(".", "_")

	build_name = f"demomgr-v{ref}-win{arch}"

	gh_env_file = os.environ["GITHUB_ENV"]
	with open(gh_env_file, "a") as f:
		for name, value in (
			("BUILD_NAME", build_name),
			("DEMOMGR_DIST_GLOB", "./nuitka_build/demomgr.dist/**"),
		):
			f.write(f"{name}={value}\n")
