import asyncio
import logging
import time
from copy import deepcopy
from collections.abc import Callable
from struct import unpack
from pymscada import BusClient, TagTyped
from pymscada.milp.model_hyd import HydraulicModel, TimeSeries, State, Constraint
from pymscada.bus_client_tag import TagInt, TagFloat, TagStr, TagDict, TagBytes


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


class MPCRunner:
    def __init__(self, temp_dir: str, log_dir: str, control_tag: str, history_tag: str,
                 solve_time_tag: str, last_solve_tag: str, setpoint_tag: str, result_tag: str,
                 solver_timeout: int, time_step: int, duration: int, history_tags: dict,
                 model: dict) -> None:
        self.temp_dir = temp_dir
        self.log_dir = log_dir
        self.control_tag = TagInt(control_tag)
        self.history_tag = TagBytes(history_tag)
        self.solve_time_tag = TagFloat(solve_time_tag)
        self.last_solve_tag = TagInt(last_solve_tag)
        self.setpoint_tag = TagFloat(setpoint_tag)
        self.result_tag = TagStr(result_tag)
        self.solver_timeout = solver_timeout
        self.time_step = time_step
        self.duration = duration
        self.tags: dict[str, TagFloat] = {}
        self.tag_update: dict[str, dict] = {}
        for tagname, age_s in history_tags.items():
            self.tags[tagname] = TagFloat(tagname)
            self.tags[tagname].age_us = age_s * 1000000
        for tagname in find_matching_key_values('_tag', model):
            self.tags[tagname] = TagFloat(tagname)
        self.model_config = model
        self.model = {}
        self.hydraulic_model = None
        self.saved_model_path = None
        self.site_time = TagInt('_site_time')

    def make_model(self, actual_time: int | None=None):
        """Create the model needed to run Hydraulic Model. If there is a saved path, read
        the saved model and the time parameters needed for the run."""
        self.model['name'] = 'Hydraulic Model'
        if actual_time is None:
            actual_time = int(time.time())
        self.model['actual_time'] = actual_time
        self.model['time_step'] = self.time_step
        self.model['duration'] = self.duration
        self.model['tempdir'] = self.temp_dir
        self.model['model'] = {}
        c = self.model_config
        m = self.model['model']
        for node in c:
            m[node] = {}
            for k, v in c[node].items():
                if k == 'state':
                    if v == 'OFF':
                        v = State.OFF
                    elif v == 'FIXED':
                        v = State.FIXED
                    elif v == 'FREE':
                        v = State.FREE
                    else:
                        logging.error(f"Invalid state: {v}")
                        raise ValueError(f"Invalid state: {v}")
                elif '_read_tag' in k:
                    k = k.strip('_read_tag')
                    v = self.tags[v].value
                elif k == 'time_series_tag':
                    k = 'time_series'
                    logging.info(f"tag: {self.tags[v].name} value: {self.tags[v].value}")
                    v = TimeSeries(self.tags[v].value)
                m[node][k] = v
        self.hydraulic_model = HydraulicModel(self.model)

    def process_model_output(self):
        """Process the output of the model."""
        pass

    def run_model(self):
        """Save the config, run the model, save the output, process the output, write
        the output to the bus if this is a real-time run (don't write for saved path runs)."""

    def control_tag_callback(self, tag: TagInt):
        """Callback for the control tag."""
        pass

    def setpoint_callback(self, tag: TagFloat):
        """Callback for the setpoint tag."""
        pass

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
            # packed with self.rta.value = pack('>HHH', rta_id, tagid, packtype) + data
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
            for time_us, value in data:
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

    async def periodic(self):
        """Subject to state, trigger run every 10 minutes at :00:30, :10:30, :20:30, etc."""
        pass

    async def start(self, rta: Callable):
        """Start the MPCRunner."""
        await self.fill_history(rta)
        pass


class MPControl:
    """Connect to bus, run Model Predictive Control."""

    def __init__(self, bus_ip: str | None = '127.0.0.1', bus_port: int = 1324,
                 **kwargs) -> None:
        self.busclient = BusClient(bus_ip, bus_port, module='MP Control')
        self.runner = None
        self.connector_kwargs = kwargs


    async def start(self):
        await self.busclient.start()
        self.runner = MPCRunner(**self.connector_kwargs)
        await self.runner.start(self.busclient.rta)
