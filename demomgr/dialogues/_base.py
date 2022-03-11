import tkinter as tk
import tkinter.ttk as ttk

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
	duplicate dialogs will not show up when their `show` method is clicked and have
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

		self.grab_set()
		self.focus_set()
		self.withdraw()

		self.rootframe = ttk.Frame(self)
		self._mainframe = ttk.Frame(self.rootframe)
		self.body(self._mainframe)
		self._mainframe.pack(expand = 1, fill = tk.BOTH, padx = 5, pady = 5)
		self.rootframe.pack(expand = 1, fill = tk.BOTH)

		if self.parent.winfo_viewable():
			self.transient(self.parent)

		if self.parent is not None:
			self.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

		self.deiconify()
		self.wait_window(self)

	def body(self, master):
		"""Override this"""
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
