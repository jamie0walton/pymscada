# Things I plan to add
#### [Previous](./apache.md) [Up](./README.md)

## Pull Requests
If you decide to fix something keep it small. I will likely edit and,
at very least, add some tests. Nothing big at the moment please.

## Future
I hope this works well and finds a suitable niche. The controls
industry is very conservative so I'd like to keep the functionality
reasonably complete for a SCADA package but without attempting to do
everything.

Plans for the future:

1. Consider adding Tag classes for each data type. i.e.
```TagInt('tagname')``` as opposed to ```Tag('tagname', int)```.

1. Prefix multi tag state descriptions with _ and grey these options
out in the angular web client.

1. Make the _files_ module work for downloading history, config and
pdf files, and allow upload of pdf files.

1. Add an _alarms_ system. I have an SMS callout module in MobileSCADA
however this needs a rethink.

1. Add a [pycomm3](https://github.com/ottowayi/pycomm3) wrapper. A
lot of my projects connect to Rockwell PLCs.

1. Improve ```pytest``` coverage.
