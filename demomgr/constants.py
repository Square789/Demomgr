from enum import IntEnum

# Important for them to have these values since some indexing stuff for the
# events and json is being done by subtracting 1 from them.
# Not that there ever will be a reason to change these or add new containers
# realistically.
class DATA_GRAB_MODE(IntEnum):
	NONE = 0
	EVENTS = 1
	JSON = 2

	def get_display_name(self):
		if self is self.NONE:
			return "None"
		elif self is self.EVENTS:
			return EVENT_FILE
		elif self is self.JSON:
			return ".json"

class FILE_MANAGER_MODE(IntEnum):
	WINDOWS_EXPLORER = 0
	USER_DEFINED = 1

class BULK_OPERATION(IntEnum):
	MOVE = 0
	COPY = 1
	DELETE = 2

CFG_FOLDER = ".demomgr"
CFG_NAME = "config.cfg"
WELCOME = (
	"Hi and Thank You for using Demomgr!\n\nA config file has been "
	"created.\n\nThis program is able to delete files if you tell it to.\n"
	"I can't guarantee that Demomgr is 100% safe or reliable and will not take any "
	"responsibility for lost data, damaged drives and/or destroyed hopes and dreams.\n"
	"(Look, I use it personally, it's probably fine.)\n\n"
	"This program is licensed via the BSD 3-Clause License."
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
TF2_HEAD_PATH = "steamapps/common/Team Fortress 2/"
TF2_FS_ROOT_TAIL_PATH = "tf/"
TF2_EXE_TAIL_PATH = "hl2.exe"
TF2_LAUNCHARGS = ["-steam", "-game", "tf"]
TF2_GAME_ID = "440"
APPLAUNCH_ARGS = ["-applaunch", TF2_GAME_ID]
HLAE_EXE = "hlae.exe"
HLAE_HOOK_DLL = "AfxHookSource.dll"
HLAE_LAUNCHARGS0 = ["-customLoader", "-noGui", "-autoStart", "-hookDllPath"]
HLAE_LAUNCHARGS1 = ["-programPath"]
HLAE_LAUNCHARGS2 = ["-cmdLine"]
HLAE_ADD_TF2_ARGS = ["-insecure", "+sv_lan", "1"]
LIBRARYFOLDER_VDF = "steamapps/libraryfolders.vdf"
STEAM_CFG_PATH0 = "userdata/"
STEAM_CFG_PATH1 = "config/localconfig.vdf"
STEAM_EXE = "steam.exe"
STEAM_SH = "steam.sh"
REPLACEMENT_CHAR = "\uFFFD"
STEAM_CFG_LAUNCH_OPTIONS = (
	"UserLocalConfigStore", "Software", "Valve", "Steam", "Apps", TF2_GAME_ID, "LaunchOptions",
)
STEAM_CFG_USER_NAME = ("UserLocalConfigStore", "friends", "PersonaName")
# Setting this to lower values might lock the UI, use with care.
GUI_UPDATE_WAIT = 30
THEME_SUBDIR = "ui_themes"
# 0: tcl file, 1: theme name, 2: resource dir name
THEME_PACKAGES = {
	"Dark": ("dark.tcl", "demomgr_dark", "dark"),
}
HEADER_HUMAN_NAMES = {
	"hostname": "Hostname", "clientid": "Playername",
	"map_name": "Map", "playtime": "Playtime",
	"tick_num": "No. of ticks", "game_dir": "Game directory",
}
