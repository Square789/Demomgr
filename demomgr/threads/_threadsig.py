"""
Unfortunately, threads will need to import THREADSIG
from here in order to prevent a circular import.
"""

# Zero-Parameter values: 0x0   - 0xFF
# One-Parameter values:  0x100 - 0x2FF
# |---Info level:        |- 0x100 - 0x1FF
# '---Result level:      '- 0x200 - 0x2FF
#
# Two-Parameter values:  0x300 - 0x4FF
# |---Info level:        |- 0x300 - 0x3FF
# '---Result level:      '- 0x400 - 0x4FF
# etc.
class THREADSIG:
	SUCCESS = 0x0
	FAILURE = 0x1
	ABORTED = 0x2

	INFO_CONSOLE = 0x100
	INFO_STATUSBAR = 0x101
	RESULT_DEMODATA = 0x200
	RESULT_FS_INFO = 0x201
	RESULT_HEADER = 0x202
	RESULT_DEMO_AMOUNT = 0x203

	INFO_IDX_PARAM = 0x300
