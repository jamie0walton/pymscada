"""Observer."""
from collections import deque
from collections.abc import Callable
import logging
import math
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagInt, TagFloat
from pymscada.kalman_filter import KalmanFilter
from pymscada.misc import interp, ramp
from pymscada.periodic import Periodic


class Element():
    """Base model element."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str):
        """Base element with common required attributes."""
        self.name = name
        self.element_type = element_type
        self.p = p

    def initialise(self):
        pass

    def link(self):
        pass

    def follow_step(self):
        pass

    def tag_callback(self, tag: TagFloat | TagInt):
        pass

    def simulate_step(self):
        pass


class Node(Element):
    """Nodes collect inflows and outflows."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str):
        """Nodes collect inflows and outflows with arcs."""
        super().__init__(p, name, element_type)
        self.inflow = 0.0
        self.inflows = []
        self.outflow = 0.0
        self.outflows = []


class Arc(Element):
    """Arc element has source and destination nodes."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 source: str = '', destination: str = ''):
        """Arcs connect between Elements."""
        super().__init__(p, name, element_type)
        self.source = source
        self.destination = destination

    def link(self):
        if self.source != '':
            self.p.model[self.source].outflows.append(self.name)
        if self.destination != '':
            self.p.model[self.destination].inflows.append(self.name)


class Summing(Node):
    """Sum flows. A single river outflow is required."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str):
        super().__init__(p, name, element_type)

    def recalc_riverdst(self):
        riverdst = None
        inflow = 0.0
        for src in self.inflows:
            if hasattr(self.p.model[src], 'flow'):
                inflow += self.p.model[src].flow
            else:  # must be riverlike
                inflow += self.p.model[src].outflow
        outflow = 0.0
        for dst in self.outflows:
            if hasattr(self.p.model[dst], 'flow'):
                outflow += self.p.model[dst].flow
            else:  # must be the river
                if riverdst is not None:
                    raise ValueError(f"{self.name} only one river permitted")
                riverdst = dst
        if riverdst is None:
            raise ValueError(f"{self.name} one river required")
        else:
            self.p.model[riverdst].inflow = inflow - outflow

    def initialise(self):
        self.recalc_riverdst()

    def follow_step(self):
        self.recalc_riverdst()

    def simulate_step(self):
        self.recalc_riverdst()


class Storage(Node):
    """Collect inflows and outflows in storage, represent as level."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 level: float = 0.0, volume: float = 0.0, LV=None):
        super().__init__(p, name, element_type)
        self.level = level
        self.volume = volume
        self.netflow = 0
        self.LV = LV if LV is not None else []
        self.LV_xs = [x[0] for x in self.LV]
        self.LV_ys = [x[1] for x in self.LV]

    def recalc_level(self):
        self.level = interp(self.volume, self.LV_ys, self.LV_xs)

    def recalc_volume(self):
        self.volume = interp(self.level, self.LV_xs, self.LV_ys)

    def recalc_netflow(self):
        self.inflow = 0.0
        for src in self.inflows:
            if hasattr(self.p.model[src], 'flow'):
                self.inflow += self.p.model[src].flow
            else:  # must be riverlike
                self.inflow += self.p.model[src].outflow
        self.outflow = 0.0
        for dst in self.outflows:
            if hasattr(self.p.model[dst], 'flow'):
                self.outflow += self.p.model[dst].flow
            else:  # must be the one required river
                logging.error(
                    f"{self.name} river {self.p.model[dst].name} not permitted"
                )
        self.netflow = self.inflow - self.outflow

    def initialise(self):
        self.recalc_volume()

    def follow_step(self):
        self.recalc_volume()

    def simulate_step(self):
        self.volume += self.netflow  # 1 sec
        self.recalc_level()
        self.recalc_netflow()


class StorageRainEst(Node):
    """Collect inflows and outflows in storage, represent as level."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 level=0, volume=0, alpha: float = 1.0,
                 Q: list[list[float]]=[[]], R:list[list[float]]=[[]],
                 F=None, H=None, P=None, LV=[],
                 level_read_tag: str = '', rainflow_write_tag: str = ''):
        super().__init__(p, name, element_type)
        self.level = level
        self.volume = volume
        self.netflow = 0
        self.known_flow = None
        self.rainflow = None
        self.Q = Q
        self.R = R
        self.alpha = alpha
        if F is None:
            self.F = [[1, 60, 60],
                      [0, 1, 0],
                      [0, 0, 1]]
        else:
            self.F = F
        if H is None:
            self.H = [[1, 0, 0],
                      [0, 1, 0],
                      [0, 0, 0]]
        else:
            self.H = H
        if P is None:
            self.P = [[1000, 0, 0],
                      [0, 1000, 0],
                      [0, 0, 1000]]
        else:
            self.P = P
        self._Dt = 0
        self.LV = LV
        self.LV_xs = [x[0] for x in self.LV]
        self.LV_ys = [x[1] for x in self.LV]
        self.level_read_tag = None
        if level_read_tag != '':
            self.level_read_tag = TagFloat(level_read_tag)
            self.level_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.rainflow_write_tag = None
        if rainflow_write_tag != '':
            self.rainflow_write_tag = TagFloat(rainflow_write_tag)

    def recalc_level(self):
        self.level = interp(self.volume, self.LV_ys, self.LV_xs)

    def recalc_volume(self):
        self.volume = interp(self.level, self.LV_xs, self.LV_ys)

    def recalc_netflow(self):
        self.inflow = 0.0
        for src in self.inflows:
            if hasattr(self.p.model[src], 'flow'):
                logging.info(f"{self.name} inflow {src} {self.p.model[src].flow:.3f}")
                self.inflow += self.p.model[src].flow
            else:  # must be riverlike
                logging.info(
                    f"{self.name} inflow {src} {self.p.model[src].outflow:.3f}"
                )
                self.inflow += self.p.model[src].outflow
        self.outflow = 0.0
        for dst in self.outflows:
            if hasattr(self.p.model[dst], 'flow'):
                logging.info(f"{self.name} outflow {dst} {self.p.model[dst].flow:.3f}")
                self.outflow += self.p.model[dst].flow
            else:  # must be the one required river
                logging.error(
                    f"{self.name} river {self.p.model[dst].name} not permitted"
                )
        self.netflow = self.inflow - self.outflow

    def initialise(self):
        self.recalc_volume()
        self.recalc_netflow()
        x0 = [[self.volume],
              [self.netflow],
              [0]]
        self.kf = KalmanFilter(F=self.F, H=self.H, Q=self.Q, R=self.R,
                               P=self.P, x0=x0, alpha=self.alpha)

    def follow_step(self):
        if self._Dt <= 0:
            self._Dt = 60
            self.recalc_netflow()
            self.recalc_volume()
            self.kf.predict()
            update = self.kf.update([[self.volume],
                                     [self.netflow],
                                     [0]])
            self.rainflow = update[2][0]
            logging.info(
                f"{self.name} level {self.level:.2f}"
                f" inflow {self.inflow:.3f} outflow {self.outflow:.3f}"
                f" rainflow {self.rainflow:.3f}"
            )
        self._Dt -= 1

    def tag_callback(self, tag):
        if tag is self.level_read_tag:
            self.level = tag.value
            self.recalc_volume()

    def simulate_step(self):
        # need to check if this object makes sense as simulation
        self.volume += self.netflow  # 1 sec
        self.recalc_level()
        self.recalc_netflow()


class Valve(Arc):
    """Ramps to a flow setpoint."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 source: str = '', destination: str = '', flow: float = 0.0,
                 flow_read_tag: str = '',
                 setFlow: float = 0.0, rate: float = 10.0):
        super().__init__(p, name, element_type, source, destination)
        self.flow = flow
        self.setFlow = setFlow
        self.flow_read_tag = None
        if flow_read_tag != '':
            self.flow_read_tag = TagFloat(flow_read_tag)
            self.flow_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.rate = rate
        if self.rate == 0.0:
            raise ValueError(f"{self.name} rate cannot be zero")

    def tag_callback(self, tag):
        if tag is self.flow_read_tag:
            self.flow = tag.value

    def simulate_step(self):
        if self.flow_read_tag is not None:
            self.flow = self.flow_read_tag.value
            return
        self.flow = ramp(self.flow, self.setFlow, self.rate)


class Canal(Arc):
    """Links flow driven by head difference."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 source: str = '', destination: str = '', flow: float = 0.0):
        super().__init__(p, name, element_type, source, destination)
        self.flow = flow
        self.HQ = []
        self.lag = 0.99
        self.HQ_xs = [x[0] for x in self.HQ]
        self.HQ_ys = [x[1] for x in self.HQ]

    def simulate_step(self):
        leveldelta = self.p.model[self.source].level - self.p.model[self.destination].level
        drivenflow = interp(leveldelta, self.HQ_xs, self.HQ_ys)
        self.flow = self.flow * self.lag + drivenflow * (1 - self.lag)
        pass


class River(Arc):
    """Create a delay."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 source: str = '', destination: str = '',
                 inflow: float = 0.0, outflow: float = 0.0, delay: int = 0,
                 inflow_read_tag: str = '', outflow_write_tag: str = ''):
        super().__init__(p, name, element_type, source, destination)
        self.inflow = inflow
        self.outflow = outflow
        self.delay = delay
        self.delayline = deque()
        self.inflow_read_tag = None
        if inflow_read_tag != '':
            self.inflow_read_tag = TagFloat(inflow_read_tag)
            self.inflow_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.outflow_write_tag = None
        if outflow_write_tag != '':
            self.outflow_write_tag = TagFloat(outflow_write_tag)

    def initialise(self):
        if self.inflow < 0:
            self.inflow = 0.0
            logging.error(f"{self.name} inflow < 0, setting to 0")
        self.delay
        if self.inflow_read_tag is not None:
            tag = self.inflow_read_tag
            time_us = int(time.time() * 1e6)
            for i in range(self.delay):
                self.delayline.append(tag.get(time_us - i * 1_000_000))
        else:
            for _i in range(self.delay):
                self.delayline.append(self.inflow)
        self.outflow = self.inflow
        if self.outflow_write_tag is not None:
            self.outflow_write_tag.value = self.outflow

    def recalc_flow(self):
        self.delayline.append(self.inflow)
        self.outflow = self.delayline.popleft()

    def follow_step(self):
        self.recalc_flow()

    def tag_callback(self, tag):
        if tag is self.inflow_read_tag:
            self.inflow = tag.value

    def simulate_step(self):
        self.follow_step()


class Generator(Arc):
    """Ramp MW, calculates flow."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 source: str = '', destination: str = '', flow: float = 0.0,
                 MW: float = 0.0, setMW: float = 0.0, rate: float = 0.1,
                 min: float|None = None, max: float|None = None,
                 nosim: bool = False,
                 K: float = 1.0, bestMW: float = 0.0, maxMW: float = 0.0,
                 SNLflow: float = 0.1, PQ: list = [],
                 MW_read_tag: str = '', flow_write_tag: str = ''):
        super().__init__(p, name, element_type, source, destination)
        self.flow = flow
        if min is None:
            self.min = PQ[0][0]
        else:
            self.min = min
        if max is None:
            self.max = PQ[-1][0]
        else:
            self.max = max
        self.MW = MW
        self.setMW = setMW
        self.rate = rate
        self.K = K
        self.bestMW = bestMW
        self.maxMW = maxMW
        self.SNLflow = SNLflow
        self.PQ = PQ
        self.PQ_xs = [x[0] for x in self.PQ]
        self.PQ_ys = [x[1] for x in self.PQ]
        self.nosim = nosim
        self.MW_read_tag = None
        if MW_read_tag != '':
            self.MW_read_tag = TagFloat(MW_read_tag)
            self.MW_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.flow_write_tag = None
        if flow_write_tag != '':
            self.flow_write_tag = TagFloat(flow_write_tag)

    def recalc_flow(self):
        """Calculate flow given MW."""
        self.flow = interp(self.MW, self.PQ_xs, self.PQ_ys)

    def initialise(self):
        self.recalc_flow()

    def follow_step(self):
        """Calculate flow given MW, keep doing for nosim mode."""
        self.recalc_flow()

    def tag_callback(self, tag):
        if tag is self.MW_read_tag:
            self.MW = tag.value

    def simulate_step(self):
        if self.nosim:
            self.follow_step()
            return
        self.MW = ramp(self.MW, self.setMW, self.rate)
        self.MW = min(self.max, max(self.min, self.MW))
        self.follow_step()


class RadialGate(Arc):
    """Opens under water."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 source: str = '', destination: str = '', flow: float = 0.0,
                 position: float = 0.0, setposition: float = 10.0,
                 rate: float = 0.5,
                 min: float = 0.0, max: float = 100.0, level: float = 0.0,
                 crest: float = 0.0, width: float = 10.0, PO: list = [],
                 position_read_tag: str = '', level_read_tag: str = '',
                 flow_write_tag: str = ''):
        super().__init__(p, name, element_type, source, destination)
        self.flow = flow
        self.position = position
        self.setposition = setposition
        self.rate = rate
        self.min = min
        self.max = max
        self.level = level
        self.crest = crest
        self.width = width
        self.PO = PO
        self.PO_xs = [x[0] for x in self.PO]
        self.PO_ys = [x[1] for x in self.PO]
        self.position_read_tag = None
        if position_read_tag != '':
            self.position_read_tag = TagFloat(position_read_tag)
            self.position_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.level_read_tag = None
        if level_read_tag != '':
            self.level_read_tag = TagFloat(level_read_tag)
            self.level_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.flow_write_tag = None
        if flow_write_tag != '':
            self.flow_write_tag = TagFloat(flow_write_tag)

    def recalc_flow(self):
        opening = interp(self.position, self.PO_xs, self.PO_ys)
        area = self.width * opening
        headtocentre = self.level - (self.crest + opening / 2)
        if headtocentre > 0 and area > 0:
            C = 0.775 - math.log10(area ** 0.7) / headtocentre
            self.flow = C * area * math.sqrt(2 * 9.80665 * headtocentre)
        else:
            self.flow = 0

    def initialise(self):
        self.recalc_flow()

    def follow_step(self):
        self.recalc_flow()

    def tag_callback(self, tag):
        if tag is self.position_read_tag:
            self.position = tag.value
        if tag is self.level_read_tag:
            self.level = tag.value

    def simulate_step(self):
        self.position = ramp(self.position, self.setposition, self.rate)
        self.position = min(self.max, max(self.min, self.position))
        self.follow_step()


class FlapGate(Arc):
    """Opens by lowering the weir crest."""

    def __init__(self, p: 'ObserverModel', name: str, element_type: str,
                 source: str = '', destination: str = '', flow: float = 0.0,
                 position: float = 0.0, setposition: float = 10.0,
                 rate: float = 0.5,
                 min: float = 0.0, max: float = 100.0, level: float = 0.0,
                 PC: list = [], HQ: list = [],
                 position_read_tag: str = '', level_read_tag: str = '',
                 flow_write_tag: str = ''):
        super().__init__(p, name, element_type, source, destination)
        self.flow = flow
        self.position = position
        self.setposition = setposition
        self.rate = rate
        self.min = min
        self.max = max
        self.level = level
        self.PC = PC
        self.HQ = HQ
        self.PC_xs = [x[0] for x in self.PC]
        self.PC_ys = [x[1] for x in self.PC]
        self.HQ_xs = [x[0] for x in self.HQ]
        self.HQ_ys = [x[1] for x in self.HQ]
        self.position_read_tag = None
        if position_read_tag != '':
            self.position_read_tag = TagFloat(position_read_tag)
            self.position_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.level_read_tag = None
        if level_read_tag != '':
            self.level_read_tag = TagFloat(level_read_tag)
            self.level_read_tag.add_callback(self.tag_callback, bus_id=0)
        self.flow_write_tag = None
        if flow_write_tag != '':
            self.flow_write_tag = TagFloat(flow_write_tag)

    def recalc_flow(self):
        crest = interp(self.position, self.PC_xs, self.PC_ys)
        if self.level > crest:
            self.flow = interp(self.level - crest, self.HQ_xs, self.HQ_ys)
        else:
            self.flow = 0.0

    def initialise(self):
        self.recalc_flow()

    def follow_step(self):
        self.recalc_flow()

    def tag_callback(self, tag):
        if tag is self.position_read_tag:
            self.position = tag.value
        elif tag is self.level_read_tag:
            self.level = tag.value

    def simulate_step(self):
        self.position = ramp(self.position, self.setposition, self.rate)
        self.position = min(self.max, max(self.min, self.position))
        self.follow_step()


def inclass(*args):
    """Repeat isinstance() for each class, return True if any."""
    test, *clss = args
    for cls in clss:
        if isinstance(test, cls):
            return True
    return False


class ObserverModel():
    """
    Reads node / arc hyraulic model and simulates.

    For an observer more values are fixed, use follow_step.
    For a simulation more values are free, use simulate_step.
    """

    def __init__(self, model):
        """Just set the main timebase. 1.0 works."""
        self.model = {}
        for e in model:
            self.add_element(e, model[e])
        self.periodic = Periodic(self.periodic_cb, 1.0)

    def add_element(self, name: str, e: dict):
        """Add an element, node or arc to the model."""
        by_type = {
            'summing': Summing,
            'storage': Storage,
            'storage_rain_est': StorageRainEst,
            'valve': Valve,
            'canal': Canal,
            'river': River,
            'generator': Generator,
            'radial_gate': RadialGate,
            'flap_gate': FlapGate
        }
        element_type = e.get('element_type')
        if element_type not in by_type:
            raise SystemExit(f"{name} does not have a valid type")
        self.model[name] = by_type[element_type](p=self, name=name, **e)

    def initialise(self):
        """
        Init each element in the correct order.

        Sets default arc values and connects the arcs to the
        relevant nodes. Simple elements don't connect.
        """
        for e in self.model.values():
            e.link()
        for e in self.model.values():
            if inclass(e, Storage, StorageRainEst):
                e.initialise()
        for e in self.model.values():
            if inclass(e, Valve, Canal, Generator, RadialGate, FlapGate):
                e.initialise()
        for e in self.model.values():
            if inclass(e, Summing):
                e.initialise()
        for e in self.model.values():
            if inclass(e, River):
                e.initialise()

    def follow_step(self):
        """Follow the running system, observing unknowns."""
        for e in self.model.values():
            if inclass(e, Storage, StorageRainEst):
                e.follow_step()
        for e in self.model.values():
            if inclass(e, Valve, Canal, Generator, RadialGate, FlapGate):
                e.follow_step()
        for e in self.model.values():
            if inclass(e, Summing):
                e.follow_step()
        for e in self.model.values():
            if inclass(e, River):
                e.follow_step()

    def simulate_step(self):
        """Simulate the system, setting unknowns."""
        for e in self.model.values():
            if inclass(e, Storage, StorageRainEst):
                e.simulate_step()
        for e in self.model.values():
            if inclass(e, Valve, Canal, Generator, RadialGate, FlapGate):
                e.simulate_step()
        for e in self.model.values():
            if inclass(e, Summing):
                e.simulate_step()
        for e in self.model.values():
            if inclass(e, River):
                e.simulate_step()

    async def periodic_cb(self):
        self.follow_step()

    async def start(self):
        self.initialise()
        await self.periodic.start()


class Observer:
    """Connect to bus on bus_ip:bus_port."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 model: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port.

        Makes connections to Modbus PLCs to read and write data.
        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='Observer')
        self.model = ObserverModel(model)
    
    async def start(self):
        """Provide observer."""
        if self.busclient is not None:
            await self.busclient.start()
        await self.model.start()
