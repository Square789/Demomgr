"""
Offers the run() function which starts demomgr.
"""
import demomgr.main_app

def run():
	m = demomgr.main_app.MainApp()
	m.root.mainloop()
