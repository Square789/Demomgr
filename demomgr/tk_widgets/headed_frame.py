
from tkinter import ttk

class HeadedFrame(ttk.Frame):
	"""
	Visually similar to a labelframe, only creates a 1px border frame with the
	color specified in style "Contained.TFrame" and a label with all
	options in hlabel routed to it.
	!!! Stash any widgets that should appear in this HeadedFrame inside of the
	HeadedFrame's internal_frame attribute. !!!
	"""
	def __init__(self, master, hlabel_conf = None, iframe_conf = None, **kwargs):
		"""
		master: Parent tk widget
		hlabel_conf: <Dict> : Options to give to the heading label.
			By default, style will be set to `"Contained.TLabel"`.
		iframe_conf: <Dict> : Options to give to the inner frame.

		Any other kwargs will be passed to the underlying Frame.
		"""
		super().__init__(master, style = "Contained.TFrame", **kwargs)
		hlabel_conf = {} if hlabel_conf is None else hlabel_conf
		iframe_conf = {} if iframe_conf is None else iframe_conf

		if not "style" in hlabel_conf:
			hlabel_conf["style"] = "Contained.TLabel"

		self._heading_label = ttk.Label(self, **hlabel_conf)
		self.internal_frame = ttk.Frame(self, **iframe_conf)

		self.grid_columnconfigure(0, weight = 1)
		self.grid_rowconfigure(1, weight = 1)

		self._heading_label.grid(row = 0, sticky = "w", padx = (2, 0))
		self.internal_frame.grid(row = 1, sticky = "nesw", padx = 1, pady = (0, 1))
