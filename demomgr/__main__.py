"""
Alternative module call for "py -m demomgr"
"""
from demomgr.main_app import MainApp

if __name__ == "__main__":
	m = MainApp()
	m.root.mainloop()
