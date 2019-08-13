'''Offers the filterstr_to_lambdas function that parses a string of the 
following scheme to a list of lambdas that can be applied to elements to 
filter them.
The generated lambdas should be safe.

A valid filterstring is one or more key-parameter pairs, seperated by
	<Whitespace>,<Whitespace>

A key-parameter pair looks like this:
	[Key]:<Whitespace>[Parameter]
The k-p pair seperator is optional if the k-p pair is the last one.

Valid parameters include:
	A tuple of strings [ ("a", "b", 'c', ) ] <regex module required>
	A tuple of unquoted strings [ (a, b, c) ]
	A string [ "a" ]  <regex module required>
	An unquoted string [ a ]
	A numeric range [ 1..2 ] [ ..2 ]
		(Ranges are inclusive.)

'''

from ast import literal_eval

import re
try:
	import regex
	NO_REGEX_MODULE = False
except ImportError:
	NO_REGEX_MODULE = True

from _constants import FILTERDICT

KEY_PARAM_SEP = ":"
KEY_NEGATOR = "!"

class SIGNS: #enum?
	EQ = "=="
	LTE = "<="
	GTE = ">="
	LT = "<"
	GT = ">"

FAIL_OUT_LEN = 10

# TODO: ADD BETTER REGEX LIB TO DEPENDENCIES
# https://pypi.org/project/regex/

# Current quoteless string chars: [A-Za-z0-9_-]

re_quoted_string = re.compile(r"""(?:(['"])(.*?(?:(?<!\\)(?:\\\\)*))\1)""")
# For some reason, groups will be inaccessible without the encasing
# non-capturing group.

re_unesc_dbl_quotes = re.compile(r"""(?<!\\)(?P<slashes>\\\\)*(?=\")""")

re_key = re.compile("^[A-Za-z0-9_-]*" + KEY_PARAM_SEP + "\\s*")

# Parameter format regex
# 0: validation regex; 1: parameter matching regex (gets applied to the full
# match of 0), 2: group of 1 to read from, unless 2 is "RANGE"
re_params = {
	"quoteless_string_tuple": (
		re.compile(r"^\([A-Za-z0-9_-]+(?:\s*,\s*[A-Za-z0-9_-]+)" \
			"*\s*(?:,\s*)?\)\s*(?:,\s*|$)"),
		re.compile(r"[A-Za-z0-9_-]+"), 0,
	),
	"num_range": (
		re.compile(r"(?:(^[0-9]+)|^)\.\.(?(1)[0-9]*|[0-9]+)\s*(?:,\s*|$)"),
		re.compile(r"(?:(?P<start>[0-9]+)?\.\.(?P<end>[0-9]+)?)"),
		"RANGE",
		# range extraction regex must have 2 groups called "start" and "end"
	),
	"quoteless_string": (
		re.compile(r"^[A-Za-z0-9_-]+\s*(?:,\s*|$)"),
		re.compile(r"^[A-Za-z0-9_-]*"), 0,
	),
}

if not NO_REGEX_MODULE:
	re_params["string_tuple"] = ( regex.compile(r"""
		(?(DEFINE)
			(?<string> (['"]).*?(?&even_backslash)\2 )
			(?<even_backslash> (?:((?<=[^\\]))(?:\\\\)*) )
			(?<separator> \s*,\s* )
			(?<separator_end> \s*(?:,\s*)? )
			(?<separator_end_line> \s*(?:,\s*|$) )
		)
		\(\s*(?>(?&string))((?&separator)(?&string))*(?&separator_end)?\)
		(?&separator_end_line)""", re.X + regex.VERSION1
	),
	# DO NOT BACKTRACK INTO FIRST string GROUP
	# good got all the hours gone to waste and i just had to make that
	# group atomic
		re_quoted_string, 2, )
	re_params["string"] = (
		regex.compile(r"""^(?>(['"]).*?(?:(?<=[^\\])(?:\\\\)*)\1)?""" \
			"""\s*(,\s*|$)"""), re_quoted_string, 2,
	)

def escapeinput(raw):
	r"""Adds escape char (\) in front of all occurrences of \, ' and " """
	raw = raw.replace("\\", "\\\\")
	raw = raw.replace('"', '\\"')
	raw = raw.replace("'", "\\'") # technically unneccessary as all strings
	# in FILTERDICT are double-quoted.
	return raw

# Key extraction
def _extract_key(inp):
	'''Grabs the key (character chain of [A-Za-z0-9_-] ended by ":",
	followed by 0+ whitspace chars and then the key's value).
	inp is expected to have no leading whitespace.
	Returns: the key <Str>, whether the key was negated <Bool> and the
	input string with the key and potential whitespace cut off.
	'''
	key_negated = False
	if inp[0] == KEY_NEGATOR:
		key_negated = True
		inp = inp[len(KEY_NEGATOR):]
	raw_key = re_key.search(inp)
	if raw_key is None:
		raise ValueError("Could not find valid key at around: " \
			"\"{}\"".format(inp[:FAIL_OUT_LEN]))
	raw_key = raw_key[0]
	key_name = raw_key.split(KEY_PARAM_SEP)[0]

	return key_name, key_negated, inp[len(raw_key):]

# Parameter container type extraction
def _ident_and_extract_param(inp):
	'''Grabs the first parameter of inp and breaks it down into escaped
	strings using regular expressions and ast.literal_eval.
	A parameter may be any of the ones defined in the module docstring.
	inp is expected to have no leading whitespace.
	Returns: The parameter(s) in a list, whether the parameter is a range,
	the input with parameters and whitespace as well as a potential comma
	following it cut off.
	'''
	for exp_name, exp_tuple in re_params.items():
		expression = exp_tuple[0]
		res = expression.search(inp)
		if res is not None:
			break
	if res is None:
		errstr = "No parameter could be identified at around: \"{}\"".format(
			inp[:FAIL_OUT_LEN])
		if NO_REGEX_MODULE:
			errstr = errstr + "; Try installing the regex module."
		raise ValueError(errstr)
	# print(exp_name)
	raw_param = res[0]

	param_matches = exp_tuple[1].finditer(raw_param)

	if exp_tuple[2] == "RANGE":
		# param_matches should be of length 1, the single element defining
		# the capture groups "start" and "end"
		is_range = True
		param_matches = next(param_matches)
		final_params = [param_matches["start"], param_matches["end"]]
	else:
		is_range = False
		if not param_matches:
			raise ValueError("Apparently, the validator function {} is " \
				"garbage. Please report this.".format(exp_name))
		tmp_params = [i[exp_tuple[2]] for i in param_matches]
		tmp_params = [re_unesc_dbl_quotes.sub(r"\g<slashes>\\", i)
			for i in tmp_params]
		final_params = [escapeinput(
			literal_eval('"' + i + '"' )) for i in tmp_params]
		# As the string is encased with double quotes for the literal eval,
		# which allows for parsing of escape characters, non-escaped double
		# quotes would raise a parser error within literal_eval. Those are
		# escaped in the regex above.
		# print(final_params)

	return final_params, is_range, inp[len(raw_param):]

def _extract_keys_and_params(inp):
	'''Repeatedly removes a key and a parameter from inp until nothing
	is left, returns a dict where:
	{<key>:[[<param0>, <param1>, ...>], <is_key_negated>, <is_range>], ...}
	'''
	filterstring = inp.strip()
	parsed_str = {}

	while filterstring != "":
		keyres = _extract_key(filterstring)
		# print("Key found:", " || ".join([str(i) for i in keyres]))
		filterstring = keyres[2]
		paramres = _ident_and_extract_param(filterstring)
		# print("Parameters found:", " || ".join([str(i) for i in paramres]))
		parsed_str[keyres[0]] = [paramres[0], keyres[1], paramres[1]]
		filterstring = paramres[2]

	return parsed_str

def filterstr_to_lambdas(inp):
	'''Creates a list of lambdas that correspond to the filtering input
	using _constants.FILTERDICT .
	'''
	lambdas = []

	key_param_dict = _extract_keys_and_params(inp)
	for key, spec in key_param_dict.items():
		params = spec[0]
		is_negated = spec[1]
		is_range = spec[2]
		if not key in FILTERDICT:
			raise ValueError("Unknown key: \"{}\"".format(key))
		lambdastub = FILTERDICT[key][0]
		req_type = FILTERDICT[key][1]
		if is_range: # Range-ify
			if is_negated:
				rngtup = ((params[0], SIGNS.LT), (params[1], SIGNS.GT))
				logic_conjugator = " or "
			else:
				rngtup = ((params[0], SIGNS.GTE), (params[1], SIGNS.LTE))
				logic_conjugator = " and "

			lambdastubs = [lambdastub.format(req_type(i), sign = sign)
				for i, sign in rngtup if i is not None]
			lambdas.append(eval("lambda x: {}".format(
				logic_conjugator.join(lambdastubs))))
			#!(1..5) -> !(>= 1 & <= 5) -> (< 1 | > 5)
			#!(1..) ->  !(>= 1) ->        (< 1)
			#!(..5) ->  !(<= 5) ->        (> 5)
			#!(5..1) -> !(>= 5 & <= 1) -> (< 5 | > 1)
		else: # Regular comparision
			lambdastubs = [lambdastub.format(req_type(i), sign = SIGNS.EQ)
				for i in params]
			lambdas.append(eval("lambda x: {}{}{}".format(
				"not (" * is_negated,
				" or ".join(lambdastubs),
				")" * is_negated, )))

	return lambdas