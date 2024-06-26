# Demomgr
Demomgr is a python program designed to keep track of, cleanup and play demo files from the Source video game Team Fortress 2, released by Valve Corporation in 2007.

> ![Main program window](https://github.com/Square789/Demomgr/blob/master/images/main_view.png)  
> _Main program view, directory filtered to only demos taking place on payload maps, sorted by file size. One demo selected._

## Current features:
* List Demos, their filesize, creation date and the amount of Killstreaks/Bookmarks
  * Sort them by these criteria
* Read Killstreak/Bookmark information from both .json files and the \_events.txt file
* View and edit bookmark information of individual demos
* View header information of individual demos
* Sort demos and filter/select them by multiple criteria
* Delete selections of demos
* Copy/Move selections of demos and their info to other directories
* Launch TF2 with a `playdemo` and/or `demo_gototick` command attached
  * Optionally with HLAE
* Play demos into an already running instance of TF2 using [RCON](https://developer.valvesoftware.com/wiki/Source_RCON_Protocol)

## Installation Instructions (Pure python):
If you don't have python, get it from [the official website](https://www.python.org).

Demomgr is in python's package index (PyPI), you can install it using `pip install demomgr`.
This should create an entry point script in your python installations's `Scripts` directory.
If that is on your system's path, you should now be able to run `demomgr` pretty much anywhere.

If that does not work out for you, try `py -m demomgr`, or in a very extravagant case create a
python script that runs  
`from demomgr.main_app import MainApp; MainApp()`.

## Installation instructions (exe):
For Windows, there is an experimental [Nuitka](https://nuitka.net/) build of Demomgr available in the [Releases](https://github.com/Square789/Demomgr/releases/) section.  
Extract it to a good place for programs to be and run the contained `demomgr.exe`.

## Getting started:
After accepting the disclaimer (Look, I have no idea how to set up tests for deletion/file management logic
intertwined with a UI, and even though I spend hours testing proper functionality there is a risk of something sneaking by),
you will be presented an empty UI. In order to view your demos, click "Add demo path" and select the directory containing your demos.  
You can switch between directories using the selection box at the top of the window.  

## Filter instructions:
The filter criteria are entered in pairs: `[keyname]:[parameter]`, seperated by commas.  
**You can negate all key-parameter pairs by prefixing the key with **`!`**.**  
**Do not re-use the same filtering key (Even if negated) in a filter request, one will replace the other.**  

You can currently filter the directory you are in by the following keys:
 * map : _Substring of the map name a demo is playing on._ (String)
 * name : _Substring of a demo's filename._ (String)
 * killstreaks : _Amount of a demo's killstreaks._ (Range)
 * bookmarks : _Amount of bookmarks recorded._ (Range)
 * beststreak : _Value of the best streak recorded in a demo._ (Range)
   * May produce erratic results at values out of normal ranges
 * bookmark_contains : _Substring of any of a demo's bookmarks._ (String)
 * hostname : _Substring of the server name a demo took place on._ (String) (Usually a IPv4)
 * clientid : _Substring of the Steam community name of the player._ (String)
 * moddate : _A demo's last modification time._ (Range) (Direct UNIX Timestamp)
 * filesize : _Filesize in bytes._ (Range)

Keys are either strings or integer ranges. Strings can be:
 * Quoteless string: `foo`
   * Quoteless strings may consist out of `A-Z`, `a-z`, `_`, `-`
 * Quoteless string tuple: `(foo, bar, baz)`
 * String: `"foo"`, `'b\u0061r'`
 * String tuple: `("foo", 'b\u0061r', "b\u0061z", )`

Ranges can be:
 * Number: `1`, `5`  
 * Range: `1..2`, `10..`, `..50`  
   * Ranges are beginning- and end-inclusive

### Examples
`beststreak:15..`  
Will filter for all demos with a recorded killstreak of at least 15.

`!bookmark_contains: recorded, bookmarks:1..`  
Filters out demos that don't contain a bookmark named "recorded", but at least one other bookmark.
Personally, i use this one to find demos with noteworthy moments, adding in the `recorded` bookmark once the content has been extracted from it.

`killstreaks: ..1, bookmarks:0`  
Filters demos that have no bookmarks and at most 1 killstreak. Good candidates for deletion.

`!map:(mvm_,plr_,tr_), killstreaks:2.., beststreak:5..`  
This will select all demos where: The user has gotten at least two killstreaks, at least one of those streaks was 5 or more
and the game does not take place on maps containing the substrings `mvm_`, `plr_` or `tr_`.

## Quirks
Nothing is perfect, and Demomgr isn't nothing. These could be fixed, but i'm not seeing much feedback and my motivation to work
on this rather old codebase also isn't too big.

- Demomgr will replace demos that already exist in a target directory when moving/copying without any notification.
- Demo data can be read from two different sources, the `_events.txt` log file that was probably never meant to have data extracted from it,
  or a `.json` file associated with each demo. These two get notoriously easy out of sync, and there's no way to transfer info between them.
  (Apart from the bookmarks only, which can be achieved by manually writing them without any changes for each demo.)
  This is why it's probably best you keep the information reading mode set to `.json`.
- The UI may report demo information as `?`, but this has multiple causes for the different modes. Basically, there's no distinction or not
  even a clear definition of the distinction between "no info" and "info not found".
  - For mode `None`, it always happens.
  - For mode `_events.txt`, it may be caused by a missing file, no logchunk existing for the given demo, or other errors while processing the file.
  - For mode `.json`, the causes may be decoding errors, file processing errors or the file simply not existing.
- The filtering algorithm considers missing demo information to be 0 killstreaks and 0 bookmarks and might thus select them when not intended.
  (A demo might contain a bunch of cool frags, but its json file is corrupted, which might select it when filtering for demos to delete.)
  - There's no toggle for this behavior, the best option is to manually unselect these demos with ctrl+click before continuing.

Thanks, and have fun.
