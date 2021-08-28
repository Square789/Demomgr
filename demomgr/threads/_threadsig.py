"""
THREADSIG enum
Located here in order to prevent a circular import.
"""

from enum import IntEnum

# NOTE: There are many signals in here specifically made
# for and used by only one thread type

# Zero-Parameter values:          0x0   - 0x1FF
# |---Result level (Termination): |- 0x0   - 0xFF
# '---Info level:                 '- 0x100 - 0x1FF
# One-Parameter values:           0x200 - 0x3FF
# |---Info level:                 |- 0x200 - 0x2FF
# '---Result level:               '- 0x300 - 0x3FF
# Two-Parameter values:           0x400 - 0x5FF
# |---Info level:                 |- 0x400 - 0x4FF
# '---Result level:               '- 0x500 - 0x5FF
# etc.


class THREADSIG(IntEnum):
	SUCCESS = 0x0
	FAILURE = 0x1
	ABORTED = 0x2

	CONNECTED = 0x100
	EVENT_FILE_MISSING = 0x101

	INFO_CONSOLE = 0x200
	INFO_STATUSBAR = 0x201
	INFO_INFORMATION_CONTAINERS = 0x202

	RESULT_DEMODATA = 0x300
	RESULT_FS_INFO = 0x301
	RESULT_HEADER = 0x302
	RESULT_DEMO_AMOUNT = 0x303

	INFO_IDX_PARAM = 0x400

	def is_finish_signal(self):
		return self.value < 0x100

