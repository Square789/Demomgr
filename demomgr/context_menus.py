"""
Offers some callbacks that can be bound to tkinter widgets, where
they will open context menus on the widgets.
"""

import tkinter as tk

def _generate_readonly_cmd(w):
	cmd = (
		("command", {"label": "Copy", "command": lambda: w.event_generate("<<Copy>>")}, 2),
		("command", {"label": "Select all", "command": lambda: w.event_generate("<<SelectAll>>")})
	)
	return cmd

def _generate_normal_cmd(w):
	cmd = (
		("command", {"label": "Cut", "command": lambda: w.event_generate("<<Cut>>")}),
		("command", {"label": "Clear", "command": lambda: w.event_generate("<<Clear>>")}),
		("command", {"label": "Paste", "command": lambda: w.event_generate("<<Paste>>")}),
	)
	return cmd

class PopupMenu(tk.Menu):
	"""Base popup menu."""
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

def multiframelist_cb(event, mfl, demo_ops):
	"""
	Very specific and hardcoded callback that opens a popup menu on a
	MultiframeList.

	Arguments:
	event: The tkinter event that triggered the callback.
	mfl: The MultiframeList that got clicked.
	demo_ops: A tuple of tuples where for every contained tuple:
		[0] is the label for the menu entry and [2] is the command
		associated with that entry.
	"""
	w = event.widget
	x, y = mfl.getlastclick()
	add_elems = [("command", {"label": f"{s0}...", "command": cmd}) for s0, _, cmd in demo_ops]
	men = PopupMenu(mfl, add_elems)
	men.post(x, y)

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
