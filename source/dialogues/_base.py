import tkinter as tk
import tkinter.ttk as ttk

from tkinter.simpledialog import Dialog

class BaseDialog(tk.Toplevel):
	'''A base dialog that serves as ground for all other dialogs in the
	program. Override self.body(), call self.cancel() or
	self.destroy() for closing the dialog.

	Code "borrowed" from tkinter.simpledialog.Dialog, overrides the 5px
	border that is unstylable.
	'''
	def __init__(self, parent, title = None):
		super().__init__(parent, bg = "#000000")
		self.grab_set()
		self.focus_set()

		self.withdraw()
		if parent.winfo_viewable():
			self.transient(parent)

		if title != None:
			self.title(title)

		self.parent = parent
		rootframe = ttk.Frame(self, padding = (5, 5, 5, 5))
		rootframe.pack(expand = 1, fill = tk.BOTH)
		mainframe = ttk.Frame(rootframe)
		self.body(mainframe)
		mainframe.pack(expand = 1, fill = tk.BOTH)

		self.protocol("WM_DELETE_WINDOW", self.cancel)

		if self.parent is not None:
			self.geometry("+{}+{}".format(parent.winfo_rootx() + 50,
				parent.winfo_rooty() + 50))
		self.deiconify()

		self.wait_visibility()
		self.wait_window(self)

	def body(self, master):
		'''Override this'''
		pass

	def cancel(self):
		self.destroy()

	def destroy(self):
		super().destroy()
