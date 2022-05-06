import tkinter as tk
import tkinter.ttk as ttk

from demomgr import context_menus
from demomgr.dialogues._diagresult import DIAGSIG, DiagResult

class BaseDialog(tk.Toplevel):
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

	! WARNING ! Tkinter or maybe the way I handle dialogs is bugged in a way
	that allows two dialogs to pop up when spamming the activation key (Space)
	on a button very quickly while it's focused. Thus, `show` and heavy computational
	work should be done in `body` since it's guaranteed to be called only once;
	duplicate dialogs will not show up when their `show` method is called and have
	their `state` set to `GLITCHED`.

	Code "borrowed" from tkinter.simpledialog.Dialog, overrides the 5px
	border that is unstylable.
	"""

	_is_open = False

	def __init__(self, parent, title = None):
		"""
		Initializes a new dialog.

		parent: Parent tkinter window, should be a Tk or Toplevel instance.
		title: Window title.
		"""
		self.result = DiagResult()
		self.parent = parent

		super().__init__(parent)

		self._is_glitched = type(self)._is_open
		type(self)._is_open = True

		if title is not None:
			self.title(title)

		context_menus.decorate_root_window(self)

	def show(self):
		"""
		Create the dialog's interface and show it if the dialog is not a duplicate.
		If it is, the custom subclass `body` method won't be called and the dialog's
		exit state will be set to `DIAGSIG.GLITCHED`.
		"""
		if self._is_glitched:
			# Code duplication from `self.destroy()`?
			self.result.state = DIAGSIG.GLITCHED
			self.result.remember = []
			super().destroy()
			return

		# tcl/tk moment
		self.transient(self.parent)

		self._rootframe = ttk.Frame(self)
		self._mainframe = ttk.Frame(self._rootframe)
		self.body(self._mainframe)
		self._mainframe.pack(expand = 1, fill = tk.BOTH, padx = 5, pady = 5)
		self._rootframe.pack(expand = 1, fill = tk.BOTH)

		x, y = (
			(0, 0) if self.parent is None
			else (self.parent.winfo_rootx(), self.parent.winfo_rooty())
		)
		self.geometry(f"+{x + 50}+{y + 50}")

		self.deiconify()
		self.grab_set()
		# This causes the execution to stall until the window is closed.
		# Very epic, cause it means that calling functions can simply continue
		# as if nothing happened and read the dialog's results.
		self.wait_window(self)

	def body(self, master):
		"""
		Override this. But never ever call `update`, `wait_visibility`
		or anything that might prompt tkinter to start processing user
		events in here.
		"""
		pass

	def destroy(self):
		"""
		Destroy the dialog and if not taken care of set the state to FAILURE.
		Sets the dialog classes `is_open` attribute to `False`.

		This may be overridden, be sure to call super().destroy() then.
		"""
		if self.result.state == DIAGSIG.OPEN:
			self.result.state = DIAGSIG.FAILURE
		if self.result.remember is None:
			self.result.remember = []
		type(self)._is_open = False
		super().destroy()
