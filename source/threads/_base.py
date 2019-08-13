import threading

class _StoppableBaseThread(threading.Thread):
	'''This thread has a killflag (stoprequest <threading.Event>),
	and expects a queue_in and queue_out attribute in the constructor.
	It also takes args and kwargs. The stopflag can be set by calling the
	thread's join() method, however regularly has to be checked for in
	the run method.
	The stopflag can be ignored by passing a third arg that is evaluated
	to True to the join() method.
	Override this thread's run() method, start by calling start() !
	'''
	def __init__(self, queue_inp, queue_out, *args, **kwargs):
		super().__init__()
		self.queue_inp = queue_inp
		self.queue_out = queue_out
		self.args = args
		self.kwargs = kwargs
		self.stoprequest = threading.Event()

	def join(self, timeout=None, dontstop=False):
		'''Set the thread's stop request and call the thread's join method.
		If the dontstop arg is set to a truthy value, the thread's killflag
		won't be set.
		'''
		if not dontstop:
			self.stoprequest.set()
		super().join(timeout)
