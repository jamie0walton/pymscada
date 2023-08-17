"""
Protocol description and protocol constants.

Bus holds a tag forever, assigns a tag id forever, holds a tag value with len
< 1000 forever, otherwise wipes periodically. So assign tagnames once, at the
start of your program; use RQS as an update messenger, share whole structures
rarely.

- version 16-bit int == 0x01
- command 16-bit int
- tag_id 16-bit int
- size 16-bit unsigned int
  - if size == 0xff  continuation mandatory
  - size 0x00 completes an empty continuation
- time_us 64-bit unsigned int, UTC microseconds
- data size of 16-bit words

command
- ID size < 0x0f data is tagname
  - reply: ID with tag_id and data as tagname
- SET size <= 0xff data is typed or json packed
- UNSUB size == 0x00
  - no reply
- GET size == 0x00 data is empty
- RQS size <= 0xff data is request to tag creator
- SUB size == 0x00 data is empty
  - reply: SET with tag_id and value, value may be None
- LIST intended for interactive shell
  - size == 0x00 tags with values newer than time_us
  - size > 0x00
    - ^text matches start of tagname
    - text$ matches start of tagname
    - text matches anywhere in tagname
- reply: LIST with tag_id of 0
"""

# Tuning constants
MAX_LEN = 65535  # sometimes negligibly faster at 65535 - 14

# Network protocol commands
CMD_ID = 1  # query / inform tag ID - data is tagname bytes string
CMD_SET = 2  # set a tag
CMD_GET = 3  # get a tag
CMD_RQS = 4  # request set - request passed to last tag setter
CMD_SUB = 5  # subscribe to a tag
CMD_UNSUB = 6  # unsubscribe from a tag
CMD_LIST = 7  # bus list tags
CMD_ERR = 8  # action failed

CMD_TEXT = {
    1: 'CMD_ID',
    2: 'CMD_SET',
    3: 'CMD_GET',
    4: 'CMD_RQS',
    5: 'CMD_SUB',
    6: 'CMD_UNSUB',
    7: 'CMD_LIST',
    8: 'CMD_ERR'
}

COMMANDS = [CMD_ID, CMD_SET, CMD_GET, CMD_RQS, CMD_SUB, CMD_UNSUB, CMD_LIST,
            CMD_ERR]

# data types
TYPE_FLOAT = 1  # 64 bit IEEE float
TYPE_INT = 2  # 64 bit signed integer
TYPE_STR = 3  # string
TYPE_JSON = 4  # json encoded list or dict

TYPES = [TYPE_FLOAT, TYPE_INT, TYPE_STR, TYPE_JSON]
