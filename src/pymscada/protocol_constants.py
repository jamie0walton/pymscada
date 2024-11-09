"""
Protocol description and protocol constants.

Bus holds a tag forever, assigns a tag id forever, holds a tag value with len
< 1000 forever, otherwise wipes periodically. So assign tagnames once, at the
start of your program; use RTA as an update messenger, share whole structures
rarely.

- version 16-bit unsigned int == 0x01
- command 16-bit unsigned int
- tag_id 32-bit unsigned int     0 is not a valid tag_id
- size 32-bit unsigned int
  - if size == 0xff  continuation mandatory
  - size 0x00 completes an empty continuation
- time_us 128-bit unsigned int, UTC microseconds
- data size of 8-bit char

command
- CMD.ID data is tagname
  - reply: CMD_ID with tag_id and data as tagname
- CMD.SET id, data is typed or json packed
  - no reply
- CMD.UNSUB id
  - no reply
- CMD.GET id
- CMD.RTA id, data is request to author
- CMD.SUB id
  - reply: SET id and value, value may be None
- CMD.LIST
  - size == 0x00
    - tags with values newer than time_us
  - size > 0x00
    - ^text matches start of tagname
    - text$ matches start of tagname
    - text matches anywhere in tagname
  - reply: LIST data as space separated tagnames
- CMD.LOG data to logging.warning
"""

# Tuning constants
MAX_LEN = 65535 - 14  # TODO fix server(?) when 3

from enum import IntEnum

class COMMAND(IntEnum):
    ID = 1     # query / inform tag ID - data is tagname bytes string
    SET = 2    # set a tag
    GET = 3    # get a tag
    RTA = 4    # request to author
    SUB = 5    # subscribe to a tag
    UNSUB = 6  # unsubscribe from a tag
    LIST = 7   # bus list tags
    ERR = 8    # action failed
    LOG = 9    # bus print a logging message

    @staticmethod
    def text(cmd) -> str:
        """Return command text description for enum or int."""
        return COMMAND(cmd).name

class TYPE(IntEnum):
    INT = 1    # 64 bit signed integer
    FLOAT = 2  # 64 bit IEEE float
    STR = 3    # string
    BYTES = 4  # raw bytes
    JSON = 5   # JSON encoded data
