"""
Alternative module call, eg. "py -m demomgr"
This stuff is tricky.
"""
from demomgr.main_app import MainApp

if __name__ == "__main__":
	m = MainApp()
	m.root.mainloop()
