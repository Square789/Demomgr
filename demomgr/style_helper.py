"""
This module supplies the StyleHelper class which is a class to read
image directories and save them in a tcl variable as well as convert dicts
to tk commands to make creation of image-reliant interfaces easier.
(Although you should probably just use the plain tcl script for a UI and not
recreate it every program start which is what load_theme is for.)
! DO NOT USE THESE CLASSES IF YOUR VARIABLE/STYLE NAMES CONTAIN CHARACTERS
LIKE [, ], {, } ! (but why would they, really.)

2021 update: This file is a mess and I don't think I will be touching it
	anytime soon.
"""

import os
import re

RE_FORBIDDEN = [(re.compile(r"\["), "Attempted command call."),
	(re.compile(r"(?:(?<=[^\\])|^)(\\(?:\\{2})*)(?=[^\\]|$)"),
		"Odd amount of backslashes.")
	]

IMGLOADERSCRIPT = """
variable {imgvarname}
foreach imgpath [glob -directory {imagedir} {globpattern}] \
{{
	set imgname [file tail $imgpath]
	set {imgvarname}($imgname) [image create photo -file $imgpath]
}}
"""

class StyleHelper():
	"""
	This class takes the following for initialization:
	Args:
	parent <Tcl object>: Any object that has a tcl interpreter available as
		object.tk; tkinter.Tk instance is recommended.
	"""
	def __init__(self, parent):
		self.parent = parent
		self.tk = parent.tk

	def load_image_dir(self, imagedir, filetypes, imgvarname):
		"""
		Execute direct tcl calls to get all images ending in filetypes
		from imagedir and saves them in imgvarname for use in ttk styles.
		Args:
		imagedir <Str>: directory to search in (will be extended by cwd)
		filetypes <List|Tuple>: file extensions to get
		imgvarname <Str>: Name for the Tcl variable to save images in
		"""

		imagedir = os.path.join(os.path.normpath(os.getcwd()),
			os.path.normpath(imagedir))
		imagedir = imagedir.replace("\\", "\\\\")

		_validate(*filetypes)

		filetypes = [i.strip(".") for i in filetypes]
		#remove potential file identifier dots
		filetypes = ["*." + i for i in filetypes]
		#add tcl glob wildcard limiters
		globpattern = "{{{{{}}}}}".format(", ".join(filetypes))

		_validate(imagedir, imgvarname)

		localscript = IMGLOADERSCRIPT.format(
			imagedir = imagedir,
			imgvarname = imgvarname,
			globpattern = globpattern
		)
		self.tk.eval(localscript)

	def load_theme(self, theme_filepath, themename):
		"""
		Loads the tcl file at theme_filepath defining a theme with
		"ttk::style theme create" from disk, executes it !BLINDLY!, then calls
		setTheme with themename on the newly created theme.
		Does not create or set theme when it already exists/is in use.
		USE WITH CARE!
		"""
		existingthemes = self.tk.eval("ttk::style theme names").split(" ")
		if not themename in existingthemes:
			with open(theme_filepath, "r") as handle:
				script = handle.read()
			self.tk.eval(script)
			del script
		curtheme = self.tk.eval("return $ttk::currentTheme")
		if themename != curtheme:
			self.tk.eval("ttk::setTheme {}".format(themename))

	def generate_theme_script(self, styledict, themename, parent = None):
		"""
		Returns a string that can be executed by a Tcl interpreter
		that will result in a theme being declared. Tries to keep it neat
		and indented.
		Args:

		styledict <dict>: Style dictionary. Must follow the convention below:
		themename <Str>: Name to be used for the theme.
		parent <Str>: Theme the created theme will be based on. Default: None

		styledict must consist out of 4 commands, with:
		{
			"configure": {
				"<STYLENAME0>": {
					"<option0>": <value0>,
					"<option1>": <value1>, ...
				},
				"<STYLENAME1>": {...}
			}
			"element create": {
				"<STYLENAME0>": {
					"image": [
						[ # LENGTH OF THIS ARRAY MUST BE ODD!
							"<IMAGENAME-default>",
							"<STATE0>", "<IMAGENAME-state0>",
							[<STATE1a>, <STATE1b>], "<IMAGENAME-state1>", ...
						],
						{
							"<option0>": <value0>, ...
						}
					]
				}, ...
			}
			"layout": {
				"<STYLENAME>"
					"<ELEMENTNAME0>": {
						"<option0>":<value0>, ... #VALUE MAY BE LIST OR STRING FOR
							SOME SITUATIONS
						"children": {
							"<SUBELEMENT0>": {
								"children": {
									"<SUBSUBELEMENT0>": {
										...
									}
								}
							}
						}
					}
				}, ...
			},
			"map": {
				"<STYLENAME0>": {
					"<option0>": [
						[ [ "<states0>" ], <value0>], #length of 2
						[ ["<states1a>", "<states1b>"], <value1>], # length of 2
						...
					]
				}, ...
			}
		}
		Options containing square brackets or backslashes will raise a
		validation error.
		"""
		script = []

		for key, val in styledict.items():
			if key == "configure":
				script.extend(self._resolve_config(val))
			elif key == "element create":
				script.extend(self._resolve_element_create(val))
			elif key == "layout":
				script.extend(self._resolve_layout(val))
			elif key == "map":
				script.extend(self._resolve_map(val))

		if parent:
			parentarg = " -parent " + parent
		else:
			parentarg = ""
		script = ("ttk::style theme create " + themename + parentarg +
					" -settings \\\n{\n" + "\n".join(script) + "\n}")
		return script

	def _resolve_config(self, indict):
		outscript = []
		for style, optdict in indict.items():
			_validate(style)
			stylecnf = []
			for optkey, optval in optdict.items():
				stylecnf.append(self._resolve_opt_val_pair(optkey, optval))
			stylecnf = " \\\n\t\t".join(stylecnf)
			outscript.append("\tttk::style configure " + style +
				" \\\n\t\t" + stylecnf)
		return outscript

	def _resolve_element_create(self, indict):
		outscript = []
		for style, styledict in indict.items(): # e.g. "TLabelframe, {}"
			_validate(style)
			for elementname, elemlist in styledict.items(): # e.g. "image", []
				_validate(elementname)
				elementparams, elemcnfcmd = "", ""
				#TODO: Add support for vs_api item (@ else: ... below)
				if elementname == "image": #Construct image creation command
					statelist = elemlist[0]
					baseimg = statelist.pop(0) # base image name
					if len(statelist) % 2 != 0:
						raise ValueError("State-image combinations must be set"
							" in pairs of two.")
					statecmd = []
					while statelist: #convert state combinations to commands
						statespec, img = statelist.pop(0), statelist.pop(0)
						if isinstance(statespec, list):
							statespec = "{{{}}}".format(" ".join(statespec))
						_validate(statespec, img)
						statecmd.append("{} {}".format(statespec, img))

					if not statecmd:
						elementparams = baseimg
					else:
						elementparams = ("[list " + baseimg + " \\\n\t\t" +
							" \\\n\t\t".join(statecmd) + "]")

					elemconfig = elemlist[1] # element configuration
					elemcnfcmd = []
					for optkey, optval in elemconfig.items():
						elemcnfcmd.append(self._resolve_opt_val_pair(optkey,
							optval))
					elemcnfcmd = " \\\n\t\t".join(elemcnfcmd)
					if elemcnfcmd: elemcnfcmd = " \\\n\t\t" + elemcnfcmd
				elif elementname == "vs_api":
					...
				outscript.append("\tttk::style element create " + style + " " +
					elementname + " " + elementparams + elemcnfcmd)
		return outscript

	def _resolve_layout(self, indict):
		outscript = []
		for style, layoutdict in indict.items(): # e.g. "TFrame", {...}
			_validate(style)
			layoutcmd = self._layout_spec(layoutdict)
			outscript.append(("\tttk::style layout " + style + " \\\n\t{\n" +
				layoutcmd + " \n\t}"))
		return outscript

	def _resolve_opt_val_pair(self, option, value):
		"""
		Formats two values that are sure to be a option value pair such
		as {"sticky":"news"} to "-sticky news", applying formatting when
		value is empty or a list.
		"""
		if isinstance(value, list):
			value = [str(i) for i in value]
			value = "{{{}}}".format(" ".join(value))
		_validate(option, value)
		if value == "":
			value = "\"\""
		pair = " -{} {}".format(option, value)
		return pair

	def _layout_spec(self, layoutdict, recursionlayer = 1):
		rl = recursionlayer
		outscript = []
		for element, options in layoutdict.items(): # e.g. "widgElement", {...}
			_validate(element)
			childrencmd = None
			# If the current element has a children option, heavy reformatting
			# is neccessary.
			curelem_command = "\t" * (rl + 1) + element
			for opt, val in options.items(): #e.g. "side", "left"; "children", {...}
				_validate(opt)
				if opt == "children":
					childrencmd = self._layout_spec(val, rl + 1)
				else:
					curelem_command += self._resolve_opt_val_pair(opt, val)
			if childrencmd:
				curelem_command += (" -children \\\n" + "\t" * (rl + 1) + "{\n" +
					"".join(childrencmd) + "\n" + "\t" * (rl + 1) + "}")
			outscript.append(curelem_command)

		outscript = "\n".join(outscript)
		return outscript

	def _resolve_map(self, indict):
		outscript = []
		for style, mapdict in indict.items(): #e.g. "TCheckbutton", {...}
			_validate(style)
			cmdargs = []
			for option, optionconf in mapdict.items(): #e.g. "background", []
				statespecs = ""
				_validate(option)
				for statespecpair in optionconf:
					statelist = statespecpair[0]
					stateattr = statespecpair[1]
					if len(statelist) > 1:
						state = "{{{}}}".format(" ".join(statelist))
					else:
						state = statelist[0]
					_validate(state, stateattr)
					statespecs += "{} {} ".format(state, stateattr)
				cmdargs.append("-{} {}".format(option,
					"{" + statespecs + "}") )

			cmdargs = " \\\n\t\t".join(cmdargs)

			outscript.append(("\tttk::style map " + style + " \\\n\t\t" +
				cmdargs))
		return outscript

def _validate(*tocheck):
	"""
	Raises an error if a regex from RE_FORBIDDEN matches any
	value from tocheck. Purpose is to prevent code injection.
	"""
	for scriptsegm in tocheck:
		if isinstance(scriptsegm, list):
			scriptsegm = [str(i) for i in scriptsegm]
			scriptsegm = "{{{}}}".format(" ".join(scriptsegm))
		if not isinstance(scriptsegm, str):
			scriptsegm = str(scriptsegm)
		for elem in RE_FORBIDDEN:
			if elem[0].search(scriptsegm):
				raise ValueError(("{}".format(scriptsegm) +
					" is in an unallowed format: {}".format(elem[1])))
