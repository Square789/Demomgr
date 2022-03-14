
import tkinter as tk
from tkinter import ttk

class PasswordButton(ttk.Button):
	def __init__(self, parent, **kwargs):
		super().__init__(parent, **kwargs)

		self._is_showing = False

	def bind_to_entry(self, entry, symbol = "\u25A0"):
		"""
		Binds commands to a button making it toggle the `show` configure
		option for the given entry to `symbol` while untouched and `""`
		while it is being pressed.
		"""
		def on_press(_):
			if not self._is_showing:
				self._is_showing = True
				entry.configure(show = "")

		def on_release(_):
			self._is_showing = False
			entry.configure(show = symbol)

		self.bind("<Button-1>", on_press)
		self.bind("<KeyPress-space>", on_press)
		self.bind("<ButtonRelease-1>", on_release)
		self.bind("<KeyRelease-space>", on_release)
