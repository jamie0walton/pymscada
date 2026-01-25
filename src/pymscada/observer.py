"""Observer."""
import asyncio
from collections.abc import Callable
import time
import logging
import math
from collections import deque
import random
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagInt, TagFloat
from pymscada.kalman_filter import KalmanFilter
from pymscada.misc import interp, bid_period


class Element():
    """Base model element."""

    def __init__(self, p: 'Observer', name: str, element_type: str):
        """Base element with common required attributes."""
        self.name = name
        self.element_type = element_type
        self.p = p
        self.calc_time_us: int = 0

    def initialise(self, time_us: int):
        pass

    def link(self):
        pass

    def follow_step(self, time_us: int):
        pass

    def exception_step(self, tag: TagFloat | TagInt):
        pass

    def sim_step(self, time_us: int):
        pass


class Node(Element):
    """Node element has inflows and outflows."""

    def __init__(self, p: 'Observer', name: str, element_type: str):
        """Nodes collect inflows and outflows with arcs."""
        super().__init__(p, name, element_type)
        self.inflow = 0.0
        self.inflows = []
        self.outflow = 0.0
        self.outflows = []


class Arc(Element):
    """Arc element has source and destination nodes."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 srcnode: str = '', dstnode: str = ''):
        """
        Arcs have a flow that connects to Nodes.
        """
        super().__init__(p, name, element_type)
        self.srcnode = srcnode
        self.dstnode = dstnode

    def link(self):
        if self.srcnode != '':
            self.p.model[self.srcnode].outflows.append(self.name)
        if self.dstnode != '':
            self.p.model[self.dstnode].inflows.append(self.name)


class Ramp(Element):
    """Ramp a setpoint to a target."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 setpoint: float = 0.0, process: float = 0.0, deadband: float = 1.0,
                 control: float = 0.0, control_min: float = 0.0, control_max: float = 100.0,
                 rate_per_sec: float = 0.1):
        super().__init__(p, name, element_type)
        self.setpoint = setpoint
        self.process = process
        self.deadband = deadband
        self.control = control
        self.control_min = control_min
        self.control_max = control_max
        self.rate_per_sec = rate_per_sec

    def sim_step(self, time_us: int):
        error = self.setpoint - self.process
        if error > self.deadband:
            self.control += self.rate_per_sec * self.p.timebase_s
            if self.control > self.control_max:
                self.control = self.control_max
        elif error < -self.deadband:
            self.control -= self.rate_per_sec * self.p.timebase_s
            if self.control < self.control_min:
                self.control = self.control_min
        pass


class Noise(Element):
    """Add noise to a value."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 noisy: float = 0.0, amplitude: float = 0.0, interval: int = 60):
        random.seed(time.time_ns())
        super().__init__(p, name, element_type)
        self.noisy = noisy
        self.amplitude = amplitude
        self.interval = interval
        self._interval = 0

    def sim_step(self, time_us: int):
        self._interval += 1
        if self._interval >= self.interval:
            self._interval = 0
            if self.amplitude > 0.0:
                self.noisy += random.uniform(
                    -self.amplitude, self.amplitude
                )


class BidPeriod(Element):
    """Lookup."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 db: float = 1.0, timedb: int = 300, bidoffer=None):
        super().__init__(p, name, element_type)
        self.db = db
        self.timedb = timedb
        self.bidoffer = bidoffer
        self.dispatch = None
        self.low = None
        self.high = None
        self.lastdispatch = None
        self.last = int(time.time())
        self.lastperiod = bid_period(self.last) - 1
        self.lastbid = None

    def initialise(self, time_us: int):
        if self.bidoffer is not None:
            self.dispatch = self.bidoffer['setpoint'][0]
            self.lastdispatch = self.dispatch
            self.low = self.dispatch - self.db
            self.high = self.dispatch + self.db

    def sim_step(self, time_us: int):
        t = int(time.time())
        period = bid_period(t)
        jitter = 90 * ((period > 24.5) - (period < 24.5))
        nextperiod = bid_period(t + jitter)
        if nextperiod != self.lastperiod:
            self.lastperiod = nextperiod
            if nextperiod == self.bidoffer['period'][0]:
                self.dispatch = self.bidoffer['setpoint'][0]
                logging.warning(f"New dispatch {self.dispatch}")
            elif nextperiod == self.bidoffer['period'][1]:
                self.dispatch = self.bidoffer['setpoint'][1]
                logging.warning(f"New dispatch {self.dispatch}")
            else:
                logging.warning(f"Code error {t} {jitter} {self.bidoffer}")
        # Acceptable generation band calc
        if self.lastdispatch != self.dispatch:
            if t - self.last > self.timedb:
                self.lastdispatch = self.dispatch
        else:
            self.last = t
        self.low = min(self.dispatch - self.db,
                       self.lastdispatch - self.db)
        self.high = max(self.dispatch + self.db,
                        self.lastdispatch + self.db)


class Summing(Node):
    """Sum flows. A single river outflow is required."""

    def __init__(self, p: 'Observer', name: str, element_type: str):
        super().__init__(p, name, element_type)

    def recalc_flow(self, time_us: int):
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
        self.calc_time_us = time_us

    def initialise(self, time_us: int):
        self.recalc_flow(time_us)

    def sim_step(self, time_us: int):
        self.recalc_flow(time_us)

    def follow_step(self, time_us: int):
        self.recalc_flow(time_us)


class Storage(Node):
    """Collect inflows and outflows in storage, represent as level."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
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

    def initialise(self, time_us: int):
        self.recalc_volume()

    def sim_step(self, time_us: int):
        if self.calc_time_us > 0:
            delta_t = (time_us - self.calc_time_us) / 1e6
        else:
            delta_t = self.p.timebase_s
        self.volume += self.netflow * delta_t
        self.calc_time_us = time_us
        self.recalc_level()
        self.recalc_netflow()

    def follow_step(self, time_us: int):
        self.recalc_volume()
        self.calc_time_us = time_us


class StorageRainEst(Node):
    """Collect inflows and outflows in storage, represent as level."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
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
            tb = self.p.timebase_s
            self.F = [[1, tb, tb],
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
            self.level_read_tag.add_callback(self.exception_step, bus_id=0)
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

    def initialise(self, time_us: int):
        self.recalc_volume()
        self.recalc_netflow()
        x0 = [[self.volume],
              [self.netflow],
              [0]]
        self.kf = KalmanFilter(F=self.F, H=self.H, Q=self.Q, R=self.R,
                               P=self.P, x0=x0, alpha=self.alpha)

    def sim_step(self, time_us: int):
        # need to check if this object makes sense as simulation
        if self.calc_time_us > 0:
            delta_t = (time_us - self.calc_time_us) / 1e6
        else:
            delta_t = self.p.timebase_s
        self.volume += self.netflow * delta_t
        self.calc_time_us = time_us
        self.recalc_level()
        self.recalc_netflow()

    def follow_step(self, time_us: int):
        if self._Dt <= 0.0:
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
        self._Dt -= self.p.timebase_s
        self.calc_time_us = time_us

    def exception_step(self, tag):
        if self.level_read_tag is not None and tag is self.level_read_tag:
            if tag.time_us > self.calc_time_us:
                self.level = tag.value
                self.recalc_volume()
                self.calc_time_us = tag.time_us


class Valve(Arc):
    """Ramps to a flow setpoint."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 srcnode: str = '', dstnode: str = '', flow: float = 0.0,
                 flow_read_tag: str = '',
                 setFlow: float = 0.0, rate_per_sec: float = 10.0):
        super().__init__(p, name, element_type, srcnode, dstnode)
        self.flow = flow
        self.setFlow = setFlow
        self.flow_read_tag = None
        if flow_read_tag != '':
            self.flow_read_tag = TagFloat(flow_read_tag)
            self.flow_read_tag.add_callback(self.exception_step, bus_id=0)
        self.rate_per_sec = rate_per_sec
        if self.rate_per_sec == 0.0:
            raise ValueError(f"{self.name} rate_per_sec cannot be zero")

    def sim_step(self, time_us: int):
        if self.flow_read_tag is not None:
            self.flow = self.flow_read_tag.value
            return
        delta_t = (time_us - self.calc_time_us) / 1e6
        if self.flow < self.setFlow:
            self.flow += self.rate_per_sec * delta_t
            if self.flow > self.setFlow:
                self.flow = self.setFlow
        elif self.flow > self.setFlow:
            self.flow -= self.rate_per_sec * delta_t
            if self.flow < self.setFlow:
                self.flow = self.setFlow
        self.calc_time_us = time_us

    def exception_step(self, tag):
        if tag is self.flow_read_tag:
            self.flow = tag.value
        else:
            logging.error(f"Valve: {self.name} got {tag.name}")


class Canal(Arc):
    """Links flow driven by head difference."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 srcnode: str = '', dstnode: str = '', flow: float = 0.0):
        super().__init__(p, name, element_type, srcnode, dstnode)
        self.flow = flow
        self.HQ = []
        self.lag = 0.99
        self.HQ_xs = [x[0] for x in self.HQ]
        self.HQ_ys = [x[1] for x in self.HQ]

    def sim_step(self, time_us: int):
        leveldelta = self.p.model[self.srcnode].level - self.p.model[self.dstnode].level
        drivenflow = interp(leveldelta, self.HQ_xs, self.HQ_ys)
        self.flow = self.flow * self.lag + drivenflow * (1 - self.lag)
        pass


class River(Arc):
    """Create a delay."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 srcnode: str = '', dstnode: str = '',
                 inflow: float = 0.0, outflow: float = 0.0, delay: int = 0,
                 inflow_read_tag: str = '', outflow_write_tag: str = ''):
        super().__init__(p, name, element_type, srcnode, dstnode)
        self.inflow = inflow
        self.outflow = outflow
        self.delay = delay
        self.delayline = deque()
        self.volume = 0.0
        self.volume_calc_time_us = 0
        self.inflow_read_tag = None
        if inflow_read_tag != '':
            self.inflow_read_tag = TagFloat(inflow_read_tag)
            self.inflow_read_tag.add_callback(self.exception_step, bus_id=0)
        self.outflow_write_tag = None
        if outflow_write_tag != '':
            self.outflow_write_tag = TagFloat(outflow_write_tag)

    def initialise(self, time_us: int):
        self.volume_calc_time_us = 0
        if self.inflow < 0:
            self.inflow = 0.0
            logging.error(f"{self.name} inflow < 0, setting to 0")
        num_intervals = math.ceil(self.delay / self.p.timebase_s)
        if self.inflow_read_tag is not None:
            tag = self.inflow_read_tag
            now_sec = int(time.time())
            for i in range(num_intervals):
                sec = now_sec - self.delay + int(i * self.p.timebase_s)
                self.delayline.append(tag.get(sec * 1_000_000))
        if len(self.delayline) == 0:
            for _i in range(num_intervals):
                self.delayline.append(self.inflow)
            self.outflow = self.inflow

    def recalc_flow(self, time_us: int):
        if self.inflow < 0:
            self.inflow = 0.0
            logging.error(f"{self.name} inflow < 0, setting to 0")
        timebase_us = self.p.timebase_s * 1000000
        step_calc_time_us = time_us - time_us % timebase_us
        if step_calc_time_us > self.calc_time_us:
            step_to_end_s = (step_calc_time_us - self.volume_calc_time_us
                             ) / 1e6
            step_in_new_s = (time_us - step_calc_time_us) / 1e6
        else:
            step_to_end_s = (time_us - self.volume_calc_time_us) / 1e6
            step_in_new_s = 0
        self.volume_calc_time_us = time_us
        # apportion the volume of water within the current period
        self.volume += self.inflow * step_to_end_s
        if step_calc_time_us <= self.calc_time_us:
            return
        # add the completed period to the delay line
        self.delayline.append(self.volume / self.p.timebase_s)
        self.outflow = self.delayline.popleft()
        if self.outflow_write_tag is not None:
            self.outflow_write_tag.value = self.outflow
        # apportion the volume of water within the next period
        self.volume = self.inflow * step_in_new_s
        self.calc_time_us = step_calc_time_us

    def sim_step(self, time_us: int):
        self.follow_step(time_us)

    def follow_step(self, time_us: int):
        self.recalc_flow(time_us)

    def exception_step(self, tag):
        if self.inflow_read_tag is not None and tag is self.inflow_read_tag:
            if tag.time_us > self.calc_time_us:
                self.recalc_flow(tag.time_us)
                self.inflow = tag.value

class Generator(Arc):
    """Ramp MW, calculates flow."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 srcnode: str = '', dstnode: str = '', flow: float = 0.0,
                 MW: float = 0.0, setMW: float = 0.0,
                 rate_per_sec: float = 0.1,
                 min: float|None = None, max: float|None = None,
                 nosim: bool = False,
                 K: float = 1.0, bestMW: float = 0.0, maxMW: float = 0.0,
                 SNLflow: float = 0.1, PQ: list = [],
                 MW_read_tag: str = '', flow_write_tag: str = ''):
        super().__init__(p, name, element_type, srcnode, dstnode)
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
        self.rate_per_sec = rate_per_sec
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
            self.MW_read_tag.add_callback(self.exception_step, bus_id=0)
        self.flow_write_tag = None
        if flow_write_tag != '':
            self.flow_write_tag = TagFloat(flow_write_tag)

    def recalc_flow(self):
        """Calculate flow given MW."""
        self.flow = interp(self.MW, self.PQ_xs, self.PQ_ys)

    def initialise(self, time_us: int):
        self.recalc_flow()

    def sim_step(self, time_us: int):
        if self.nosim:
            self.follow_step(time_us)
            return
        if self.MW < self.setMW:
            self.MW += self.rate_per_sec * self.p.timebase_s
            if self.MW > self.setMW:
                self.MW = self.setMW
        elif self.MW > self.setMW:
            self.MW -= self.rate_per_sec * self.p.timebase_s
            if self.MW < self.setMW:
                self.MW = self.setMW
        if self.MW > self.max:
            self.MW = self.max
        elif self.MW < self.min:
            self.MW = self.min
        self.follow_step(time_us)

    def follow_step(self, time_us: int):
        """Calculate flow given MW, keep doing for nosim mode."""
        self.recalc_flow()
        self.calc_time_us = time_us

    def exception_step(self, tag):
        if self.MW_read_tag is not None and tag is self.MW_read_tag:
            if tag.time_us > self.calc_time_us:
                self.MW = tag.value
                self.recalc_flow()
                self.calc_time_us = tag.time_us


class RadialGate(Arc):
    """Opens under water."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 srcnode: str = '', dstnode: str = '', flow: float = 0.0,
                 position: float = 0.0, setposition: float = 10.0,
                 rate_per_sec: float = 0.5,
                 min: float = 0.0, max: float = 100.0, level: float = 0.0,
                 crest: float = 0.0, width: float = 10.0, PO: list = [],
                 position_read_tag: str = '', level_read_tag: str = '',
                 flow_write_tag: str = ''):
        super().__init__(p, name, element_type, srcnode, dstnode)
        self.flow = flow
        self.position = position
        self.setposition = setposition
        self.rate_per_sec = rate_per_sec
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
            self.position_read_tag.add_callback(self.exception_step, bus_id=0)
        self.level_read_tag = None
        if level_read_tag != '':
            self.level_read_tag = TagFloat(level_read_tag)
            self.level_read_tag.add_callback(self.exception_step, bus_id=0)
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

    def initialise(self, time_us: int):
        self.recalc_flow()

    def sim_step(self, time_us: int):
        if self.position < self.setposition:
            self.position += self.rate_per_sec * self.p.timebase_s
            if self.position > self.setposition:
                self.position = self.setposition
        elif self.position > self.setposition:
            self.position -= self.rate_per_sec * self.p.timebase_s
            if self.position < self.setposition:
                self.position = self.setposition
        if self.position > self.max:
            self.position = self.max
        elif self.position < self.min:
            self.position = self.min
        self.follow_step(time_us)

    def follow_step(self, time_us: int):
        self.recalc_flow()
        self.calc_time_us = time_us

    def exception_step(self, tag):
        updated = False
        if self.position_read_tag is not None and tag is self.position_read_tag:
            if tag.time_us > self.calc_time_us:
                self.position = tag.value
                updated = True
        if self.level_read_tag is not None and tag is self.level_read_tag:
            if tag.time_us > self.calc_time_us:
                self.level = tag.value
                updated = True
        if updated:
            self.recalc_flow()
            self.calc_time_us = tag.time_us


class FlapGate(Arc):
    """Opens by lowering the weir crest."""

    def __init__(self, p: 'Observer', name: str, element_type: str,
                 srcnode: str = '', dstnode: str = '', flow: float = 0.0,
                 position: float = 0.0, setposition: float = 10.0,
                 rate_per_sec: float = 0.5,
                 min: float = 0.0, max: float = 100.0, level: float = 0.0,
                 PC: list = [], HQ: list = [],
                 position_read_tag: str = '', level_read_tag: str = '',
                 flow_write_tag: str = ''):
        super().__init__(p, name, element_type, srcnode, dstnode)
        self.flow = flow
        self.position = position
        self.setposition = setposition
        self.rate_per_sec = rate_per_sec
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
            self.position_read_tag.add_callback(self.exception_step, bus_id=0)
        self.level_read_tag = None
        if level_read_tag != '':
            self.level_read_tag = TagFloat(level_read_tag)
            self.level_read_tag.add_callback(self.exception_step, bus_id=0)
        self.flow_write_tag = None
        if flow_write_tag != '':
            self.flow_write_tag = TagFloat(flow_write_tag)

    def recalc_flow(self):
        crest = interp(self.position, self.PC_xs, self.PC_ys)
        if self.level > crest:
            self.flow = interp(self.level - crest, self.HQ_xs, self.HQ_ys)
        else:
            self.flow = 0.0

    def initialise(self, time_us: int):
        self.recalc_flow()

    def sim_step(self, time_us: int):
        if self.position < self.setposition:
            self.position += self.rate_per_sec * self.p.timebase_s
            if self.position > self.setposition:
                self.position = self.setposition
        elif self.position > self.setposition:
            self.position -= self.rate_per_sec * self.p.timebase_s
            if self.position < self.setposition:
                self.position = self.setposition
        if self.position > self.max:
            self.position = self.max
        elif self.position < self.min:
            self.position = self.min
        self.follow_step(time_us)

    def follow_step(self, time_us: int):
        self.recalc_flow()
        self.calc_time_us = time_us

    def exception_step(self, tag):
        updated = False
        if self.position_read_tag is not None and tag is self.position_read_tag:
            if tag.time_us > self.calc_time_us:
                self.position = tag.value
                updated = True
        if self.level_read_tag is not None and tag is self.level_read_tag:
            if tag.time_us > self.calc_time_us:
                self.level = tag.value
                updated = True
        if updated:
            self.recalc_flow()
            self.calc_time_us = tag.time_us


def inclass(*args):
    """Repeat isinstance() for each class, return True if any."""
    test, *clss = args
    for cls in clss:
        if isinstance(test, cls):
            return True
    return False


class Observer():
    """
    Reads node / arc hyraulic model and simulates.

    For an observer more values are fixed, use follow_step.
    For a simulation more values are free, use sim_step.
    """

    def __init__(self, config, timebase_s: int):
        """Just set the main timebase. 1.0 works."""
        self.timebase_s = timebase_s
        self.model = {}
        for e in config['model']:
            self.add_element(e, config['model'][e])
        self.runinit = True

    def add_element(self, name: str, e: dict):
        """Add an element, node or arc to the model."""
        element_by_type = {
            'summing': Summing,
            'storage': Storage,
            'storage_rain_est': StorageRainEst,
            'valve': Valve,
            'canal': Canal,
            'river': River,
            'generator': Generator,
            'radial_gate': RadialGate,
            'flap_gate': FlapGate,
            'ramp': Ramp,
            'noise': Noise,
            'bidperiod': BidPeriod,
        }
        element_type = e.get('element_type')
        if element_type not in element_by_type:
            raise SystemExit(f"{name} does not have a valid type")
        self.model[name] = element_by_type[element_type](p=self, name=name, **e)

    def initialise(self):
        """
        Init each element in the correct order.

        Sets default arc values and connects the arcs to the
        relevant nodes. Simple elements don't connect.
        """
        self.runinit = False
        time_us = int(time.time() * 1e6)
        for e in self.model.values():
            e.link()
        for e in self.model.values():
            if inclass(e, Storage, StorageRainEst):
                e.initialise(time_us)
        for e in self.model.values():
            if inclass(e, Valve, Canal, Generator, RadialGate, FlapGate):
                e.initialise(time_us)
        for e in self.model.values():
            if inclass(e, Summing):
                e.initialise(time_us)
        for e in self.model.values():
            if inclass(e, River):
                e.initialise(time_us)
        for e in self.model.values():
            if inclass(e, Ramp, Noise, BidPeriod):
                e.initialise(time_us)

    def sim_step(self):
        """Simulate the system, setting unknowns."""
        time_us = int(time.time() * 1e6)
        if self.runinit:
            self.initialise()
        # Before flows to set head for head driven flows
        for e in self.model.values():
            if inclass(e, Storage, StorageRainEst):
                e.sim_step(time_us)
        for e in self.model.values():
            if inclass(e, Valve, Canal, Generator, RadialGate, FlapGate):
                e.sim_step(time_us)
        for e in self.model.values():
            if inclass(e, Summing):
                e.sim_step(time_us)
        for e in self.model.values():
            if inclass(e, River):
                e.sim_step(time_us)
        for e in self.model.values():
            if inclass(e, Ramp, Noise, BidPeriod):
                e.sim_step(time_us)

    def follow_step(self):
        """Follow the running system, observing unknowns."""
        time_us = int(time.time() * 1e6)
        if self.runinit:
            self.initialise()
        for e in self.model.values():
            if inclass(e, Valve, Canal, Generator, RadialGate, FlapGate):
                e.follow_step(time_us)
        for e in self.model.values():
            if inclass(e, Summing):
                e.follow_step(time_us)
        for e in self.model.values():
            if inclass(e, River):
                e.follow_step(time_us)
        # After flows, TODO check this.
        for e in self.model.values():
            if inclass(e, Storage, StorageRainEst):
                e.follow_step(time_us)
        for e in self.model.values():
            if inclass(e, Ramp, Noise, BidPeriod):
                e.follow_step(time_us)
