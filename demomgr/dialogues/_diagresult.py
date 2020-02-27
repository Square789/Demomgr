"""
Contains the DiagResult class, which should exist as an attribute
of dialogues and show their state and return information.
"""

class DIAGSIG:
	"""
	This class is a constant collection of a few numeral flags.

	OPEN: 0x2, dialog is still running, result undefined.
	SUCCESS: 0x0, dialog closed and succeeded.
	FAILURE: 0x1, dialog closed and failed.
	"""
	OPEN = 0x2
	SUCCESS = 0x0
	FAILURE = 0x1

class DiagResult():
	"""
	Should be attribute of a dialog to inform of that dialog's state.
	How the value should be expected is to be described in each dialog's
	class docstring.
	"""
	def __init__(self, state = None, remember = None):
		"""
		The DiagResult will have a `data` attribute that is set to `None`
			at initialization. A dialog may store custom data here. It is
			recommended to be a dict, as all `__getitem__` operations will
			be routed to it.

		state: Should be one of the states of `DIAGSIG`, will be set to
			`DIAGSIG.OPEN` if not given.
		"""
		self.state = state
		if state is None:
			self.state = DIAGSIG.OPEN
		self.data = None

	def __getitem__(self, name):
		if self.data is None:
			raise TypeError("No data stored in dialog result.")
		return self.data[name]
