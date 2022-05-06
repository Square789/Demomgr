from copy import deepcopy
import json

from schema import And, Or, Schema, SchemaError

import demomgr.constants as CNST
from demomgr.helpers import deepupdate_dict
from demomgr.platforming import should_use_windows_explorer

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
	"file_manager_mode": None,
	"file_manager_path": None,
	"_comment": "By messing with the firstrun parameter you acknowledge "
		"the disclaimer :P",
	"first_run": True,
	"hlae_path": None,
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

class EnumTransformer:
	def __init__(self, enum_type) -> None:
		self.enum_type = enum_type

	def validate(self, v):
		return self.enum_type(v)


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
	def __init__(self, default, validators = None) -> None:
		if validators is None:
			validators = tuple(Schema(type(v)) for v in default)
		else:
			validators = tuple(
				Schema(type(v)) if s is None else s
				for v, s in zip(default, validators)
			)

		self.default = default
		self.validators = validators

	def validate(self, update_with):
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


_SCHEMA = Schema(
	{
		"data_grab_mode": And(int, EnumTransformer(CNST.DATA_GRAB_MODE)),
		"date_format": str,
		"demo_paths": [And(str, lambda x: x != "")],
		"events_blocksize": And(int, lambda x: x > 0),
		"file_manager_mode": Or(
			None,
			And(int, EnumTransformer(CNST.FILE_MANAGER_MODE))
		), # will be set depending on OS when None
		"file_manager_path": Or(None, str),
		"_comment": str,
		"first_run": bool,
		"hlae_path": Or(None, str),
		"last_path": Or(str, None, int), # str only for pre-1.9.0 comp
		"lazy_reload": bool,
		"preview_demos": bool,
		"rcon_port": int,
		"rcon_pwd": Or(None, str),
		"steam_path": Or(None, str),
		"ui_remember": {
			"launch_tf2": RememberListValidator([False, True, "", "", 0]),
			"settings": RememberListValidator([0]),
			"bulk_operator": RememberListValidator(
				[CNST.BULK_OPERATION.DELETE, ""],
				[EnumTransformer(CNST.BULK_OPERATION), None],
			),
		},
		"ui_theme": str,
	},
	ignore_extra_keys = True,
)

def _rename_fields(data):
	return {_RENAMES.get(k, k): v for k, v in data.items()}

class Config():

	_cfg = None

	def __init__(self, passed_cfg):
		"""
		Initializes a demomgr config.

		Will merge the supplied dict with a copy of the default
		config and run a Schema validation on the supplied dict, so a
		SchemaError may be raised.

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

	def to_json(self):
		"""
		Returns a json string containing the config, ready to be written
		to a file.
		"""
		return json.dumps(self._cfg, indent = "\t")

	def update(self, **kwargs):
		"""
		Updates the config from the given kwargs using the helper function
		`deepupdate_dict`.
		If an argument is supplied that isn't a valid config field, a
		`ValueError` is raised.
		"""
		for k in kwargs.keys():
			if k not in DEFAULT:
				raise ValueError("Unallowed key: {k!r}")

		deepupdate_dict(self._cfg, kwargs)

	def __getattr__(self, attr):
		if self._cfg is None or attr not in self._cfg:
			raise AttributeError(f"{type(self).__name__!r} has no attribute {attr!r}")
		return self._cfg[attr]

	def __setattr__(self, attr, value):
		if self._cfg is not None and attr in self._cfg:
			self._cfg[attr] = value
		else:
			super().__setattr__(attr, value)

	@classmethod
	def load_and_validate(cls, file_path):
		"""
		Loads and validates the configuration file from the given file
		path.
		May raise: JSONDecodeError, any sort of OSError from opening a
		protected/nonexistent/used file and any error `Config.__init__`
		may raise.
		"""
		with open(file_path, "r") as f:
			data = json.load(f)
		return cls(data)

	@classmethod
	def get_default(cls):
		"""
		Creates and returns a new default config.
		"""
		return cls(deepcopy(DEFAULT))
