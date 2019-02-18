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

The script works (tested on Python 3.6.6) with nearly the standard library, installing the [vdf module](https://pypi.org/project/vdf/) however will allow it to work with standard launch information for TF2.

### Progress and (hopefully) upcoming features:
- [x] Basic filtering mechanism
- [ ] Help/About dialog window
- [ ] Broader filtering options
- [ ] Better Cleanup item selector
