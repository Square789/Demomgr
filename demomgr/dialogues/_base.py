import tkinter as tk
import tkinter.ttk as ttk

from tkinter.simpledialog import Dialog

from demomgr.dialogues._diagresult import DIAGSIG, DiagResult

class BaseDialog(tk.Toplevel):
	"""
	A base dialog that serves as ground for all other dialogs in the
	program. Override self.body(), call self.destroy() for closing the dialog.
	The `result` attribute will contain a DiagState instance, whose `state` is
	set to FAILURE if it is still OPEN on exit.

	Code "borrowed" from tkinter.simpledialog.Dialog, overrides the 5px
	border that is unstylable.
	"""
	def __init__(self, parent, title = None):
		"""
		Initializes a new dialog.

		parent: Parent tkinter window, should be a Tk or Toplevel instance.
		title: Window title.
		"""
		self.result = DiagResult()
		self.parent = parent
		super().__init__(parent)
		if title != None:
			self.title(title)

	def show(self):
		"""Show the dialog."""
		self.grab_set()
		self.focus_set()

		self.withdraw()
		if self.parent.winfo_viewable():
			self.transient(self.parent)

		rootframe = ttk.Frame(self, padding = (5, 5, 5, 5))
		rootframe.pack(expand = 1, fill = tk.BOTH)
		mainframe = ttk.Frame(rootframe)
		self.body(mainframe)
		mainframe.pack(expand = 1, fill = tk.BOTH)

		self.protocol("WM_DELETE_WINDOW", self.destroy)

		if self.parent is not None:
			self.geometry("+{}+{}".format(self.parent.winfo_rootx() + 50,
				self.parent.winfo_rooty() + 50))

		self.deiconify()
		self.wait_visibility()
		self.wait_window(self)

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
		super().destroy()
