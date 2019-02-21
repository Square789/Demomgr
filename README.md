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
- [ ] Broader filtering options (Such as ranges)
- [ ] Better Cleanup item selector
- [ ] Remove hassle with UNIX Timestamps

### Start Instructions:
Optionally install the [vdf module](https://pypi.org/project/vdf/).  
Make sure you extract all three files into a directory where the script will have write access, and then launch `demomgr.py`.  
After accepting the license, you will be presented with an empty UI. In order to view your demos, click "Add demo path" and select the directory containing your demos.  
You can switch between directories using the Selection box at the top of the window.  

#### Filter instructions:
The filter criteria must be entered as follows:  
`<keyname>:<value>`, seperated by commas.  

Example: `map_name:cp_badlands, killstreak_min:2`  

You can currently filter the directory you are in by the following:
 * map_name : _Name of the map the demo is playing on. (Substring)_
 * name : _Filename of the demo. (Substring)_
 * killstreak_min : (Inclusive) _Minimum amount of present killstreaks._
 * bookmark_min : (Inclusive) _Minimum amount of bookmarks recorded._
 * bookmark_contains : _Bookmarks containing this String (Substring)_
 * hostname : _Name of the server the demo took place on. (Usually in IPv4 format)_
 * clientid : _Steam community name of the player. (Substring)_
 * moddate : _Modified (created) after this date. (UNIX Timestamp)_
