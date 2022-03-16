"""
Offers the filterstr_to_lambdas function that parses a string of the
following scheme to a list of lambdas that can be applied to elements to
filter them.
The generated lambdas should be safe.

A valid filterstring is one or more key-parameter pairs, seperated by
	<Whitespace>,<Whitespace>

A key-parameter pair looks like this:
	[Key]:<Whitespace>[Parameter]
The k-p pair seperator is optional if the k-p pair is the last one.

Valid parameters include:
	A tuple of strings [ ("a", "b", 'c', ) ]
	A tuple of unquoted strings [ (a, b, c) ]
	A string [ "a" ]
	An unquoted string [ a ]
	A numeric range [ 1..2 ] [ ..2 ]
		(Ranges are inclusive.)
"""

from ast import literal_eval

import re
import regex

class FILTERFLAGS:
	HEADER = 1
	FILESYS = 2

FILTERDICT = {
	"name":              ('"{}" in x["name"]', str, 0),
	"bookmark_contains": ('any("{}" in b.value for b in x["demo_info"].bookmarks)', str, 0),
	"map":               ('"{}" in x["header"]["map_name"]', str, FILTERFLAGS.HEADER),
	"hostname":          ('"{}" in x["header"]["hostname"]', str, FILTERFLAGS.HEADER),
	"clientid":          ('"{}" in x["header"]["clientid"]', str, FILTERFLAGS.HEADER),
	"killstreaks":       ('len(x["demo_info"].killstreak_peaks) {sign} {}', int, 0),
	"bookmarks":         ('len(x["demo_info"].bookmarks) {sign} {}', int, 0),
	"beststreak":        ('max((i.value for i in x["demo_info"].killstreak_peaks), default=-1) {sign} {}', int, 0),
	"moddate":           ('x["filedata"]["modtime"] {sign} {}', int, FILTERFLAGS.FILESYS),
	"filesize":          ('x["filedata"]["filesize"] {sign} {}', int, FILTERFLAGS.FILESYS),
}
# [0] will be passed through eval(), prefixed with "lambda x: "; {} replaced
# by [1] called with ESCAPED user input as parameter
# -> eval("lambda x:\"" + str("koth_") + "\" in x[\"name\"]") -> lambda x: "koth_" in x["name"]
# [2] denotes whether drive access will have to be made so the filtering loop doesn't waste
# resources on requests that don't require such

KEY_PARAM_SEP = ":"
KEY_NEGATOR = "!"

class SIGNS: #enum?
	EQ = "=="
	LTE = "<="
	GTE = ">="
	LT = "<"
	GT = ">"

FAIL_OUT_LEN = 10

# Current quoteless string chars: [A-Za-z0-9_-]

RE_QUOTED_STRING = re.compile(r"""(?:(['"])(.*?(?:(?<!\\)(?:\\\\)*))\1)""")
# For some reason, groups will be inaccessible without the encasing
# non-capturing group.

RE_UNESC_DBL_QUOT = re.compile(r"""(?<!\\)(?P<slashes>\\\\)*(?=\")""")

RE_KEY = re.compile(r"^[A-Za-z0-9_-]*" + KEY_PARAM_SEP + r"\s*")

# Parameter format regex
# 0: validation regex; 1: parameter matching regex (gets applied to the full
# match of 0), 2: group of 1 to read from, unless 2 is -1.
# In that case it's a range extraction regex, which must have 2 groups called
# "start" and "end"
RE_PARAMS = {
	"quoteless_string_tuple": (
		re.compile(r"^\([A-Za-z0-9_-]+(?:\s*,\s*[A-Za-z0-9_-]+)*\s*(?:,\s*)?\)\s*(?:,\s*|$)"),
		re.compile(r"[A-Za-z0-9_-]+"),
		0,
	),
	"num_range": (
		re.compile(r"(?:(^[0-9]+)|^)\.\.(?(1)[0-9]*|[0-9]+)\s*(?:,\s*|$)"),
		re.compile(r"(?:(?P<start>[0-9]+)?\.\.(?P<end>[0-9]+)?)"),
		-1,
	),
	"quoteless_string": (
		re.compile(r"^[A-Za-z0-9_-]+\s*(?:,\s*|$)"),
		re.compile(r"^[A-Za-z0-9_-]+"),
		0,
	),
	"string_tuple": (
		regex.compile(r"""
			(?(DEFINE)
				(?<string> (['"]).*?(?&even_backslash)\2 )
				(?<even_backslash> (?:((?<=[^\\]))(?:\\\\)*) )
				(?<separator> \s*,\s* )
				(?<separator_end> \s*(?:,\s*)? )
				(?<separator_end_line> \s*(?:,\s*|$) )
			)
			\(\s*(?>(?&string))((?&separator)(?&string))*(?&separator_end)?\)
			(?&separator_end_line)""", re.X + regex.VERSION1),
		RE_QUOTED_STRING,
		2
	),
	"string": (
		regex.compile(r"""^(?>(['"]).*?(?:(?<=[^\\])(?:\\\\)*)\1)\s*(,\s*|$)"""),
		RE_QUOTED_STRING,
		2,
	),
}

def escapeinput(raw):
	r"""Adds escape char (`\`) in front of all occurrences of `\`, `'` and `"`."""
	raw = raw.replace("\\", "\\\\")
	raw = raw.replace('"', '\\"')
	raw = raw.replace("'", "\\'") # technically unneccessary as all strings
	# in FILTERDICT are double-quoted.
	return raw

# Key extraction
def _extract_key(inp):
	"""
	Grabs the key (character chain of [A-Za-z0-9_-] ended by ":",
	followed by 0+ whitspace chars and then the key's value).
	inp is expected to have no leading whitespace.
	Returns: the key <Str>, whether the key was negated <Bool> and the
	input string with the key and potential whitespace cut off.
	"""
	key_negated = False
	if inp[0] == KEY_NEGATOR:
		key_negated = True
		inp = inp[len(KEY_NEGATOR):]
	raw_key = RE_KEY.search(inp)
	if raw_key is None:
		raise ValueError(f"Could not find valid key around: \"{inp[:FAIL_OUT_LEN]}\"")
	raw_key = raw_key[0]
	key_name = raw_key.split(KEY_PARAM_SEP)[0]

	return key_name, key_negated, inp[len(raw_key):]

# Parameter container type extraction
def _ident_and_extract_param(inp):
	"""
	Grabs the first parameter of inp and breaks it down into escaped
	strings using regular expressions and ast.literal_eval.
	A parameter may be any of the ones defined in the module docstring.
	inp is expected to have no leading whitespace.
	Returns: The parameter(s) in a list, whether the parameter is a range,
	the input with parameters and whitespace as well as a potential comma
	following it cut off.
	"""
	for exp_name, (id_re, val_re, re_group) in RE_PARAMS.items():
		res = id_re.search(inp)
		if res is not None:
			break
	else:
		raise ValueError(f"No parameter could be identified around: \"{inp[:FAIL_OUT_LEN]}\"")
	raw_param = res[0]

	param_matches = val_re.finditer(raw_param)
	if not param_matches:
		raise ValueError(
			f"Apparently, the validator function {exp_name} is garbage. "
			f"Please report this."
		)

	if re_group == -1:
		is_range = True
		# param_matches should be of length 1, the single element defining
		# the capture groups "start" and "end"
		param_matches = next(param_matches)
		final_params = [param_matches["start"], param_matches["end"]]
	else:
		is_range = False
		tmp_params = [i[re_group] for i in param_matches]
		tmp_params = [RE_UNESC_DBL_QUOT.sub(r"\g<slashes>\\", i) for i in tmp_params]
		final_params = [escapeinput(literal_eval('"' + i + '"')) for i in tmp_params]
		# As the string is encased with double quotes for the literal eval,
		# which allows for parsing of escape characters, non-escaped double
		# quotes would raise a parser error within literal_eval. Those are
		# escaped in the regex above.

	return final_params, is_range, inp[len(raw_param):]

def _extract_keys_and_params(inp):
	"""
	Repeatedly removes a key and a parameter from inp until nothing
	is left, returns a dict where:
	{<key>:[[<param0>, <param1>, ...>], <is_key_negated>, <is_range>], ...}
	"""
	filterstring = inp.strip()
	parsed_str = {}

	while filterstring:
		key, key_negated, key_remainder = _extract_key(filterstring)
		params, is_range, param_remainder = _ident_and_extract_param(key_remainder)
		parsed_str[key] = [params, key_negated, is_range]
		filterstring = param_remainder

	return parsed_str

def process_filterstring(inp):
	"""
	Returns a two-element tuple where 0 is a list of lambdas that correspond
	to the filtering input using this module's FILTERDICT and 1 is each identified
	filtering key's flag ORed together.
	"""
	lambdas = []
	flags = 0

	key_param_dict = _extract_keys_and_params(inp)
	for key, (params, is_negated, is_range) in key_param_dict.items():
		if key not in FILTERDICT:
			raise ValueError(f"Unknown key: {key!r}")
		flags |= FILTERDICT[key][2]
		lambdastub = FILTERDICT[key][0]
		req_type = FILTERDICT[key][1]
		if is_range: # Range-ify
			if is_negated:
				rngtup = ((params[0], SIGNS.LT), (params[1], SIGNS.GT))
				logic_conjugator = " or "
			else:
				rngtup = ((params[0], SIGNS.GTE), (params[1], SIGNS.LTE))
				logic_conjugator = " and "

			lambdastubs = [
				lambdastub.format(req_type(i), sign = sign)
				for i, sign in rngtup if i is not None
			]
			lambdas.append(eval(f"lambda x: {logic_conjugator.join(lambdastubs)}"))
			#!(1..5) -> !(>= 1 & <= 5) -> (< 1 | > 5)
			#!(1..) ->  !(>= 1) ->        (< 1)
			#!(..5) ->  !(<= 5) ->        (> 5)
			#!(5..1) -> !(>= 5 & <= 1) -> (< 5 | > 1)
		else: # Regular comparision
			lambdastubs = [lambdastub.format(req_type(i), sign = SIGNS.EQ) for i in params]
			lambdas.append(eval(
				"lambda x: {}{}{}".format(
					"not (" * is_negated,
					" or ".join(lambdastubs),
					")" * is_negated,
				)
			))

	return lambdas, flags
