"""
Protocol description and protocol constants.

Bus holds a tag forever, assigning a new ID for each new tagname.

Bus protocol message format:
- version: 8-bit unsigned int == 0x01
- command: 8-bit unsigned int
- tag_id: 16-bit unsigned int (0 is valid for ID requests)
- size: 16-bit unsigned int
- time_us: 64-bit unsigned int, UTC microseconds
- data: variable length bytes of size

Commands:
- CMD.ID: Query/inform tag ID
  - Request: data is tagname as bytes
  - Reply: CMD.ID with assigned tag_id and tagname as data
  - Error: CMD.ERR if tagname undefined
  
- CMD.SET: Set a tag value
  - Data format: TYPE byte + typed value
  - No reply
  - Error: CMD.ERR if tag_id invalid
  
- CMD.GET: Get a tag value
  - Request: empty data
  - Reply: CMD.SET with current value
  - Error: CMD.ERR if tag_id invalid
  
- CMD.RTA: Request to author
  - Request: JSON encoded request
  - Reply: Comes from target client, not server
  - Error: CMD.ERR if tag_id invalid or target gone
  
- CMD.SUB: Subscribe to tag updates
  - Request: empty data
  - Reply: CMD.SET with current value
  - Error: CMD.ERR if tag_id invalid
  
- CMD.UNSUB: Unsubscribe from tag
  - No reply
  - Error: CMD.ERR if tag_id invalid
  
- CMD.LIST: List tags
  - Empty data: tags newer than time_us
  - ^text: tags starting with text
  - text$: tags ending with text 
  - text: tags containing text
  - Reply: CMD.LIST with space-separated tagnames
  
- CMD.LOG: Log message
  - Data: Message to log (max 300 bytes)
  - Updates __bus__ tag with client address and message

Large messages are split into MAX_LEN chunks. Final chunk size < MAX_LEN.
"""

# Tuning constants
MAX_LEN = 65535 - 14  # Maximum data size per message

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
