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
- CMD_ID data is tagname
  - reply: CMD_ID with tag_id and data as tagname
- CMD_SET id, data is typed or json packed
  - no reply
- CMD_UNSUB id
  - no reply
- CMD_GET id
- CMD_RTA id, data is request to author
- CMD_SUB id
  - reply: SET id and value, value may be None
- CMD_LIST
  - size == 0x00
    - tags with values newer than time_us
  - size > 0x00
    - ^text matches start of tagname
    - text$ matches start of tagname
    - text matches anywhere in tagname
  - reply: LIST data as space separated tagnames
- CMD_LOG data to logging.warning
"""

# Tuning constants
MAX_LEN = 65535 - 14  # TODO fix server(?) when 3

# Network protocol commands
CMD_ID = 1  # query / inform tag ID - data is tagname bytes string
CMD_SET = 2  # set a tag
CMD_GET = 3  # get a tag
CMD_RTA = 4  # request to author
CMD_SUB = 5  # subscribe to a tag
CMD_UNSUB = 6  # unsubscribe from a tag
CMD_LIST = 7  # bus list tags
CMD_ERR = 8  # action failed
CMD_LOG = 9  # bus print a logging message

CMD_TEXT = {
    1: 'CMD_ID',
    2: 'CMD_SET',
    3: 'CMD_GET',
    4: 'CMD_RTA',
    5: 'CMD_SUB',
    6: 'CMD_UNSUB',
    7: 'CMD_LIST',
    8: 'CMD_ERR',
    9: 'CMD_LOG'
}

COMMANDS = [CMD_ID, CMD_SET, CMD_GET, CMD_RTA, CMD_SUB, CMD_UNSUB, CMD_LIST,
            CMD_ERR, CMD_LOG]

# data types
TYPE_INT = 1  # 64 bit signed integer
TYPE_FLOAT = 2  # 64 bit IEEE float
TYPE_STR = 3  # string
TYPE_BYTES = 4
TYPE_JSON = 5

TYPES = [TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_BYTES, TYPE_JSON]
