import ast
from setuptools import setup

# Thanks: https://stackoverflow.com/questions/2058802/
# 	how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
__version__ = None
with open("demomgr/main_app.py") as h:
	for line in h.readlines():
		if line.startswith("__version__"):
			__version__ = ast.parse(line).body[0].value.s
			break

if __version__ == None:
	raise SyntaxError("Version not found.")

with open("README.md") as h:
	long_desc = h.read()

with open("requirements.txt") as h:
	reqs = h.read().splitlines()

setup(
	name = "Demomgr",
	author = "Square789",
	version = __version__,
	description = "TF2 demo file management tool written in Python and Tcl, using tkinter.",
	long_description = long_desc,
	long_description_content_type = "text/markdown",
	packages = ["demomgr"],
	install_requires = reqs,
	classifiers = [
		"Topic :: Desktop Environment :: File Managers",
		"Programming Language :: Python",
		"Programming Language :: Tcl",
		"License :: OSI Approved :: MIT License",
		"Intended Audience :: End Users/Desktop",
	],
	entry_points = {
		"console_scripts": [
			"demomgr = demomgr.__init__:run",
		],
	},
	url = "https://www.github.com/Square789/Demomgr",
)
