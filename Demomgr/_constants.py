#Values. These are more or less static, but should not be configured.

CFG_FOLDER = ".demomgr"
CFG_NAME = "config.cfg"
# ICONNAME = "demmgr.ico",
DEFAULT_CFG = {
	"demopaths":[],
	"lastpath":"",
	"firstrun":True,
	"__comment":"By messing with the firstrun parameter you acknowledge that you've read the Terms of use.",
	"datagrabmode":0,
	"previewdemos":True,
	"steampath":"",
	"evtblocksz":65536,
	"ui_theme":"Dark"
}
DEFAULT_CFG_TYPES = {
	"demopaths":list, "lastpath":str, "firstrun": bool, "__comment":str,
	"datagrabmode":int, "previewdemos":bool, "steampath":str,
	"evtblocksz":int, "ui_theme":str
}
EVENT_BACKUP_FOLDER = "_eventbackup"
WELCOME =  ("Hi and Thank You for using DemoManager!\n\nA config file has been "
	"created in a folder next to the script.\n\nThis script is able to delete "
	"files if you tell it to.\nI in no way guarantee that this script is safe "
	"or 100% reliable and will not take any responsibility for lost data, damaged "
	"drives and/or destroyed hopes and dreams.\nThis program is licensed via the "
	"MIT Licence, by clicking the accept button below you confirm that you have "
	"read and accepted the license.")
EVENT_FILE = "_events.txt"
DATE_FORMAT = "%d.%m.%Y  %H:%M:%S"
EVENTFILE_FILENAMEFORMAT = "(?<= \\(\").+(?=\" at)" #regex
EVENTFILE_BOOKMARK = "Bookmark"
EVENTFILE_KILLSTREAK = "Killstreak"
EVENTFILE_TICKLOGSEP = "(?<= at )\\d+(?=\\))" # regex
EVENTFILE_ARGIDENT = r"(?<= )[a-zA-Z0-9]+(?= \()" # regex
STATUSBARDEFAULT = "Ready."
TF2_EXE_PATH = "steamapps/common/team fortress 2/hl2.exe"
TF2_HEAD_PATH = "steamapps/common/team fortress 2/tf/"
TF2_LAUNCHARGS = ["-steam", "-game", "tf"]
STEAM_CFG_PATH0 = "userdata/"
STEAM_CFG_PATH1 = "config/localconfig.vdf"
LAUNCHOPTIONSKEYS = ("[\"UserLocalConfigStore\"][\"Software\"][\"Valve\"][\"Steam\"][\"Apps\"][\"440\"][\"LaunchOptions\"]",
					"[\"UserLocalConfigStore\"][\"Software\"][\"valve\"][\"Steam\"][\"Apps\"][\"440\"][\"LaunchOptions\"]",
					"[\"UserLocalConfigStore\"][\"Software\"][\"Valve\"][\"Steam\"][\"apps\"][\"440\"][\"LaunchOptions\"]",
					"[\"UserLocalConfigStore\"][\"Software\"][\"valve\"][\"Steam\"][\"apps\"][\"440\"][\"LaunchOptions\"]",)
ERRLOGFILE = "err.log"
GUI_UPDATE_WAIT = 20 # Setting this to lower values might lock the UI, use with care.
THEME_SUBDIR = "ui_themes"
THEME_PACKAGES = {	"Dark":("dark.tcl", "demomgr_dark", "dark"),}
					# 0: tcl file, 1: theme name, 2: resource dir name
FALLBACK_HEADER = {"dem_prot":3, "net_prot":24, "hostname":"",
	"clientid":"", "map_name":"", "game_dir":"", "playtime":0,
	"tick_num":0, "framenum":0, "tickrate":0}

FILTERDICT = {
	"name":				("\"{}\" in x[\"name\"]", str),
	"bookmark_contains":("\"{}\" in \"\".join((i[0] for i in x[\"bookmarks\"]))", str),
	"map":				("\"{}\" in x[\"header\"][\"map_name\"]", str),
	"hostname":			("\"{}\" in x[\"header\"][\"hostname\"]", str),
	"clientid":			("\"{}\" in x[\"header\"][\"clientid\"]", str),
	"killstreaks":		("len(x[\"killstreaks\"]) {sign} {}", int),
	"bookmarks":		("len(x[\"bookmarks\"]) {sign} {}", int),
	"beststreak":		("max((i[0] for i in x[\"killstreaks\"]), default=-1) {sign} {}", int),
	"moddate":			("x[\"filedata\"][\"modtime\"] {sign} {}", int),
	"filesize":			("x[\"filedata\"][\"filesize\"] {sign} {}", int),
}
# [0] will be passed through eval(), prefixed with "lambda x: "; {} replaced by [1] called with ESCAPED user input as parameter
# -> eval("lambda x:\"" + str("koth_") + "\" in x[\"name\"]") -> lambda x: "koth_" in x["name"]
