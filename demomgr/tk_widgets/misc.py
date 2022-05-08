
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


class DynamicLabel(ttk.Label):
	def __init__(self, min_wraplength, ini_wraplength, parent, **kwargs):
		kwargs["wraplength"] = ini_wraplength

		super().__init__(parent, **kwargs)

		self._min_wl = min_wraplength
		self._block_reconfigure = False

		parent.bind("<Configure>", self._reconfigure)

	def _reconfigure(self, e):
		# I think this block does nothing, but i'll just leave it in anyways, just in case.
		if self._block_reconfigure:
			return
		self._block_reconfigure = True
		# Hardcoded 5, who cares, good enough for the places it's used in.
		self.configure(wraplength = max(self._min_wl, e.widget.winfo_width() - 5))
		self._block_reconfigure = False
