
from copy import deepcopy
import json
import typing as t

from schema import And, Or, Schema, SchemaError, Use

import demomgr.constants as CNST
from demomgr.helpers import deepupdate_dict
from demomgr.platforming import should_use_windows_explorer


# You can do silly things with some of these values.
# I do not trust.

class IntClipper:
	def __init__(self, min_: int, max_: int) -> None:
		self._min_constraint = min_
		self._max_constraint = max_

	def validate(self, v: t.Any) -> int:
		if not isinstance(v, int):
			raise SchemaError("Not an int.")
	
		return min(max(v, self._min_constraint), self._max_constraint)


class StringClipper:
	def __init__(self, max_length: int) -> None:
		self._max_length = max(0, max_length)

	def validate(self, v: t.Any) -> str:
		if not isinstance(v, str):
			raise SchemaError("Not a string.")

		return v[:self._max_length]


# No clue how to type hint this.
class EnumTransformer:
	def __init__(self, enum_type) -> None:
		self.enum_type = enum_type

	def validate(self, v):
		return self.enum_type(v)


_bool_schema = Schema(bool)
def validate_launchcmd_template(v: t.Any) -> t.Tuple[str, bool]:
	if not isinstance(v, (list, tuple)) or len(v) != 2:
		raise SchemaError("Invalid argument template object. Expected list or tuple of length 2.")

	string = StringClipper(CNST.CMDARG_MAX).validate(v[0])
	is_template = _bool_schema.validate(v[1])
	if is_template and string not in "DSs":
		raise SchemaError("Invalid template string.")

	return (string, is_template)


class RememberListValidator:
	"""
	RememberListValidators validate the types of submitted values
	against the schema validatables in the given default validators,
	then apply a forward-compatible update scheme of incoming values
	into a copy of the default values, returning it.
	If the validation fails, an unchanged copy of the default is
	returned, all errors suppressed.
	Validators can be omitted, in which case they will be treated
	as `Schema(type(v))` for each default value.

		i. e.: `DEF: [], UPD: [1, 2]` -> `[1, 2]`;
		`DEF: [False, 5], UPD: [True]` -> `[True, 5]`
		`DEF: ["abc", 10], UPD: ["def", "ghi"]` -> `["abc", 10]`
	"""
	def __init__(self, default: t.List, validators: t.Optional[t.List] = None) -> None:
		if validators is None:
			validators = tuple(Schema(type(v)) for v in default)
		else:
			validators = tuple(
				Schema(type(v)) if s is None else s
				for v, s in zip(default, validators)
			)

		self.default: t.List = default
		self.validators: t.List[Schema] = validators

	def validate(self, update_with: t.List) -> t.List:
		if len(self.default) < len(update_with):
			return self.default.copy()

		transformed_values = []
		for schem, newval in zip(self.validators, update_with):
			try:
				transformed_values.append(schem.validate(newval))
			except SchemaError:
				return self.default.copy()

		if len(self.default) == len(update_with):
			return transformed_values

		# If this gets too complex for whatever reason, use deepcopy
		out = self.default.copy()
		out[:len(transformed_values)] = transformed_values
		return out


# Field renames since 2019 me made some really poor, ugly to read
# naming choices. (Converts <=1.8.4 to >=1.9.0 cfg)
_RENAMES = {
	"datagrabmode": "data_grab_mode",
	"demopaths": "demo_paths",
	"evtblocksz": "events_blocksize",
	"__comment": "_comment",
	"firstrun": "first_run",
	"hlaepath": "hlae_path",
	"lastpath": "last_path",
	"lazyreload": "lazy_reload",
	"previewdemos": "preview_demos",
	"steampath": "steam_path",
}


DEFAULT = {
	"data_grab_mode": CNST.DATA_GRAB_MODE.JSON.value,
	"date_format": "%d.%m.%Y %H:%M:%S",
	"demo_paths": [],
	"events_blocksize": 65536,
	"file_manager_launchcmd": [],
	"file_manager_mode": None,
	"file_manager_path": None,
	"_comment": "By messing with the firstrun parameter you acknowledge the disclaimer :P",
	"first_run": True,
	"hlae_path": None,
	"hlae_tf2_exe_name": "tf.exe",
	"last_path": None,
	"lazy_reload": False,
	"preview_demos": True,
	"rcon_port": 27015,
	"rcon_pwd": None,
	"steam_path": None,
	"ui_remember": {
		"launch_tf2": [],
		"settings": [],
		"bulk_operator": [],
	},
	"ui_theme": "Dark",
}


_SCHEMA = Schema(
	{
		"data_grab_mode": And(int, EnumTransformer(CNST.DATA_GRAB_MODE)),
		"date_format": str,
		"demo_paths": [And(str, lambda x: x != "")],
		"events_blocksize": IntClipper(1, 1 << 31),
		"file_manager_launchcmd": [Use(validate_launchcmd_template)],
		"file_manager_mode": Or(
			None,
			And(int, EnumTransformer(CNST.FILE_MANAGER_MODE))
		), # will be set depending on OS when None
		"file_manager_path": Or(None, StringClipper(CNST.PATH_MAX)),
		"_comment": str,
		"first_run": bool,
		"hlae_path": Or(None, StringClipper(CNST.PATH_MAX)),
		"hlae_tf2_exe_name": And(StringClipper(CNST.FILENAME_MAX), lambda x: x != ""),
		"last_path": Or(str, None, int), # str only for pre-1.9.0 comp
		"lazy_reload": bool,
		"preview_demos": bool,
		"rcon_port": IntClipper(0, 65535),
		"rcon_pwd": Or(None, StringClipper(CNST.RCON_PWD_MAX)),
		"steam_path": Or(None, StringClipper(CNST.PATH_MAX)),
		"ui_remember": {
			"launch_tf2": RememberListValidator(
				[False, True, "", "", 0],
				[None, None, None, StringClipper(CNST.CMDLINE_MAX), IntClipper(0, 5000)]
			),
			"settings": RememberListValidator([0]),
			"bulk_operator": RememberListValidator(
				[CNST.BULK_OPERATION.DELETE, ""],
				[EnumTransformer(CNST.BULK_OPERATION), StringClipper(CNST.PATH_MAX)],
			),
		},
		"ui_theme": str,
	},
	ignore_extra_keys = True,
)

def _rename_fields(data: t.Dict) -> t.Dict:
	return {_RENAMES.get(k, k): v for k, v in data.items()}

class Config():

	_cfg = None

	def __init__(self, passed_cfg: t.Dict) -> None:
		"""
		Initializes a demomgr config.

		Will merge the supplied dict with a copy of the default
		config and run a Schema validation on the supplied dict, so a
		SchemaError may be raised.
		May also raise TypeError if the passed object was not of type
		dict.

		Will perform some backwards-compatibility operations on the
		supplied arguments, notably `hlae_path`, `last_path`, `rcon_pwd`
		and `steam_path` will be set to `None` if they should be empty
		strings.
		If `last_path` is a string, it will be set to the index the
		string can be found at in `demo_paths`, or `None` if
		`demo_paths` does not contain `last_path`.
		If `file_manager_mode` is `None`, will be set to a value fitting
		for the system.
		"""

		if not isinstance(passed_cfg, dict):
			raise TypeError(
				f"Bad type for passed config object. Expected dict, was "
				f"{type(passed_cfg).__name__}"
			)

		cfg = deepcopy(DEFAULT)
		deepupdate_dict(cfg, _rename_fields(passed_cfg))
		cfg = _SCHEMA.validate(cfg)

		# It would feel scuffed to put some of these in the schema itself.
		# Pre-1.9.0 path replacement
		for k in ("hlae_path", "last_path", "rcon_pwd", "steam_path"):
			if cfg[k] == "":
				cfg[k] = None

		# Change pre-1.9.0 path to an index
		if isinstance(cfg["last_path"], str):
			try:
				cfg["last_path"] = cfg["demo_paths"].index(cfg["last_path"])
			except ValueError:
				cfg["last_path"] = None

		# Select fm mode based on system
		if cfg["file_manager_mode"] is None:
			cfg["file_manager_mode"] = (
				CNST.FILE_MANAGER_MODE.WINDOWS_EXPLORER if should_use_windows_explorer()
				else CNST.FILE_MANAGER_MODE.USER_DEFINED
			)

		cfg["_comment"] = DEFAULT["_comment"]

		self._cfg = cfg

	def to_json(self) -> str:
		"""
		Returns a json string containing the config, ready to be written
		to a file.
		"""
		return json.dumps(self._cfg, indent = "\t")

	def update(self, updater: t.Dict) -> None:
		"""
		Updates the config from the given dict using the helper function
		`deepupdate_dict`.
		If an argument is supplied that isn't a valid config field, a
		`ValueError` is raised.
		"""
		for k in updater.keys():
			if k not in DEFAULT:
				raise ValueError("Unallowed key: {k!r}")

		deepupdate_dict(self._cfg, updater)

	def __getattr__(self, attr: str) -> t.Any:
		if self._cfg is None or attr not in self._cfg:
			raise AttributeError(f"{type(self).__name__!r} has no attribute {attr!r}")
		return self._cfg[attr]

	def __setattr__(self, attr: str, value: t.Any) -> None:
		if self._cfg is not None and attr in self._cfg:
			self._cfg[attr] = value
		else:
			super().__setattr__(attr, value)

	@classmethod
	def get_default(cls) -> "Config":
		"""
		Creates and returns a new default config.
		"""
		return cls(deepcopy(DEFAULT))
