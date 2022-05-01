"""
Offers some callbacks that can be bound to tkinter widgets, where
they will open context menus on the widgets.
"""

import tkinter as tk


def _generate_readonly_cmd(w):
	cmd = (
		("command", {"label": "Copy", "command": lambda: w.event_generate("<<Copy>>")}, 2),
		("command", {"label": "Select all", "command": lambda: w.event_generate("<<SelectAll>>")}),
	)
	return cmd

def _generate_normal_cmd(w):
	cmd = (
		("command", {"label": "Cut", "command": lambda: w.event_generate("<<Cut>>")}),
		("command", {"label": "Clear", "command": lambda: w.event_generate("<<Clear>>")}),
		("command", {"label": "Paste", "command": lambda: w.event_generate("<<Paste>>")}),
	)
	return cmd


_existing_menu = None

def _remove_existing_menu():
	global _existing_menu

	if _existing_menu is not None:
		# It's possible for the existing menu to be destroyed when its
		# root widgets are, e.g. when it was created in a dialog and the dialog
		# is closed. Just eat the error up then, seems fine.
		try:
			_existing_menu.unpost()
			_existing_menu.destroy()
		except tk.TclError as e:
			pass
		_existing_menu = None


class PopupMenu(tk.Menu):
	"""Base popup menu. Will immediatedly focus itself when posted."""

	def __init__(self, parent, elems, *args, **kw):
		"""
		Passes all arguments to a tk.Menu, except for:

		parent <tkinter.Widget>: Parent widget of the menu.
		elems: Elements that will be added to the menu, in the form of
			((<str>, <dict>, [<int>]), ...) where the element type is [0] and
			the related options the dict in [1]. If [2] is present, the entry
			will be inserted into the menu at the given position, if not, it
			will be appended.
		"""

		super().__init__(parent, *args, tearoff = 0, **kw)

		for elem in elems:
			if len(elem) > 2:
				self.insert(elem[2], elem[0], **elem[1])
			else:
				self.add(elem[0], **elem[1])

		def f(e, self=self):
			self.unpost()

		self.bind("<Escape>", f)

	def post(self, x, y):
		global _existing_menu

		_remove_existing_menu()
		super().post(x, y)
		_existing_menu = self

def multiframelist_cb(event, mfl, demo_ops):
	"""
	Very specific and hardcoded callback that opens a popup menu on a
	MultiframeList.

	Arguments:
	event: The tkinter event that triggered the callback.
	mfl: The MultiframeList that got clicked.
	demo_ops: The demo operations just like in `MainApp.__init__`.
	"""
	add_elems = [
		("command", {"label": s, "command": cmd})
		for s, cmd, _, fit_for_sel in demo_ops
		if fit_for_sel(len(mfl.selection))
	]
	men = PopupMenu(mfl, add_elems)
	men.post(*mfl.get_last_click())
	men.focus()

def entry_cb(event):
	"""
	Callback that is designed to open a menu over widgets
	such as Entries, Comboboxes and Spinboxes and contains options
	for copying, pasting etc.
	"""
	w = event.widget
	x = w.winfo_rootx() + event.x
	y = w.winfo_rooty() + event.y

	add_elems = []
	w_state = str(w.configure("state")[-1])
	if w_state != "disabled":
		if w_state != "readonly":
			add_elems.extend(_generate_normal_cmd(w))
		add_elems.extend(_generate_readonly_cmd(w))
	if not add_elems:
		return

	men = PopupMenu(w, add_elems)
	men.post(x, y)
	men.focus()

def _remove_existing_menu_swallow_event(e):
	_remove_existing_menu()

def decorate_root_window(win):
	"""
	On linux (in some environments anyways), menus remain and
	apparently have to be unposted manually, because why make things
	easy when you can add more pain?

	This function registers a bunch of event callbacks to top-level
	windows that will fire on clicks in appropiate regions and then
	close possibly opened context menus.
	"""
	win.bind(f"<Button>", _remove_existing_menu_swallow_event)
	win.bind(f"<KeyPress>", _remove_existing_menu_swallow_event)
	win.bind(f"<Unmap>", _remove_existing_menu_swallow_event)
