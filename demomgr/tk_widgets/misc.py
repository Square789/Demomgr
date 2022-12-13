
import re
from tkinter import ttk


RE_NUMBER = re.compile(r"^\d+$")


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
		e.widget.update_idletasks()
		self._block_reconfigure = False


def _int_validator(action, changed_section, if_allowed):
	"""
	Test whether only (positive) integers are being keyed into an entry.
	Call signature: %d %S %P
	"""
	if len(if_allowed) > 10:
		return False

	# don't validate deletion
	return (action == 0) or bool(RE_NUMBER.match(changed_section))


_command_registry = {}

def purge_commands(tk):
	"""
	Properly deletes all commands that have been registered to
	demomgr specific widgets in the past.
	"""
	for cmd in _command_registry.values():
		tk.deletecommand(cmd)

# The needcleanup parameter will cause tkinter to not store the commands in an internal
# list on the parent that is used to destroy it as soon as the parent is.
# We technically leak these, but track them ourselves so it's all good, man
def _get_command(input_limit, tk_haver):
	if input_limit not in _command_registry:
		if input_limit == 0:
			_command_registry[input_limit] = tk_haver.register(_int_validator, needcleanup=False)
		else:
			def _name_validator(if_allowed):
				"""
				Limits length of string to X chars
				Call signature: %P
				"""
				return len(if_allowed) <= input_limit
			_command_registry[input_limit] = tk_haver.register(_name_validator, needcleanup=False)

	sig = ("%d", "%S", "%P") if input_limit == 0 else ("%P",)
	return (_command_registry[input_limit],) + sig


class DmgrEntry(ttk.Entry):
	def __init__(self, parent, input_limit = 40, **kwargs):
		"""
		Creates an entry that will limit its input length to the
		amount of characters. If `input_limit` is <= 0, instead
		the entry is turned into an int-validator entry which only
		allows empty strings or valid, positive integer to be typed
		into itself.
		"""
		input_limit = max(input_limit, 0)
		kwargs["validate"] = "key"
		kwargs["validatecommand"] = _get_command(input_limit, parent)
		super().__init__(parent, **kwargs)


class DmgrSpinbox(ttk.Spinbox):
	def __init__(self, parent, input_limit = 40, **kwargs):
		"""
		Similar to the DmgrEntry, just a spinbox instead.
		"""
		input_limit = max(input_limit, 0)
		kwargs["validate"] = "key"
		kwargs["validatecommand"] = _get_command(input_limit, parent)
		super().__init__(parent, **kwargs)
