from copy import deepcopy
import json

from schema import And, Or, Schema

import demomgr.constants as CNST
from demomgr.helpers import deepupdate_dict

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
	"data_grab_mode": 2,
	"date_format": "%d.%m.%Y %H:%M:%S",
	"demo_paths": [],
	"events_blocksize": 65536,
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
		"bookmark_setter": [],
		"launch_tf2": [],
		"settings": [],
	},
	"ui_theme": "Dark",
}

_SCHEMA = Schema(
	{
		"data_grab_mode": And(
			int,
			lambda x: any(x == e.value for e in CNST.DATAGRABMODE.__members__.values()),
		),
		"date_format": str,
		"demo_paths": [And(str, lambda x: x != "")],
		"events_blocksize": And(int, lambda x: x > 0),
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
			"bookmark_setter": [object],
			"launch_tf2": [object],
			"settings": [object],
		},
		"ui_theme": str,
	},
	ignore_extra_keys = True,
)

def _rename_fields(data):
	return {_RENAMES.get(k, k): v for k, v in data.items()}

class Config():

	_cfg = None

	def __init__(self, cfg):
		"""
		Initializes a demomgr config.

		Will run a Schema validation on the supplied dict, so a SchemaError
		may be raised.

		Will perform some backwards-compatibility operations on the
		supplied arguments, notably `hlae_path`, `last_path`, `rcon_pwd`
		and `steam_path` will be set to `None` if they should be empty strings.
		If `last_path` is a string, it will be set to the index the string can
		be found at in `demo_paths`, or `None` if `demo_paths` does not contain
		`last_path`.
		"""

		cfg = _rename_fields(cfg)
		cfg = _SCHEMA.validate(cfg)

		# Schema could also do these, but not the `last_path` conversion, so
		# keeping all data compatibility transformation here
		for k in ("hlae_path", "last_path", "rcon_pwd", "steam_path"):
			if cfg[k] == "":
				cfg[k] = None

		if isinstance(cfg["last_path"], str):
			try:
				cfg["last_path"] = cfg["demo_paths"].index(cfg["last_path"])
			except ValueError:
				cfg["last_path"] = None

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
