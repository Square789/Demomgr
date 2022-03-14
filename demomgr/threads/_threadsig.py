"""
THREADSIG enum containing values to communicate the type of a thread
queue tuple.
Located here in order to prevent a circular import.
"""

from enum import IntEnum

# NOTE: There are many signals in here specifically made
# for and used by only one thread type. I guess you could
# also give each thread its own signal enum but naaaah

class THREADSIG(IntEnum):
	# Termination signals
	SUCCESS = 0x0
	FAILURE = 0x1
	ABORTED = 0x2

	# Thread milestones / information snippets
	CONNECTED = 0x100
	FILE_OPERATION_SUCCESS = 0x101
	FILE_OPERATION_FAILURE = 0x102
	BOOKMARK_CONTAINER_UPDATE_START = 0x103
	BOOKMARK_CONTAINER_UPDATE_SUCCESS = 0x104
	BOOKMARK_CONTAINER_UPDATE_FAILURE = 0x105

	# Info that should be directly displayed
	INFO_CONSOLE = 0x200
	INFO_STATUSBAR = 0x201
	INFO_INFORMATION_CONTAINERS = 0x202
	INFO_IDX_PARAM = 0x203

	# Result data
	RESULT_DEMODATA = 0x300
	RESULT_FS_INFO = 0x301
	RESULT_HEADER = 0x302
	RESULT_INFO_WRITE_RESULTS = 0x303

	def is_finish_signal(self):
		return self.value < 0x100
