from enum import IntEnum

class DATAGRABMODE(IntEnum):
	NONE = 0
	EVENTS = 1
	JSON = 2

CFG_FOLDER = ".demomgr"
CFG_NAME = "config.cfg"
WELCOME = (
	"Hi and Thank You for using Demomgr!\n\nA config file has been "
	"created.\n\nThis program is able to delete files if you tell it to.\n"
	"I can't guarantee that Demomgr is 100% safe or reliable and will not take any "
	"responsibility for lost data, damaged drives and/or destroyed hopes and dreams.\n"
	"This program is licensed via the MIT License."
)
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
GUI_UPDATE_WAIT = 30 # Setting this to lower values might lock the UI, use with care.
THEME_SUBDIR = "ui_themes"
# 0: tcl file, 1: theme name, 2: resource dir name
THEME_PACKAGES = {
	"Dark": ("dark.tcl", "demomgr_dark", "dark"),
}
FALLBACK_HEADER = {
	"dem_prot": 3, "net_prot": 24, "hostname": "",
	"clientid": "", "map_name": "", "game_dir": "", "playtime": 0,
	"tick_num": 0, "framenum": 0, "tickrate": 0,
}
HEADER_HUMAN_NAMES = {
	"hostname": "Hostname", "clientid": "Playername",
	"map_name": "Map", "playtime": "Playtime",
	"tick_num": "No. of ticks", "game_dir": "Game directory",
}
