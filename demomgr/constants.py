from schema import And

CFG_FOLDER = ".demomgr"
CFG_NAME = "config.cfg"
DEFAULT_CFG = {
	"datagrabmode": 0,
	"date_format": "%d.%m.%Y %H:%M:%S",
	"demopaths": [],
	"evtblocksz": 65536,
	"__comment": "By messing with the firstrun parameter you acknowledge "
		"that you've read the Terms of use.",
	"firstrun": True,
	"hlaepath": "",
	"lastpath": "",
	"lazyreload": False,
	"previewdemos": True,
	"rcon_port": 27015,
	"rcon_pwd": "",
	"steampath": "",
	"ui_remember": {
		"bookmark_setter": [],
		"launch_tf2": [],
		"settings": [],
	},
	"ui_theme": "Dark",
}
DEFAULT_CFG_SCHEMA = {
	"datagrabmode": int,
	"date_format": str,
	"demopaths": [And(str, lambda x: x != "")],
	"evtblocksz": int,
	"__comment": str,
	"firstrun": bool,
	"hlaepath": str,
	"lastpath": str,
	"lazyreload": bool,
	"previewdemos": bool,
	"rcon_port": int,
	"rcon_pwd": str,
	"steampath": str,
	"ui_remember": {
		"bookmark_setter": [object], "launch_tf2": [object],
		"settings": [object],
	},
	"ui_theme": str,
}
WELCOME = ("Hi and Thank You for using Demomgr!\n\nA config file has been "
	"created.\n\nThis script is able to delete files if you tell it to.\nI in no way "
	"guarantee that this script is safe or 100% reliable and will not take any "
	"responsibility for lost data, damaged drives and/or destroyed hopes and dreams.\n"
	"This program is licensed via the MIT Licence, by clicking the accept button below "
	"you confirm that you have read and accepted the license.")
EVENT_FILE = "_events.txt"
DATE_FORMATS = (
	"%d.%m.%Y %H:%M:%S",
	"%d.%m.%Y",
	"%m/%d/%Y %H:%M:%S",
	"%m/%d/%Y",
)
EVENTFILE_FILENAMEFORMAT = "(?<= \\(\").+(?=\" at)" #regex
EVENTFILE_BOOKMARK = "Bookmark"
EVENTFILE_KILLSTREAK = "Killstreak"
STATUSBARDEFAULT = "Ready."
TF2_EXE_PATH = "steamapps/common/team fortress 2/hl2.exe"
TF2_HEAD_PATH = "steamapps/common/team fortress 2/tf/"
TF2_LAUNCHARGS = ["-steam", "-game", "tf"]
HLAE_EXE = "hlae.exe"
HLAE_HOOK_DLL = "AfxHookSource.dll"
HLAE_LAUNCHARGS0 = ["-customLoader", "-noGui", "-autoStart", "-hookDllPath"]
HLAE_LAUNCHARGS1 = ["-programPath"]
HLAE_LAUNCHARGS2 = ["-cmdLine"]
HLAE_ADD_TF2_ARGS = ["-insecure", "+sv_lan", "1"]
STEAM_CFG_PATH0 = "userdata/"
STEAM_CFG_PATH1 = "config/localconfig.vdf"
REPLACEMENT_CHAR = "\uFFFD"
LAUNCHOPTIONSKEYS = (
	"UserLocalConfigStore", "Software", "Valve", "Steam", "Apps", "440", "LaunchOptions",
)
STEAM_CFG_USER_NAME = '["UserLocalConfigStore"]["friends"]["PersonaName"]'
GUI_UPDATE_WAIT = 20 # Setting this to lower values might lock the UI, use with care.
THEME_SUBDIR = "ui_themes"
THEME_PACKAGES = {
	"Dark": ("dark.tcl", "demomgr_dark", "dark"),
}
# 0: tcl file, 1: theme name, 2: resource dir name
FALLBACK_HEADER = {"dem_prot": 3, "net_prot": 24, "hostname": "",
	"clientid": "", "map_name": "", "game_dir": "", "playtime": 0,
	"tick_num": 0, "framenum": 0, "tickrate": 0,
}
HEADER_HUMAN_NAMES = {"hostname": "Hostname", "clientid": "Playername",
	"map_name": "Map", "playtime": "Playtime",
	"tick_num": "No. of ticks", "game_dir": "Game directory",
}
