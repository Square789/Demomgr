import tkinter as tk
import tkinter.ttk as ttk

from tkinter.simpledialog import Dialog

from demomgr.dialogues._diagresult import DIAGSIG, DiagResult
from demomgr.helpers import CfgReducing

class BaseDialog(tk.Toplevel, CfgReducing):
	"""
	A base dialog that serves as ground for all other dialogs in the
	program. Override self.body(), call self.destroy() for closing the dialog.
	The `result` attribute will contain a DiagState instance, whose `state` is
	set to FAILURE if it is still OPEN on exit.
	The `remember` attribute will be set to `[]` if it is still `None` upon
	closing.
	The `result`s `data` will be None, as this is the base dialog, but in
	inheriting dialogs the returned data should be documented in the class
	docstring. 

	Code "borrowed" from tkinter.simpledialog.Dialog, overrides the 5px
	border that is unstylable.
	"""

	REMEMBER_DEFAULT = []

	def __init__(self, parent, title = None):
		"""
		Initializes a new dialog.

		parent: Parent tkinter window, should be a Tk or Toplevel instance.
		title: Window title.
		"""
		self.result = DiagResult()
		self.parent = parent
		super().__init__(parent)
		if title is not None:
			self.title(title)

	def show(self):
		"""Show the dialog."""
		self.rootframe = ttk.Frame(self)
		self._mainframe = ttk.Frame(self.rootframe)
		self.body(self._mainframe)
		self._mainframe.pack(expand = 1, fill = tk.BOTH, padx = 5, pady = 5)
		self.rootframe.pack(expand = 1, fill = tk.BOTH)
		self.grab_set()
		self.focus_set()

		self.withdraw()
		if self.parent.winfo_viewable():
			self.transient(self.parent)

		if self.parent is not None:
			self.geometry("+{}+{}".format(self.parent.winfo_rootx() + 50,
				self.parent.winfo_rooty() + 50))

		self.deiconify()
		self.wait_visibility()
		self.wait_window(self)

	def validate_and_update_remember(self, update_with):
		"""
		Validates the types of update_with against the types in the dialog's
		REMEMBER_DEFAULT list, then applies a forward-compatible update
		scheme of update_with into a copy of REMEMBER_DEFAULT, returning it.
		If the validation fails, an unchanged copy of REMEMBER_DEFAULT is returned.

		i. e.: `DEF: [], UPD: [1, 2]` -> `[1, 2]`;
		`DEF: [False, 5], UPD: [True]` -> `[True, 5]`
		`DEF: ["abc", 10], UPD: ["def", "ghi"]` -> `["abc", 10]`
		"""
		if len(self.REMEMBER_DEFAULT) < len(update_with):
			return self.REMEMBER_DEFAULT.copy()
		for defval, newval in zip(self.REMEMBER_DEFAULT, update_with):
			if type(defval) is not type(newval):
				return self.REMEMBER_DEFAULT.copy()

		if len(self.REMEMBER_DEFAULT) == len(update_with):
			return update_with

		# If this gets too complex for whatever reason, use deepcopy
		out = self.REMEMBER_DEFAULT.copy()
		for i, j in enumerate(update_with):
			out[i] = j
		return out

	def body(self, master):
		"""Override this"""
		pass

	def destroy(self):
		"""
		Destroy the dialog and if not taken care of set the state to FAILURE.

		This may be overridden, be sure to call super().destroy() then.
		"""
		if self.result.state == DIAGSIG.OPEN:
			self.result.state = DIAGSIG.FAILURE
		if self.result.remember is None:
			self.result.remember = []
		super().destroy()
