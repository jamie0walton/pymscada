# pymscada
#### [Docs](https://github.com/jamie0walton/pymscada/blob/main/docs/README.md)

#### [@Github](https://github.com/jamie0walton/pymscada/blob/main/README.md)

## Python Mobile SCADA

This is a small SCADA package that will run on Linux (preferably) or
Windows. The server runs as several modules on the host, sharing
information through a message bus. A __subset__ of modules is:

- Bus server - shares tag values with by exception updates
- Modbus client - reads and writes to a PLC using Modbus/TCP
- History - saves data changes, serves history to web pages
- Web server - serves web pages which connect with a web socket
- Web pages - an Angular single page web application

Web pages are responsive and defined procedurally from the
```wwwserver.yaml``` config file.

Trends use [uPlot](https://github.com/leeoniya/uPlot).

## Objectives

Traditional SCADA has a fixed 19:6, 1920x1080 or some equivalent layout.
It's great on a big screen but not good on a phone. Hence __Mobile__
SCADA with a responsive layout.

I wrote Mobile SCADA to provide a GUI to the other things I was trying to
do, I wanted to leverage web browsers and eliminate a dedicated
_viewer.exe_. Display on the client is fast, trends, as fast as I can
make them.

Uptimes should be excellent. The best I have on an earlier version is
over 5 years for about half of the script modules. This version is a
complete rewrite, however the aim is the same.

All tag value updates are by exception. So an update from you setting a
value to seeing the feedback should be __FAST__.

# Licence

```pymscada``` is distributed under the GPLv3 [license](./LICENSE).

# Example Use
This was all run on a Raspberry Pi 3B+ with a 16GB SDRAM card.

## First
Checkout the example files. Start in an empty directory. Plan to keep
in the directory you check out into as the config file path details
are auto-generated for the location you check out in to.
```bash
mscada@raspberrypi:~/test $ pymscada checkout
making 'history' folder
making pdf dir
making config dir
Creating  /home/mscada/test/config/modbusclient.yaml
Creating  /home/mscada/test/config/pymscada-history.service
Creating  /home/mscada/test/config/wwwserver.yaml
Creating  /home/mscada/test/config/pymscada-demo-modbus_plc.service
Creating  /home/mscada/test/config/files.yaml
Creating  /home/mscada/test/config/pymscada-modbusserver.service
Creating  /home/mscada/test/config/pymscada-wwwserver.service
Creating  /home/mscada/test/config/simulate.yaml
Creating  /home/mscada/test/config/tags.yaml
Creating  /home/mscada/test/config/history.yaml
Creating  /home/mscada/test/config/pymscada-files.service
Creating  /home/mscada/test/config/bus.yaml
Creating  /home/mscada/test/config/modbusserver.yaml
Creating  /home/mscada/test/config/modbus_plc.py
Creating  /home/mscada/test/config/pymscada-modbusclient.service
Creating  /home/mscada/test/config/pymscada-bus.service
Creating  /home/mscada/test/config/README.md
mscada@raspberrypi:~/test $
``` 

## Objective
To show a trend of the temperature forecast with a custom pymscada bus
client program. The end result should look like ...

![Temperature](temperature%20trend.png)

## Configuration
### Bus
Defaults in ```bus.yaml``` are fine.

### Tags
Add some tags in ```tags.yaml```:
```yaml
temperature:
  desc: temperature
  type: float
  min: 0
  max: 35
  units: C
  dp: 1
temperature_01:
  desc: temperature_01
  type: float
  min: 0
  max: 35
  units: C
  dp: 1
... etc.
```

### History
Defaults in ```history.yaml``` are fine.

### Web Server
You will need to add a trend page to ```wwwserver.yaml``` as:
```yaml
- name: Temperature     # Creates a Temperature page in the web client
  parent: Weather       # Add the Temperature page in a submenu under Weather
  items:
  - type: uplot         # Identify the Angular component to use
    ms:
      desc: Temperature
      age: 172800
      legend_pos: left
      time_pos: left
      time_res: m
    axes:
    - scale: x
      range: [-604800, 86400]  # initial time range for the trend
    - scale: 'C'
      range: [0.0, 35.0]
      dp: 1
    series:
    - tagname: temperature     # pymscada Tag name
      label: Current Temperature
      scale: 'C'
      color: black             # standard html colour names
      width: 2
      dp: 1                    # number of decimal places
... etc for additional series
```

### Your custom pymscada Module
For this example I polled [tomorrow.io](https://www.tomorrow.io/weather-api/)

```weather.py```
```python
from datetime import datetime
import time
from pymscada import BusClient, Periodic, Tag

URL = 'https://api.tomorrow.io/v4/timelines'
QUERY = {'location': '-43.527934570040124, 172.6415203551829',
         'fields': ['temperature'],
         'units': 'metric',
         'timesteps': '1h',
         'startTime': 'now',
         'endTime': 'nowPlus24h',
         'apikey': '<your key>'}

class PollWeather():
    def __init__(self):
        self.tags = {}
        for tagname in ['temperature', 'temperature_01', 'temperature_04',
                        'temperature_12', 'temperature_24']:
            # Create pymscada tags, tags are singletons by 'tagname'
            self.tags[tagname] = Tag(tagname, float)

    async def periodic(self):
        now = int(time.time())
        if now % 3600 != 120:
            return
        # Get the weather forecast from tomorrow.io
        async with aiohttp.ClientSession() as session:
            async with session.get(URL, params=QUERY) as resp:
                response = await resp.json()
        utc_now = None
        for row in response['data']['timelines'][0]['intervals']:
            convert = row['startTime'].replace('Z', '+0000')
            utc = datetime.strptime(convert, '%Y-%m-%dT%H:%M:%S%z').timestamp()
            if utc_now is None:
                utc_now = utc
                forecast = ''
            else:
                forecast = f'_{int((utc - utc_now) / 3600):02d}'
            if forecast not in ['', '_01', '_04', '_12', '_24']:
                continue
            for k, v in row['values'].items():
                ftag = k + forecast
                value = float(v)
                time_us = int(utc * 1000000)
                if ftag in self.tags:
                    # Write the tag value. This is one of the following:
                    # - value                      # time_us, bus_id auto-generated
                    # - value, time_us             # bus_id auto-generated
                    # - value, time_us, bus_id     # Don't use this one
                    self.tags[ftag].value = value, time_us

async def main():
    # Connect to the bus and poll the weather service.
    bus = BusClient()
    await bus.start()
    weather = PollWeather()                         # demo function
    periodic = Periodic(weather.periodic, 1.0)      # part of pymscada
    await periodic.start()
    await asyncio.get_event_loop().create_future()  # run forever

if __name__ == '__main__':
    asyncio.run(main())
```

# Run the modules
You can run the modules in one of: individual terminals, ```nohup ... &``` or as a
```systemd``` service. I run as a service, the snips are abbreviated (no path) from
the exec line in the auto-generated service files.

Run the bus first! This needs to remain running all the time. It does not need to
know the tagnames in advance so it can run forever for most tests. It will gather
dead tagnames over time as you are experimenting, however this only requires a
small amount of memory (unless you are setting tag values in the MB - which does
work).

```bash
pymscada bus --config bus.yaml
pymscada wwwserver --config wwwserver.yaml --tags tags.yaml
pymscada history --config history.yaml --tags tags.yaml
python weather.py
```
