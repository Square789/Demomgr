# Demomgr
Demomgr is a python script designed to keep track of, cleanup and play demo files from the Source video game Team Fortress 2, released by Valve Corporation in 2007.

> ![Main program window](https://github.com/Square789/Demomgr/blob/master/img0.PNG)  
> _A folder, filtered to only include demos where a killstreak of at least 8 has occurred and the map type is either king of the hill or payload, sorted by creation date._
### Current features:
* List Demos, their filesize, creation date and the amount of Killstreaks/Bookmarks
  * View demo header information
* Read Killstreak/Bookmark information from both .json files and the \_events.txt file
* Manage bookmark information of individual demos
* Sort and filter demos by multiple criteria
* Play or delete demos from within the program
  * Optionally with HLAE
* Cleanup entire folders by multiple criteria
  * Removes unneccessary entries from \_events.txt and also deletes useless .json files

The script has so far only been tested on python 3.8.1.

### Progress and (hopefully) upcoming features:
- [x] Basic filtering mechanism
- [x] Broader filtering options
- [ ] Remove hassle with UNIX Timestamps
- [x] Add stats after deletion
- [x] Thread demo accessing and processing for responsive UI
- [x] Insert custom bookmarks into demos
- [x] Make UI look less 1995-ish
- [x] Add right click menus
- [ ] Add filesystem-related information on current demos and directory
- [x] Add HLAE support

### Start Instructions:
Run `pip install demomgr`. This should create an entry point script in your python
installations's `Scripts` directory. You should now be able to run `demomgr.exe`.

If that does not work out for you, create a procedure that invokes the python commands
`from demomgr.main_app import MainApp; MainApp()`

After accepting the license, you will be presented with an empty UI. In order to view your demos, click "Add demo path" and select the directory containing your demos.  
You can switch between directories using the Selection box at the top of the window.  

#### Filter instructions:
The filter criteria must be entered as follows:  
`<keyname>:<parameter>`, seperated by commas.  
**You can negate all key-parameter pairs by prefixing the key with **`!`**.**  
**Do not use the same filtering key (Even if negated) in a filter request, as one will replace the other.**  
**You can enter multiple parameters by seperating them with **`,`**.**

Example: `!map:(mvm_,plr_, tr_, ), killstreaks:2.. , beststreak:5.. `  
Returns all demos where: The user has gotten at least two killstreaks, at least one of those streaks were 5 or more and the game does not take place on maps containing the substrings `mvm_`,`plr_` or `tr_`.  

You can currently filter the directory you are in by the following:
 * map : _Name of the map the demo is playing on. (String)_
 * name : _Filename of the demo. (String)_
 * killstreaks : (Inclusive) _Minimum amount of present killstreaks._ (Range/Integer)
 * bookmarks : (Inclusive) _Minimum amount of bookmarks recorded._ (Range/Integer)
 * beststreak : (Inclusive) _Minimum value of the best streak recorded in demo_ (Range/Integer)
   * May produce erratic results at values out of normal ranges
 * bookmark_contains : _Bookmarks containing this String (String)_
 * hostname : _Name of the server the demo took place on. (Usually in IPv4 format)_
 * clientid : _Steam community name of the player. (String)_
 * moddate : _Modified (created) after this date. (UNIX Timestamp)_ (Range/Integer)
 * filesize : _Filesize in bytes_ (Integer)

Accepted parameters are:
 * Quoteless string: `foo`
   * Quoteless strings may consist out of A-Z, a-z, \_, -
 * Quoteless string tuple: `(foo, bar, baz)`
 * String: `"foo"`, `'b\u0061r'`
 * String tuple: `("foo", 'b\u0061r', "b\u0061z", )`
 * Range: `1..2`, `10..`, `..50`  
 