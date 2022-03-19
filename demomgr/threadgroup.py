"""
Implements threadgroups, effectively a class containing a thread,
a callback and a queue interoperating with eachother at an attempt
to simplify threading and tkinter.
"""

from enum import IntEnum
import queue

import demomgr.constants as CNST
from demomgr.threads._base import _StoppableBaseThread

class THREADGROUPSIG(IntEnum):
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
		Create a threadgroup.

		thread_cls: A subclassed thread from / that behaves like the ones in
			`demomgr.threads`.
		tk_widget: The widget to use for tkinter's after machinery.
		"""
		self.thread_cls = thread_cls
		self.tk_wdg = tk_widget
		self.queue_out = queue.Queue()
		self.after_handle = self.tk_wdg.after(0, lambda: None)
		self.thread = DummyThread()
		self.heldback_queue_elem = None
		self.finalization_method = None
		self.run_always_method_pre = None
		self.run_always_method_post = None
		self._cb_method = None

	def register_finalize_method(self, method):
		"""
		Registers a finalization method with the threadgroup, which is called
		once when the thread has ended and the queue has been emptied by the
		callback method. It must fulfill the following criteria:
			It should take three input arguments, self, sig and *args.
				sig and args will be the last queue element that caused the
				callback method to return `THREADGROUPSIG.HOLDBACK`,
				if this signal was not received, the method will instead
				be called with sig = None and no args.
			The method should perform a heavy task that is best suited for
			the very end of thread activity, or may perform cleanup
			(Though this can easily be handled in the callback method as well.)

		method: The finalization method.

		Note that the finalization method must be registered before a
		call to build_cb_method.
		"""
		self.finalization_method = method

	def register_run_always_method_pre(self, method):
		"""
		Registers a method with the threadgroup which will be called
		ever time before the after callback runs. Useful for progress
		indicators.

		method: The method to be registered.

		Note that this method must be registered before a call to
		build_cb_method.
		"""
		self.run_always_method_pre = method

	def register_run_always_method_post(self, method):
		"""
		Registers a method with the threadgroup which will be called
		ever time after the after callback runs.

		method: The method to be registered.

		Note that this method must be registered before a call to
		build_cb_method.
		"""
		self.run_always_method_post = method

	def build_cb_method(self, cb_method):
		"""
		Builds an internal callback method from a class method so it works
		properly with the thread and is able to process elements from its
		output queue.
		The callback method must be structured as follows:
			It should take three input arguments, self, sig and args.
			It then performs actions on its class as normal depending on
			the received thread signal and its args.
			The method should return True to indicate that thread activity
			has finished (sig was a finish signal).
		It will be changed to only take one parameter (self) and re-added to
			targetobj under the same name, hiding the source method.

		targetobj: Object the queue processing method is an attribute of.
		cb_method: The queue processing callback method.

		example: `tg.build_cb_method(self, self.thread_callback)`
		"""
		if self.finalization_method is None:
			def decorated0(reschedule):
				finished = False
				while True:
					try:
						sig, *args = self.queue_out.get_nowait()
					except queue.Empty:
						break
					# Should be a bound method, so the original `self` is passed in automatically
					res = cb_method(sig, *args)
					if res is THREADGROUPSIG.FINISHED:
						finished = True
				if not finished and reschedule:
					# decorated is made a bound class method below, which this will access.
					self.after_handle = self.tk_wdg.after(CNST.GUI_UPDATE_WAIT, self._decorated_cb)
		else:
			def decorated0(reschedule):
				finished = False
				while True:
					try:
						sig, *args = self.queue_out.get_nowait()
					except queue.Empty:
						break
					res = cb_method(sig, *args)
					if res is THREADGROUPSIG.FINISHED:
						finished = True
					elif res is THREADGROUPSIG.HOLDBACK:
						self.heldback_queue_elem = (sig, *args)
				if not finished and reschedule:
					self.after_handle = self.tk_wdg.after(CNST.GUI_UPDATE_WAIT, self._decorated_cb)
				else:
					if self.heldback_queue_elem is None:
						self.finalization_method(None)
					else:
						sig, *args = self.heldback_queue_elem
						self.finalization_method(sig, *args)
					self.heldback_queue_elem = None

		# idk what's worse, nesting 2 decorated funcs or my if else branch
		# probably the if else branch
		if self.run_always_method_pre is None:
			if self.run_always_method_post is None:
				def decorated1(reschedule = True):
					decorated0(reschedule)
			else:
				def decorated1(reschedule = True):
					decorated0(reschedule)
					self.run_always_method_post()
		else:
			if self.run_always_method_post is None:
				def decorated1(reschedule = True):
					self.run_always_method_pre()
					decorated0(reschedule)
			else:
				def decorated1(reschedule = True):
					self.run_always_method_pre()
					decorated0(reschedule)
					self.run_always_method_post()

		self._decorated_cb = decorated1

	def start_thread(self, *args, **kwargs):
		"""
		Instantiate the thread with the supplied args and kwargs, except the
		ThreadGroup's output queue will always be passed in before them
		as `queue_out`, and then start it.
		"""
		if self._decorated_cb is None:
			raise ValueError(
				"No callback defined in threadgroup. Call build_cb_method on a "
				"suitable callback function."
			)
		self.heldback_queue_elem = None
		self.thread = self.thread_cls(queue_out = self.queue_out, *args, **kwargs)
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
		self.queue_out.queue.clear() # just to be reeeeeally safe

	def cancel_after(self):
		"""
		Cancels after handle immediatedly.
		"""
		self.tk_wdg.after_cancel(self.after_handle)
