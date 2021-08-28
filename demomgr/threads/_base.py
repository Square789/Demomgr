import threading

class _StoppableBaseThread(threading.Thread):
	"""
	This thread has a killflag (stoprequest <threading.Event>),
	and expects a queue_in and queue_out attribute in the constructor.
	The stopflag can be set by calling the thread's `join()` method,
	however regularly has to be checked for in the run method.
	Override this thread's `run()` method, start by calling `start()`!
	"""
	def __init__(self, queue_inp, queue_out):
		super().__init__()
		self.queue_inp = queue_inp
		self.queue_out = queue_out
		self.stoprequest = threading.Event()

	def join(self, timeout = None, nostop = False):
		"""
		Set the thread's stop request and call the thread's join method.
		If nostop is set to a truthy value, the thread's killflag
		won't be set.
		"""
		if not nostop:
			self.stoprequest.set()
		super().join(timeout)

	def queue_out_put(self, sig, *args):
		"""
		Writes a signal and its potential arguments to the output
		queue as a tuple.
		"""
		if self.queue_out is not None:
			self.queue_out.put((sig, ) + args)
