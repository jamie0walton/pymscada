import asyncio
import logging
import time
from array import array
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from struct import unpack
from yaml import UnsafeLoader, dump, load
from pymscada import BusClient, TagTyped
from pymscada.milp.model_hyd import HydraulicModel, TimeSeries, Constraint
from pymscada.bus_client_tag import TagInt, TagFloat, TagStr, TagDict, TagBytes
from pymscada.periodic import Periodic
from pymscada.misc import bid_period
from pymscada.bus_misc import BusTask


OFF = 0
TIMED_RUN = 1
RUNNING = 2
RUN_NOW = 3

# OFF = 0 also needed
FIXED = 1
FREE = 2

YET_TO_RUN = 0
GOOD = 1
BAD = 2


def find_matching_key_values(key: str, tree):
    """The key and value where the key is a substring."""
    if isinstance(tree, dict):
        for i in tree:
            if key in i:
                yield tree[i]
            yield from find_matching_key_values(key, tree[i])
    elif isinstance(tree, list):
        for i in tree:
            yield from find_matching_key_values(key, i)


class MPCTag:
    def __init__(self, tagname: str, type: str, age_s: int | None = None,
                 deadband: float | None = None):
        self.name = tagname
        self.age_us: int | None = age_s * 1000000 if age_s else None
        if type == 'float':
            self.tag = TagFloat(tagname)
            if self.age_us is not None:
                self.tag.age_us = self.age_us
        elif type == 'int':
            self.tag = TagInt(tagname)
        elif type == 'dict':
            self.tag = TagDict(tagname)
        else:
            raise ValueError(f"Invalid type: {type}")
        self.deadband: float | None = deadband
        self._timeseries: TimeSeries | None = None

    @property
    def value(self) -> float | int | dict:
        """Get the value of the tag."""
        if isinstance(self.tag, TagFloat):
            return self.tag.value
        elif isinstance(self.tag, TagInt):
            return self.tag.value
        elif isinstance(self.tag, TagDict):
            v = self.tag.value
            return {
                'period': [bid_period(x) for x in v['times']],
                'times': v['times'],
                'values': v['values'],
                'setpoint': [int(x) for x in v['values']],
            }
        else:
            raise ValueError(f"Invalid type: {type(self.tag)}")

    @property
    def id(self):
        """Get the id of the tag."""
        if self.tag is None:
            raise ValueError(f"{self.name} Tag is not set.")
        return self.tag.id

    @property
    def times_us(self):
        """Get the times_us of the tag."""
        if isinstance(self.tag, TagFloat):
            return self.tag.times_us
        else:
            raise ValueError(f"Invalid type: {type(self.tag)}")

    @times_us.setter
    def times_us(self, times_us: array[int]):
        """Set the times_us of the tag."""
        if isinstance(self.tag, TagFloat):
            self.tag.times_us = times_us
        else:
            raise ValueError(f"Invalid type: {type(self.tag)}")

    @property
    def values(self):
        """Get the values of the tag."""
        if isinstance(self.tag, TagFloat):
            return self.tag.values
        else:
            raise ValueError(f"Invalid type: {type(self.tag)}")

    @values.setter
    def values(self, values: array[float]):
        """Set the values of the tag."""
        if isinstance(self.tag, TagFloat):
            self.tag.values = values
        else:
            raise ValueError(f"Invalid type: {type(self.tag)}")

    @property
    def timeseries(self):
        """Get the timeseries of the tag."""
        if not isinstance(self.tag, TagFloat):
            raise ValueError(f"Invalid type: {type(self.tag)}")
        if self.age_us is None:
            tsv = self.value
        else:
            last_v = None
            tsv = {}
            for t, v in zip(self.times_us, self.values):
                t = int(t / 1e6)
                if v != last_v:
                    tsv[t] = v
                    last_v = v
        self._timeseries = TimeSeries(tsv)
        return self._timeseries


class MPCRunner:
    def __init__(self, temp_dir: str, log_dir: str, control_tag: str,
                 history_tag: str, solve_time_tag: str, last_solve_tag: str,
                 setpoint_tag: str, result_tag: str, status_tag: str,
                 duration_tag: str, solver_timeout: int, time_step: int,
                 duration: int, tags: dict, model: dict):
        self.temp_dir = temp_dir
        self.log_dir = log_dir
        self.control_tag = TagInt(control_tag)
        self.control_tag.add_callback(self.control_tag_callback)
        self.history_tag = TagBytes(history_tag)
        self.solve_time_tag = TagFloat(solve_time_tag)
        self.last_solve_tag = TagInt(last_solve_tag)
        self.status_tag = TagInt(status_tag)
        self.setpoint_tag = TagFloat(setpoint_tag)
        self.setpoint_tag.add_callback(self.setpoint_callback)
        self.result_tag = TagDict(result_tag)
        self.duration_tag = TagInt(duration_tag)
        self.duration_tag.add_callback(self.duration_callback)
        self.solver_timeout = solver_timeout
        self.time_step = time_step
        self.duration = duration
        self.duration_tag.value = int(duration / 3600)
        self.tags: dict[str, MPCTag] = {}
        for tagname, cfg in tags.items():
            self.tags[tagname] = MPCTag(tagname, **cfg)
        self.model_config = model
        self.model = {}
        self.hydraulic_model = None
        self.saved_model_path = None
        self.site_time = TagInt('_site_time')
        self.periodic = Periodic(self.periodic_cb, 1.0)
        self.queue = asyncio.Queue()
        self.solver_running = False
        self.status_tag.value = YET_TO_RUN

    def duration_callback(self, tag: TagInt):
        """Callback for the duration tag."""
        self.duration = tag.value * 3600

    def make_model(self, actual_time: int | None=None):
        """
        Create the model needed to run Hydraulic Model. If there is a saved
        path, read the saved model and the time parameters needed for the run.
        """
        self.model['name'] = 'Hydraulic Model'
        if actual_time is None:
            actual_time = int(time.time())
        self.model['actual_time'] = actual_time
        self.model['time_step'] = self.time_step
        self.model['duration'] = self.duration
        self.model['tempdir'] = self.temp_dir
        self.model['logdir'] = self.log_dir
        self.model['model'] = {}
        # TODO this is because of a mutation in HydraulicModel that needs
        # to be fixed.
        c = deepcopy(self.model_config)
        m = self.model['model']
        for node in c:
            m[node] = {}
            for k, v in c[node].items():
                if k == 'state':
                    if v == 'OFF':
                        v = OFF
                    elif v == 'FIXED':
                        v = FIXED
                    elif v == 'FREE':
                        v = FREE
                    else:
                        logging.error(f"Invalid state: {v}")
                        raise ValueError(f"Invalid state: {v}")
                elif k == 'time_series_tag':
                    k = 'time_series'
                    v = self.tags[v].timeseries
                elif k.endswith('_tag'):
                    k = k[:-4]
                    v = self.tags[v].value
                m[node][k] = v

    def save_model(self):
        """Save the model to a file."""
        p = Path(self.temp_dir) / f'mp_control_model.yaml'
        with p.open('w', encoding='utf-8') as f:
            dump(self.model, f)

    async def model_runner(self):
        self.control_tag.value = OFF
        while True:
            msg = await self.queue.get()
            logging.info(f"{msg['action']} {msg['reason']}")
            if msg['action'] == 'run_model':
                self.control_tag.value = RUNNING
                self.solve_time_tag.value = 0
                self.solver_running = True
                self.make_model()
                self.save_model()
                m = HydraulicModel(self.model, timeout=self.solver_timeout)
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, m.solve_lp)
                show = {
                    'actual_time': self.model['actual_time'],
                    'found': m.lp.found,
                    'optimum': m.lp.optimum,
                    'solutioncost': m.lp.solutioncost,
                    'results': {}
                }
                if m.lp.found:
                    self.status_tag.value = GOOD
                    self.last_solve_tag.value = int(time.time() * 1e6)
                    results = m.lp.resultsdict
                    for node in self.model['model']:
                        if 'result' in self.model['model'][node]:
                            parm = self.model['model'][node]['result']
                            show['results'][node] = results[node][parm]
                else:
                    self.status_tag.value = BAD
                self.result_tag.value = show
                self.solver_running = False
                if self.control_tag.value == RUNNING:
                    self.control_tag.value = TIMED_RUN
            pass

    def control_tag_callback(self, tag: TagInt):
        """Callback for the control tag."""
        if tag.value == RUN_NOW:
            self.queue.put_nowait({'action': 'run_model',
                                   'reason': 'Operator control'})

    def setpoint_callback(self, tag: TagFloat):
        """Callback for the setpoint tag."""
        if time.time() - tag.time_us / 1e6 > 60:
            logging.warning(f"Ignored {tag.value} MW > 1 minute ago.")
            return
        if self.control_tag.value == TIMED_RUN:
            self.queue.put_nowait({'action': 'run_model',
                                   'reason': 'Setpoint changed'})

    def model_tags_callback(self, tag: TagInt | TagFloat | TagDict):
        """Single callback, connect changes to correct actions and updates."""
        pass

    async def fill_history(self, rta: Callable):
        """Fill the history tags."""
        while TagTyped.check_none_ids():
            await asyncio.sleep(0.1)
        fill_done = asyncio.Event()
        fill_tags = set()

        def fill_history_cb(tag: TagBytes):
            # packed with self.rta.value = pack('>HHH', rta_id, tagid,
            # packtype) + data
            if len(tag.value) == 6:
                return
            _, tagid, packtype = unpack('>HHH', tag.value[:6])
            dtag = None
            for dtag in self.tags.values():
                if dtag.id == tagid:
                    break
            if dtag is None:
                logging.error(f"tag {tagid} not found")
                return
            payload = tag.value[6:]
            if packtype == 1:
                fmt = '>Qq'
            elif packtype == 2:
                fmt = '>Qd'
            else:
                logging.error(f"unknown packtype: {packtype}")
                return
            data = [unpack(fmt, payload[i:i+16])
                    for i in range(0, len(payload), 16)]
            repack_data = {}
            for time_us, value in data:
                repack_data[time_us] = value
            for time_us, value in repack_data.items():
                dtag.times_us.append(time_us)
                dtag.values.append(value)
            fill_tags.remove(dtag.name)
            if len(fill_tags):
                return
            fill_done.set()

        self.history_tag.add_callback(fill_history_cb)
        now = int(time.time() * 1000000)
        for tag in self.tags.values():
            if tag.age_us is not None:
                start_us = now - tag.age_us
                logging.info(f"request {tag.name}")
                rta(self.history_tag.name, {
                    '__rta_id__': 0,
                    'tagname': tag.name,
                    'start_us': start_us,
                    'end_us': now
                })
                fill_tags.add(tag.name)
        await fill_done.wait()
        self.history_tag.del_callback(fill_history_cb)
        # TODO should unsubscribe from the history tag

    async def periodic_cb(self):
        """Every second."""
        if self.control_tag.value == TIMED_RUN:
            t = time.localtime()
            if t.tm_min % 10 == 0 and t.tm_sec == 30:
                self.queue.put_nowait({'action': 'run_model',
                                       'reason': 'timed run'})
        if self.solver_running:
            self.solve_time_tag.value += 1

    async def start(self, rta: Callable):
        """Start the MPCRunner."""
        await self.fill_history(rta)
        await self.periodic.start()
        BusTask(self.model_runner())


class MPAnalyser:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def start(self):
        """Run the model analyser and exit."""
        model_path = self.kwargs.get('load', None)
        if model_path is None:
            raise ValueError("load argument is required")
        timeout = self.kwargs.get('solver_timeout', 60)
        with open(model_path, encoding='utf-8') as f:
            model = load(f, Loader=UnsafeLoader)
        m = HydraulicModel(model, timeout)
        m.solve_lp()


class MPControl:
    """Connect to bus, run Model Predictive Control."""

    def __init__(self, bus_ip: str | None = '127.0.0.1', bus_port: int = 1324,
                 **kwargs):
        self.busclient = BusClient(bus_ip, bus_port, module='MP Control')
        self.runner = None
        self.connector_kwargs = kwargs

    async def start(self):
        await self.busclient.start()
        self.runner = MPCRunner(**self.connector_kwargs)
        await self.runner.start(self.busclient.rta)
