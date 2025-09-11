# Tag class
#### [Previous](./module_list.md) [Up](./README.md) [Next](./modbus_plc_demo.md)

## Overview
```pymscada``` is based on sharing ```Tag``` values across processes. Tags can be read
and written anywhere, with values transparently passed through the message bus.
Code can be triggered by value changes through callbacks, and Tags are not restricted to
one process.

## Architecture
Each module runs as a separate process with access to Tags via the bus:

- ```BusServer``` runs in the bus module, maintaining the last value and time of every tag
- ```BusClient``` connects to the bus, publishes and subscribes to tag values
- ```Tag``` objects provide local access to shared values with callback mechanisms

## Data Flow and Callbacks

Note that Tag methods can be called by co-routines but CANNOT callback a co-routine.

### Tag Value Update Flow
1. Tag value changes - set by any process
2. Tag callbacks execute - immediate, local to the process
3. Value published to bus - if BusClient is connected
4. Bus distributes to subscribers - other connected processes
5. Remote tag callbacks execute - in other processes

### Two Types of Callbacks

#### Tag Callbacks - Respond to Value Changes
```python
# Register a function to run when tag value changes
tag.add_callback(self.handle_value_change)

# Callback function signature
def handle_value_change(self, tag: Tag):
    # tag.value - the new value
    # tag.name - the tag name
    # tag.time_us - timestamp in microseconds
    # tag.type - the tag's data type
```

Use when: You need to respond immediately to tag value changes
Examples: Process control logic, status updates, alarm triggers

#### RTA Callbacks - Respond to Explicit Requests
```python
# Register a handler for RTA (Request to Author) messages
self.busclient.add_callback_rta(rta_tag, self.handle_rta_request)

# RTA callback function signature
def handle_rta_request(self, request: dict):
    # request contains action, parameters, request_id, etc.
    # Respond by setting self.rta.value
    self.rta.value = {'status': 'success', 'data': result}
```

Use when: You need to handle on-demand requests for data or actions
Examples: Database queries, file operations, configuration changes, large data transfers

### RTA (Request to Author) Flow
1. Client sends RTA request via bus
2. Bus routes to last process that set the tag value
3. RTA callback executes in the target process
4. Response published via rta_tag.value
5. Requesting client receives the response

## Tag Properties

### Value Types
```value``` may be any of:
- float, int, string - Basic data types
- multi - State variable (displayed as text, handled as integer)
- list and dict - Complex data structures
- bytes - For large values (see Big Values section)

Note: Don't use anything that needs pickling.

### Setting Values
```python
# Simple value assignment, time and bus_id auto-set
tag.value = 42

# With timestamp (microseconds), bus_id auto-set
tag.value = (42, 1640995200000000)

# With timestamp and bus_id
tag.value = (42, 1640995200000000, bus_id)
```

## Methods

### add_callback(callback, bus_id: int = 0)
Register a function to run when a tag value changes.

Requirements:
- Function must be plain (not a coroutine)
- Must return immediately without blocking
- Do not update the triggering tag value in the callback (causes error)

Example:
```python
def status_changed(self, tag: Tag):
    if tag.value == 'Running':
        self.start_process()
    elif tag.value == 'Stopped':
        self.stop_process()

status_tag.add_callback(self.status_changed)
```

## Update Loops and Prevention

### How Updates Work
A tag value update is sent to every subscribed listener except the matching bus_id of the sender. This prevents immediate feedback loops.

### Loop Prevention Mechanisms
1. Immediate blocking - Tag callbacks cannot update the triggering tag
2. Bus_id filtering - Sender doesn't receive their own updates
3. Manual prevention - Avoid creating circular update patterns

## Request to Author (RTA)

### Large Data Transfer
Tags can handle values up to several megabytes, including:
- Historical trend data
- File contents
- Database query results
- Configuration dumps

### RTA for Efficiency
Instead of continuously publishing large values:
1. Small tag value - Contains metadata or status
2. RTA request - Client requests specific data
3. Response - Large data sent only when requested
4. Reset - Tag value reset to small size

### RTA Implementation Pattern
```python
def handle_rta_request(self, request: dict):
    if request['action'] == 'GET_HISTORY':
        # Retrieve large dataset
        data = self.get_historical_data(request['start'], request['end'])
        
        # Send response with request ID
        self.rta.value = {
            '__rta_id__': request['__rta_id__'],
            'data': data
        }
        
        # Reset to small value
        self.rta.value = {'status': 'ready'}
```
