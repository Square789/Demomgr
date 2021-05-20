"""
Implements threadgroups, effectively a class containing a thread,
a callback and a queue interoperating with eachother at an attempt
to simplify threading and tkinter.
"""

import queue
import threading
import types

import demomgr.constants as CNST
from demomgr.threads._base import _StoppableBaseThread

class THREADGROUPSIG:
	FINISHED = 0
	CONTINUE = 1
	HOLDBACK = 2

class DummyThread(_StoppableBaseThread):
	def __init__(self):
		super().__init__(None, None)

	def run(self):
		pass

class ThreadGroup():
	def __init__(self, thread_cls, tk_widget):
		"""
		Create a threadgroup. Follow this call up with a call to
		decorate_and_patch as soon as possible.

		thread_cls: A subclassed thread from / that behaves like the ones in
			`demomgr.threads`.
		tk_widget: The widget to use for tkinter's after machinery.
		"""
		self.thread_cls = thread_cls
		self.tk_wdg = tk_widget
		self.queue = queue.Queue()
		self.after_handle = self.tk_wdg.after(0, lambda: None)
		self.thread = DummyThread()
		self.caller_self = None
		self.heldback_queue_elem = None
		self.finalization_method = None
		self.run_always_method = None
		self._decorated_cb = None
		self._orig_cb_method = None

	def register_finalize_method(self, method):
		"""
		Registers a finalization method with the threadgroup, which is called
		once when the thread has ended and the queue has been emptied by the
		callback method. It must fulfill the following criteria:
			It should take two input arguments, self and queue_elem.
				queue_elem will be the last queue element that caused the
				callback method to return `THREADGROUPSIG.HOLDBACK`,
				if this signal was not received, it will instead be None.
			The method should perform a heavy task that is best suited for
			the very end of thread activity, or may perform cleanup
			(Though this can easily be handled in the callback method as well.)

		method: The finalization method.

		Note that the finalization method must be registered before a
		call to decorate_and_patch.
		"""
		self.finalization_method = method

	def register_run_always_method(self, method):
		"""
		Registers a method with the threadgroup which will be called
		ever time the after callback runs. Useful for progress
		indicators.

		method: The finalization method.

		Note that this  method must be registered before a call to
		decorate_and_patch.
		"""
		self.run_always_method = method

	def decorate_and_patch(self, targetobj, cb_method):
		"""
		Decorates and patches a class method so it works properly with the thread
		and is able to process elements from its output queue.
		The callback method must be structured as follows:
			It should take two input arguments, self and queue_elem.
			It then performs actions on its class as normal depending on
			the queue_elem.
			The method should return True to indicate that thread activity
			has finished.
		It will be changed to only take one parameter (self) and re-added to
			targetobj under the same name, hiding the source method.

		targetobj: Object the queue processing method is an attribute of.
		cb_method: The queue processing callback method.

		example: `tg.decorate_and_patch(self, self.thread_callback)`
		"""
		if self.finalization_method is None:
			def decorated0(self_, reschedule):
				finished = False
				while True:
					try:
						queue_obj = self.queue.get_nowait()
					except queue.Empty:
						break
					# Should be a bound method, so self (targetobj) is passed in automatically
					res = cb_method(queue_obj)
					if res == THREADGROUPSIG.FINISHED:
						finished = True
				if not finished and reschedule:
					# decorated is made a bound class method below, which this will access.
					self.after_handle = self.tk_wdg.after(CNST.GUI_UPDATE_WAIT, decorated)
		else:
			def decorated0(self_, reschedule):
				finished = False
				while True:
					try:
						queue_obj = self.queue.get_nowait()
					except queue.Empty:
						break
					res = cb_method(queue_obj)
					if res == THREADGROUPSIG.FINISHED:
						finished = True
					elif res == THREADGROUPSIG.HOLDBACK:
						self.heldback_queue_elem = queue_obj
				if not finished and reschedule:
					self.after_handle = self.tk_wdg.after(CNST.GUI_UPDATE_WAIT, decorated)
				else:
					self.finalization_method(self.heldback_queue_elem)
					self.heldback_queue_elem = None

		if self.run_always_method is not None:
			def decorated1(self_, reschedule = True):
				self.run_always_method()
				decorated0(self_, reschedule)
		else:
			def decorated1(self_, reschedule = True):
				decorated0(self_, reschedule)

		self._orig_cb_method = cb_method
		self.caller_self = targetobj
		decorated = types.MethodType(decorated1, targetobj)
		self._decorated_cb = decorated
		setattr(targetobj, cb_method.__name__, decorated) # Patch method

	def start_thread(self, *args, **kwargs):
		"""
		Start the thread with the supplied args and kwargs, except the
		ThreadGroup's queue will be passed before them as the first
		argument.
		"""
		if self._decorated_cb is None:
			raise ValueError(
				"No callback defined in threadgroup. Call decorate_and_patch on a "
				"suitable callback function."
			)
		self.heldback_queue_elem = None
		self.thread = self.thread_cls(self.queue, *args, **kwargs)
		self.thread.start()
		self.after_handle = self.tk_wdg.after(0, self._decorated_cb)

	def join_thread(self, finalize = True, timeout = None, nostop = False):
		"""
		Stops the after handle for the thread, then joins the
		thread, setting its stopflag and waiting until it terminates.
		Afterwards the after callback method is called again.
		This may be used to handle a thread's final termination
		signals and should result in the queue getting emptied.

		If the thread is not alive, no call to join is made as it may
		raise an error.

		finalize: If set to False, no additional call to the callback is made.

		timeout and nostop [default None, False] will be passed through to
		the thread's join method.
		"""
		self.cancel_after()
		if self.thread.is_alive():
			self.thread.join(timeout, nostop)
		if finalize:
			self._decorated_cb(reschedule = False)
		self.queue.queue.clear() # just to be reeeeeally safe

	def cancel_after(self):
		"""
		Cancels after handle immediatedly.
		"""
		self.tk_wdg.after_cancel(self.after_handle)

	def call_original_callback(self, queue_elem):
		"""
		Calls the original callback method with the supplied queue element.
		"""
		self._orig_cb_method(queue_elem)
