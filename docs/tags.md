# Tag class
#### [Previous](./module_list.md) [Up](./README.md) [Next](./modbus_plc_demo.md)

## Concept
The Tag value can be read and written anywhere, quickly, and easily.
Code can be triggered by a value change. Tag's are not restricted to
one process.

This is linked to the design principle in pymscada that each
self-contained function runs in a separate process. Each process has
access to Tags via the bus.

Two classes support the Tag operation. The ```BusServer``` which runs
in the bus module, this keeps the last value and time of every tag,
provides the value and time to any request, and sends updates to any
connected subscriber to each tag. The ```BusClient``` makes a
connection to the bus module, publishes and subscribes as necessary
to send and receive tag values, and stops any update loops associated
with a __single__ tag.

## Properties
```value``` may be any of float, int, string, multi, list and dict.
multi is a state variable which is mostly handled as an integer, on
the web client the state names are displayed instead of the integer.
Don't use anything that needs pickling. The type may also be bytes,
see big values below.

Set ```value``` with either the value alone or a tuple, either
```(value, time_us)``` or ```(value, time_us, bus_id)```.

```time_us``` is the UTC time in microseconds. This is set by the
Tag when given a value, or by the time in the tuple if value is set
with a tuple. ```value, time_us``` is shared via the bus.

```bus_id``` is the source of the tag value update through the
```BusServer``` and ```BusClient```. If not set (normal in application
code) it is assigned 0. Otherwise it is assigned the python ```id()```
value for the object managing the connection.

```RQS```, see big values below.

## Methods
```add_callback``` allows you to registor your function to run when a
tag value changes. Your function must be a plain function (not a
co-routine) that takes an action and returns immediately without
blocking. __Do not__ update the triggering tag value in the callback,
this is an error.

## Update Loops
A tag value update is sent to every subscribed listener __except for__
the matching id of the sender. When you set a tag value every subsriber,
including the mechanism updating the bus, gets an update. There is a
potential for CPU hogging update loops.

Update loops are blocked at the simplest source by prohibiting value
updates of the calling tag when in a callback. These error immediately.
More complex circular loops are not blocked, you will need to avoid
creating these.

### Example with a multi tag
multi tags can be used as a singular state variable. This can be used
in a process to manage state. The multi tag can be presented to a user
via the web client as a single indicator / control variable. Consider
a four-state tag:

- __Off__ - process is stopped
- __Running__ - process is running
- __Idle__ - process is awaiting a condition to run
- __Run Now__ - immediate run is requested

In the callback function in your site logic, set a flag for the change.
The process responding to the flag should check and correct any state
transitions and update the multi tag value, which passes through the
bus to the web client, indicating the state.

At the web client a multi-setpoint display will both show the state and
provide a user with the ability to set the state. It only makes sense
(in this case) for the operator to set __Off__ or __Run Now__. A feature
I need to add is where options that don't make sense are grayed out. I
plan to do this via a leading _ in the multi text, so __Running__ would
become ___Running__. The process you write must still filter bad state
transitions.

## Big Values and RQS
Everything is shared via a tag value. This includes historical trend
data passed to the web display. These are passed in a packed bytes
structure that assumes int and float will fit in 64 bits. Tag values
to pass history are often several megabytes.

Tag values will also be used for database interaction. Operator notes
(module to come) is a database that can be updated from the web client.
To be bandwidth efficient, this should send a full display only when
requested, and otherwise update by exception. To support this, tags
have a ReQuest Set (RQS) function that allows a request to be set for
the tag.

RQS is passed to the bus. The bus passes the RQS to the last client
that set the tag value. This __requires__ care that only one process
is setting the tag value. It also makes it fairly simple to restart
the process and make a new connection the bus to establish the RQS
path.

Once the process writing the tag recieves an RQS, with an embedded id,
it responds accordingly. If one month worth of history for a tag is
requested this is retrieved (memory and disk as needed), placed in
a tag and sent with the RQS id. The RQS id allows the web server to
filter the packets send so that this is only sent to the requesting
web client.

The history module follows the megabyte sized bytes value with a null
value to make it small again, reducing the likelihood of a later
connection gaining a really large, stale, tag value.

## Web Display
Tags are displayed via the webserver. The web pages interact with tags
in a very similar manner to that described above. The wwwserver module
has additional mechanisms to extend the bus to the web client via
a websocket.

See the ```src/pymscada/demo``` folder for demo files. An example of
every type is displayed. The web display is fully defined by the
```wwwserver.yaml``` file, i.e. you don't manually draw or layout
any of the pages. There is no graphical P&ID style display and no
plans to add one.
