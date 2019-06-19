# Demomgr
Demomgr is a light python script designed to keep track of, cleanup and play demo files from the Source video game Team Fortress 2, released by Valve Corporation in 2007.

### Current features:
* List Demos, their filesize, creation date and the amount of Killstreaks/Bookmarks
  * View demo header information
* Read Killstreak/Bookmark information from both .json files and the \_events.txt file
* Sort and filter demos by multiple criteria
* Play or delete demos from within the program
* Cleanup entire folders by multiple criteria
  * Removes unneccessary entries from \_events.txt and also deletes useless .json files

The script works (tested on Python 3.6.6) with the standard library, installing the [vdf module](https://pypi.org/project/vdf/) however will allow it to work with standard launch information for TF2.

### Progress and (hopefully) upcoming features:
- [x] Basic filtering mechanism
- [ ] Help/About dialog window
- [x] Broader filtering options
- [x] Better Cleanup item selector
- [ ] Improve Cleanup dialog filter
- [ ] Remove hassle with UNIX Timestamps
- [x] Add stats after deletion
- [x] Thread demo accessing and processing for responsive UI
- [ ] Insert custom bookmarks into demos
- [ ] Make UI look less 1995-ish

### Start Instructions:
Optionally install the [vdf module](https://pypi.org/project/vdf/).  
Make sure you extract all three files into a directory where the script will have write access, and then launch `demomgr.py`.  
After accepting the license, you will be presented with an empty UI. In order to view your demos, click "Add demo path" and select the directory containing your demos.  
You can switch between directories using the Selection box at the top of the window.  

#### Filter instructions:
The filter criteria must be entered as follows:  
`<keyname>:<value0>*<value1>*<value2>`, seperated by commas.  
**You can negate all filters by prefixing them with **`!`**.**  
**Do not use the same filtering key (Even if negated) in a filter request, as one will replace the other.**  
**You can enter multiple parameters by seperating them with **`*`**. Add a backslash in front of the asterisk in order to escape it.**  
**All integer filters ending in `min` can also be suffixed with `max` to create a filtering range for that attribute.**  

Example: `!map_name:mvm_*plr_*tr_, killstreak_min:2, beststreak_min:5, moddate_max:1551337886`  
Returns all demos where: The user has gotten at least two killstreaks, at least one of those streaks were 5 or more; the demo was made before February 28 2019 on 07:11:26 and the game does not take place on maps containing the substrings `mvm_`,`plr_` or `tr_`.  

You can currently filter the directory you are in by the following:
 * map_name : _Name of the map the demo is playing on. (Substring)_
 * name : _Filename of the demo. (Substring)_
 * killstreak_min : (Inclusive) _Minimum amount of present killstreaks._ (Integer)
 * beststreak_min : (Inclusive) _Minimum value of the best streak recorded in demo_ (Integer)
   * beststreak_max should not be set to a value of more than 99999.
 * bookmark_min : (Inclusive) _Minimum amount of bookmarks recorded._ (Integer)
 * bookmark_contains : _Bookmarks containing this String (Substring)_
 * hostname : _Name of the server the demo took place on. (Usually in IPv4 format)_
 * clientid : _Steam community name of the player. (Substring)_
 * moddate_min : _Modified (created) after this date. (UNIX Timestamp)_ (Integer)
 * filesize_min : _Filesize in bytes_ (Integer)
