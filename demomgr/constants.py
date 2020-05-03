from schema import And

CFG_FOLDER = ".demomgr"
CFG_NAME = "config.cfg"
DEFAULT_CFG = {
	"demopaths": [],
	"ui_remember": {
		"bookmark_setter": [],
		"launch_tf2": [],
	},
	"lastpath": "",
	"firstrun": True,
	"__comment": "By messing with the firstrun parameter you acknowledge "
		"that you've read the Terms of use.",
	"datagrabmode": 0,
	"previewdemos": True,
	"steampath": "",
	"hlaepath": "",
	"evtblocksz": 65536,
	"ui_theme": "Dark",
	"lazyreload": False,
}
# Config values that are passed on to other classes/modules
SHARED_CFG_KEYS = ("datagrabmode", "steampath", "hlaepath", "evtblocksz")
DEFAULT_CFG_SCHEMA = {
	"demopaths": [And(str, lambda x: x != "")], "ui_remember": {
		"bookmark_setter": [object], "launch_tf2": [object],
	},
	"lastpath": str, "firstrun": bool, "__comment": str,
	"datagrabmode": int, "previewdemos": bool, "steampath": str, "hlaepath": str,
	"evtblocksz": int, "ui_theme": str, "lazyreload": bool,
}
EVENT_BACKUP_FOLDER = "_eventbackup"
WELCOME = ("Hi and Thank You for using Demomgr!\n\nA config file has been "
	"created.\n\nThis script is able to delete files if you tell it to.\nI in no way "
	"guarantee that this script is safe or 100% reliable and will not take any "
	"responsibility for lost data, damaged drives and/or destroyed hopes and dreams.\n"
	"This program is licensed via the MIT Licence, by clicking the accept button below "
	"you confirm that you have read and accepted the license.")
EVENT_FILE = "_events.txt"
DATE_FORMAT = "%d.%m.%Y  %H:%M:%S"
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

# Zero-Parameter values: 0x0   - 0xFF
# One-Parameter values:  0x100 - 0xFFFF
# |---Info level:        0x100 - 0x1FF
# '---Result level:      0x200 - ?
# etc.
class THREADSIG:
	SUCCESS = 0x0
	FAILURE = 0x1
	ABORTED = 0x2
	INFO_CONSOLE = 0x100
	INFO_STATUSBAR = 0x101
	RESULT_DEMODATA = 0x200
	RESULT_FS_INFO = 0x201
	RESULT_HEADER = 0x202

class THREADGROUPSIG:
	FINISHED = 0
	CONTINUE = 1
	HOLDBACK = 2
