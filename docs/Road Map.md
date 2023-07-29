# Things I plan to add
## Pull Requests
If you decide to fix something and generate a pull request, please feel free.
However, please, keep them small and include a test.

Big changes I need time to consider and given the description of how this
package is supposed to work (under the hood) is largely missing it will be
hard to do a large change that fits with my vision for how this software is
supposed to work.

## Online configuration
Actually, I have no plan to add a pretty GUI for config. This is intended to be
a programmers SCADA application where its easy to stand up and do easy things,
simple enough to add complex things, but where you have to code to make it run.

## Alarms
Alarm detection is working in the parent application, I plan to port. Alarm callout
via a Teltonika RUT240 also works, also planning to port.

Missing (completely) is an alarm summary / history in the web client. I plan to do
this eventually however my intent is to avoid the Alarm Acknowledgement common to
SCADA systems. The reason for this is that Operator's tend to hit the Ack All button
quickly so the purpose of Acknowledge is uncertain.

Acknowledgement on the callout system, however, works and will be present. This stops
escalation to the next number on the list.

## Operator Notes
Works in the parent application. Plan to port. This is just a version of Notepad, but
kept together with the web page so that it is visible in more places.

## WITS and Transpower Dispatch
Specific to NZ electricity market. Present in parent, uncertain what my plan is for
these.

## Optimal Dispatch & Observer
This is modelling software that describes and does a model predictive optimal solve
for operation of plant. Presently running with dispatch of generation and management
of storage with respect to river flows and storage rules.

Likely to remain commercial offering only.

## Config, History and Notes download tool
This is new in the open application. Needs work.

## Modbus TCP
There is a python library for this, however I also have an embedded one to migrate.
Use either.

## pycomm3
If you want to talk to Rockwell PLCs use this. I intend to. I'll have some examples
added at some point. The existence of pycomm3 is what prompted me to consider open
sourcing Mobile SCADA.
