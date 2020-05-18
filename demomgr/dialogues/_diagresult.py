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
	The types and format of the values is to be described in each dialog's
	class docstring.
	"""
	def __init__(self, state = None):
		"""
		The DiagResult will have a `data` attribute that is set to `None`
			at initialization. A dialog may store custom data here.
		An attribute `remember` will be created with `None` on init. 
			If a dialog supports remembering of individual widget states
			that are passed to it in the constructor, this attribute
			should be set to a list configured in the same form as
			an expected input list upon closing.

		state: Should be one of the states of `DIAGSIG`, will be set to
			`DIAGSIG.OPEN` if not given.
		"""
		self.state = state
		if state is None:
			self.state = DIAGSIG.OPEN
		self.data = None
		self.remember = None
