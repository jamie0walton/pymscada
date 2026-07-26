# This file is copied in from another project, it uses the pymscada library but is not part of the pymscada library itself.
"""Site Code."""
import asyncio
import copy
import logging
import socket
from datetime import datetime
import time
from misc import bid_period, bid_time, interp
from pymscada import BusClient, Periodic, TagTyped, TagFloat, TagInt, \
                     TagDict, TagStr

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(f'%(levelname)s sitecode %(message)s')
handler.setFormatter(formatter)
logger.handlers.clear()  # Remove any existing handlers
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# MultiSelect:
#   desc: Select Dict Multi
#   type: dict
#   init:
#     labels: [A, B, C, D, E, F, G, H]
#     values: [0, 1, 2, 3, 3, 4, 4, 3]
#     locks: [1, 0, 0, 0, 0, 0, 0, 1]
# FloatSelect:
#   desc: Select Dict Float
#   type: dict
#   init:
#     labels: [Floats, For, This, Tag]
#     values: [0.1, 0.1, 0.2, 0.3]
#     locks: [0, 1, 0, 0]

OK = 1
NOT_OPTIMUM = 2
INVALID = 3
FAILED = 4

TRANSPOWER = 0
LOCAL = 1

STOP = 0       # _mpc_control multi-state values
TIMED_RUN = 1
RUNNING = 2
RUN_NOW = 3

READ_ONLY = 0
ACKA_MANUAL = 1
ACKQ_QUERY = 2
AUTOMATIC = 3

DONE = 0
COPY_STATION_TO_WITS = 1
SPREAD_WITS = 2
SPREAD_GEN = 3

FREE = 0
G1_LEAD = 1
G2_LEAD = 2
FORCE_G1_LEAD = 0
FORCE_G2_LEAD = 1

KI = 4
LAKE_MIN = 146.613
LAKE_MAX = 146.787
DISPATCH_BAND = 0.9
MAX_GEN = 24.6
GEN_Q = [0, 22.2, 29.0, 38.9]
GEN_P = [0, 6.8, 10.0, 12.8]

# TODO for testing
BID_LOCK = 2


def sec_to_hhmm(seconds):
    """Return an integer in hours and minutes given time in UTC."""
    time_struct = time.localtime(seconds)
    return time_struct.tm_hour * 100 + time_struct.tm_min


def wits_offset_bid(wits_set: float, lake_set: float,
                    min_bid: float, max_bid: float) -> float:
    """Offset the bid by the lake set."""
    offset = 10 * (lake_set - 146.6) - 1  # 146.6 to 146.8 to -1 to 1
    offset_lim = min(max(offset, -0.9), 0.9)
    wits_offset = wits_set + offset_lim
    wits_offset_lim = min(max(wits_offset, min_bid + 0.9), max_bid - 0.9)
    if wits_offset_lim > 12.8 and wits_offset_lim < 14:
        if wits_offset_lim < 13.2:
            wits_offset_lim = 13.2
        elif wits_offset_lim > 13.4:
            wits_offset_lim = 13.4
        else:
            wits_offset_lim = 13.3
    wits_offset_round = round(wits_offset_lim, 2)
    return wits_offset_round


class Tags:
    """namespace for tags."""

    def __init__(self):
        """add the tags"""
        # Dict tags
        self.wits_plan = TagDict('WITS_plan')
        self.g1_plan = TagDict('G1_plan')
        self.g2_plan = TagDict('G2_plan')
        self.stn_plan = TagDict('Stn_plan')
        self.outage_plan = TagDict('Outage_plan')
        self.lake_plan = TagDict('Lake_plan')
        self.mpc_result = TagDict('_mpc_result')
        # Int tags
        self.mpc_control = TagInt('_mpc_control')
        self.tds_control = TagInt('_tds_control')
        self.dispatch_source = TagInt('dispatch_source')
        self.lead = TagInt('SI_Lead')
        self.mpc_solve_period = TagInt('_mpc_solve_period')
        self.mpc_status = TagInt('_mpc_status')
        self.bid_tool = TagInt('_bid_tool')
        self.site_time = TagInt('_site_time')
        self.HHMM = TagInt('SO_HHMM')
        self.HHMM.deadband = 1
        self.set_lead = TagInt('SO_setLead')
        self.StnTimeN0 = TagInt('SO_StnTimeN0')
        self.StnTimeN1 = TagInt('SO_StnTimeN1')
        self.StnTimeN2 = TagInt('SO_StnTimeN2')
        self.StnTimeN3 = TagInt('SO_StnTimeN3')
        # Float tags
        self.bid_MW = TagFloat('SO_Station_BidMW')
        self.tp_setMW = TagFloat('I_Transpower_setMW')
        self.tp_setMVAR = TagFloat('I_Transpower_setMVAR')
        self.dispatch_setMW = TagFloat('dispatch_setMW')
        self.stn_setMW = TagFloat('SO_Generation_setMW')
        self.g1_setMW = TagFloat('SO_G1_setMW')
        self.g2_setMW = TagFloat('SO_G2_setMW')
        self.g1_MW = TagFloat('I_Aniwhenua_G1_MW')
        self.g2_MW = TagFloat('I_Aniwhenua_G2_MW')
        self.barrage_setflow = TagFloat('SO_Barrage_setflow')
        self.stream_flow = TagFloat('I_Lower_Stream_Flow')
        self.bypass_flow = TagFloat('SI_Barrage_Bypass')
        self.lake_inflow = TagFloat('SO_Lake_Aniwhenua_Inflow')
        # self.lake_inflow.age_us = 28800000000
        # self.lake_inflow_mean = TagFloat('SO_Lake_Aniwhenua_Inflow_Mean')
        self.op_min_day = TagFloat('I_Min_Override_Day')
        self.op_min_night = TagFloat('I_Min_Override_Night')
        self.min_flow_day = TagFloat('SO_Min_Controlled_Flow_Day')
        self.min_flow_night = TagFloat('SO_Min_Controlled_Flow_Night')
        self.lake_level = TagFloat('I_Lake_Aniwhenua_level')
        self.barrage_flow = TagFloat('SO_Barrage_flow')
        self.g1_scr_loss = TagFloat('I_Aniwhenua_G1_ScreenLoss')
        self.g2_scr_loss = TagFloat('I_Aniwhenua_G2_ScreenLoss')
        self.StnMwN0 = TagFloat('SO_StnMwN0')
        self.StnMwN1 = TagFloat('SO_StnMwN1')
        self.StnMwN2 = TagFloat('SO_StnMwN2')
        self.StnMwN3 = TagFloat('SO_StnMwN3')
        # MPC tags set from mpc_result
        self.mpc_bid_offer = TagFloat('mpc_Bid_Offer')
        self.mpc_station_power = TagFloat('mpc_Station_Power')
        self.mpc_revenue = TagFloat('mpc_Revenue')
        self.mpc_galatea_inflow = TagFloat('mpc_Galatea_Inflow')
        self.mpc_rain_inflow = TagFloat('mpc_Rain_Inflow')
        self.mpc_lake_level = TagFloat('mpc_Lake_Level')
        self.mpc_g1_power = TagFloat('mpc_G1_Power')
        self.mpc_g2_power = TagFloat('mpc_G2_Power')
        self.mpc_barrage_flow = TagFloat('mpc_Barrage_Flow')
        # String tags
        self.sms_info = TagStr('sms_info')
        # Fix some values
        if False:  # TODO fix this hack for when starting and values are None
            self.wits_plan.value = {}
            self.g1_plan.value = {}
            self.g2_plan.value = {}
            self.stn_plan.value = {}
            self.outage_plan.value = {}
            self.lake_plan.value = {}
        self.tp_setMVAR.value = 0
        self.mpc_result.value = {'desc': 'init ...'}
        self.sms_info.value = 'init ...'
        self.mpc_bid_offer.value = 0.0
        self.mpc_station_power.value = 0.0
        self.mpc_revenue.value = 0.0
        self.mpc_galatea_inflow.value = 0.0
        self.mpc_rain_inflow.value = 0.0
        self.mpc_lake_level.value = 0.0
        self.mpc_g1_power.value = 0.0
        self.mpc_g2_power.value = 0.0
        self.mpc_barrage_flow.value = 0.0
        self.bid_tool.value = DONE
        # Create a list, is this safe?
        self.tags: list[TagTyped] = list(vars(self).values())
    
    async def all_ready(self):
        """return when everything has a value"""
        while True:
            await asyncio.sleep(0.2)
            return
            done = True
            for tag in self.tags:
                if tag.is_none:
                    logging.info(f"{tag.name} value is None")
                    done = False
            if done:
                return


def valid_plan(plan: dict):
    """Validate the plan."""
    try:
        assert all(x in plan for x in ['times', 'labels', 'values', 'locks'])
        length = len(plan['times'])
        assert 46 <= length <= 50
        assert length == len(plan['labels'])
        assert length == len(plan['values'])
        assert length == len(plan['locks'])
        assert all(isinstance(x, int) for x in plan['times'])
        assert all(isinstance(x, str) for x in plan['labels'])
        assert all(isinstance(x, (int, float)) for x in plan['values'])
        assert all(isinstance(x, int) for x in plan['locks'])
    except (TypeError, AssertionError) as e:
        logging.critical(f"invalid structure: {e}")
        return False
    return True


def label(period: int, time: int):
    """Create a label for a period and time."""
    dt = datetime.fromtimestamp(time)
    return f"{dt.hour:02}:{dt.minute:02} {period:2}"


def times_periods(now: int):
    """Return the times and labels for the plan."""
    period0 = bid_period(now)
    time0 = bid_time(now, period0)
    times = [time0]
    periods = [period0]
    for i in range(1, 51):
        pt = time0 + i * 1800
        period = bid_period(pt)
        if period == period0:
            break
        times.append(pt)
        periods.append(period)
    return times, periods


def no_of_periods(time_s: int):
    d = datetime.fromtimestamp(time_s)
    d0 = int(time.mktime((d.year, d.month, d.day,
                         0, 0, 0, 0, 0, -1)))
    d1 = int(time.mktime((d.year, d.month, d.day + 1,
                         0, 0, 0, 0, 0, -1)))
    return int((d1 - d0) / 1800)


def default_plan(plan_tag: TagDict, tags: Tags, locked: int, now: int):
    """Create a default plan based on present generation and modes."""
    if plan_tag.name == 'WITS_plan':
        setpoint = tags.g1_MW.value + tags.g2_MW.value
    elif plan_tag.name == 'Stn_plan':
        setpoint = tags.g1_MW.value + tags.g2_MW.value
    elif plan_tag.name == 'G1_plan':
        setpoint = tags.g1_MW.value
    elif plan_tag.name == 'G2_plan':
        setpoint = tags.g2_MW.value
    elif plan_tag.name == 'Lake_plan':
        setpoint = tags.lake_level.value
    elif plan_tag.name == 'Outage_plan':
        setpoint = FORCE_G1_LEAD
    else:
        raise ValueError(f"default_plan {plan_tag.name} not found")
    setpoint = round(setpoint, 2)
    times, periods = times_periods(now)
    values = [setpoint] * len(times)
    locks = [1 if i < locked else 0 for i in range(len(times))]
    labels = [label(x, y) for x, y in zip(periods, times)]
    return {'times': times, 'labels': labels, 'values': values, 'locks': locks}


def step_plan(plan: dict, locked: int):
    """
    Rotate the plan to the next period determined by the clock.

    The period is not rotated. period0 sets the first period.
    values are rotated with rules for the 2am-3am DST move.
    locks are not rotated, they are recalculated.
    """
    time_n = plan['times'][-1] + 1800
    period_0 = bid_period(plan['times'][1])
    periods_0 = no_of_periods(plan['times'][0])
    periods_n = no_of_periods(time_n)
    # increment starting period according to DST transitions
    times = plan['times'][1:]
    values = plan['values'][1:]
    # append times and values per DST to keep a single instance of all periods
    # inserting copies for longer days, deleting for shorter days as required
    if periods_n == 48 and periods_0 == 48:
        times.append(time_n)
        values.append(plan['values'][0])
    elif periods_n == 50 and periods_0 == 48:
        if period_0 == 8:
            times.extend([time_n, time_n + 1800, time_n + 3600])
            values.extend([values[-1], values[-1], plan['values'][0]])
        else:
            times.append(time_n)
            values.append(plan['values'][0])
    elif periods_n == 48 and periods_0 == 50:
        if period_0 in [7, 8]:
            pass
        else:
            times.append(time_n)
            values.append(plan['values'][0])
    elif periods_n == 46 and periods_0 == 48:
        if period_0 in [6, 7]:
            pass
        else:
            times.append(time_n)
            values.append(plan['values'][0])
    elif periods_n == 48 and periods_0 == 46:
        if period_0 == 6:
            times.extend([time_n, time_n + 1800, time_n + 3600])
            values.extend([values[-1], values[-1], plan['values'][0]])
        else:
            times.append(time_n)
            values.append(plan['values'][0])
    # calculate the new plan locks
    labels = [label(bid_period(t), t) for t in times]
    locks = [1 if i < locked else 0 for i in range(len(times))]
    # logging.warning(f"rotate_plan {i:2} {periods_n} {periods_0} {labels[0]} {values}")
    return {'times': times, 'labels': labels, 'values': values, 'locks': locks}


def fix_locks(plan: dict, locked: int, len_times: int):
    """Fix the locks for the plan."""
    plan['locks'] = [1 if i < locked else 0 for i in range(len_times)]


def rotate_plan(plan_tag: TagDict, tags: dict, locked: int, now: int):
    """
    Rotate the plan to the next period determined by the clock.
    Step as many times as needed.
    """
    if not valid_plan(plan_tag.value):
        return default_plan(plan_tag, tags, locked, now)
    work = copy.deepcopy(plan_tag.value)
    while True:
        if work['times'][0] <= now - 1800:
            work = step_plan(work, locked)
        else:
            fix_locks(work, locked, len(work['times']))
            break
    return work


def standardise_plan(plan_tag: TagDict, tags: Tags):
    """Whereever we are at, clean the plan to a nice form."""
    locked = 99  # everything locked
    if plan_tag is tags.outage_plan and tags.lead == FREE:
        locked = 0
    if tags.mpc_control.value == STOP:
        if plan_tag in [tags.wits_plan]:
            locked = BID_LOCK
        elif plan_tag in [tags.g1_plan, tags.g2_plan]:
            locked = 0
    now = int(time.time())
    new_plan = rotate_plan(plan_tag, tags, locked, now)
    logging.info(f"{plan_tag.name} {new_plan['labels'][:3]} {new_plan['values'][:3]}"
                 f" {new_plan['locks'][:3]}")
    plan_tag.value = new_plan


class GenControl:
    # do not use tags in this class

    def __init__(self, dispatch_mw: float, source: int):
        self.min_gen = 10
        self.g1_setMW = None
        self.g2_setMW = None
        self.dispatch_mw = dispatch_mw
        self.source = source
        self.time_set = 0
        self.time_p1 = 0
        self.level_set = 146.7
        self.level_p1 = 146.7
        self.g1_set = 7
        self.g2_set = 7
        self.g1_set_p1 = 7
        self.g2_set_p1 = 7
        self.adjust = 0.0
        self.g1_mw = TagFloat('I_Aniwhenua_G1_MW')
        self.g2_mw = TagFloat('I_Aniwhenua_G2_MW')

    def solver_result(self, result: dict):
        self.time_set = result['set_time']
        times = sorted([int(x) for x in result['results']['G1'].keys()])
        set_idx = times.index(self.time_set)
        self.time_p1 = times[set_idx + 1]
        self.level_set = result['results']['Lake_Aniwhenua'][
            str(self.time_set)]
        self.level_p1 = result['results']['Lake_Aniwhenua'][str(self.time_p1)]
        self.g1_set = result['results']['G1'][str(self.time_set)]
        self.g2_set = result['results']['G2'][str(self.time_set)]
        self.g1_set_p1 = result['results']['G1'][str(self.time_p1)]
        self.g2_set_p1 = result['results']['G2'][str(self.time_p1)]
        self.g1_setMW = self.g1_set
        self.g2_setMW = self.g2_set
        self.fast_dispatch = False
        logging.info(f"Solver result: {self.time_set} {self.time_p1} {self.level_set} {self.level_p1} "
                     f"G1 G2 {self.g1_set} {self.g2_set} +1 {self.g1_set_p1} {self.g2_set_p1}")

    def dispatch(self, dispatch_mw: float, source: int):
        """Immediate fast response to dispatch, print only."""
        now = int(time.time())
        self.dispatch_mw = dispatch_mw
        self.source = source
        g1_mw = self.g1_mw.value
        g2_mw = self.g2_mw.value
        g1_mw_set = self.g1_set_p1
        g2_mw_set = self.g2_set_p1
        g1_mw_p1 = self.g1_set_p1
        g2_mw_p1 = self.g2_set_p1
        logging.info(f"Act: {g1_mw:.1f} {g2_mw:.1f} Set: {g1_mw_set:.1f} "
                     f"{g2_mw_set:.1f} +1 {g1_mw_p1:.1f} {g2_mw_p1:.1f} "
                     f"TP:{dispatch_mw:0.1f} {now} {self.time_set} "
                     f"{self.time_p1}")

    def manual_step(self, now: int, g1_plan: dict, g2_plan: dict):
        self.adjust = 0.0
        for i, t in enumerate(g1_plan['times']):
            if now >= t:
                self.g1_setMW = g1_plan['values'][i]
                self.g2_setMW = g2_plan['values'][i]
                break

    def step(self, now: int, lake_level: float):
        if self.g1_setMW is None or self.g2_setMW is None:
            return
        time_frac = (now - self.time_set) / (self.time_p1 - self.time_set)
        level_frac = (self.level_p1 - self.level_set) * time_frac
        expected = max(LAKE_MIN, min(LAKE_MAX, self.level_set + level_frac))
        level_error = lake_level - expected
        if self.source == TRANSPOWER:
            allowed_deviation = DISPATCH_BAND
        else:
            allowed_deviation = 2
        min_gen = self.dispatch_mw - allowed_deviation
        if min_gen < self.min_gen:
            min_gen = min(self.dispatch_mw, self.min_gen)
            logging.warning(f"limited gen {self.dispatch_mw} {self.min_gen}")
        max_gen = self.dispatch_mw + allowed_deviation
        expected_gen = self.g1_set + self.g2_set
        self.adjust = max(min_gen, min(max_gen,
            expected_gen + self.adjust + level_error * KI)) - expected_gen
        if self.g1_set > 1 and self.g2_set > 1:
            self.g1_setMW = max(7, min(12.8, self.g1_set + self.adjust / 2))
            self.g2_setMW = max(7, min(12.8, self.g2_set + self.adjust / 2))
        elif self.g1_set < 1 and self.g2_set > 1:
            self.g1_setMW = 0
            self.g2_setMW = max(7, min(12.8, self.g2_set + self.adjust))
        elif self.g1_set > 1 and self.g2_set < 1:
            self.g1_setMW = max(7, min(12.8, self.g1_set + self.adjust))
            self.g2_setMW = 0
        else:
            self.g1_setMW = 0
            self.g2_setMW = 0
        logging.info(f"Gen Ctl: act:{lake_level:0.3f} exp:{expected:0.3f} "
                     f"TP: {self.dispatch_mw:0.1f} "
                     f"Stn: {self.g1_setMW + self.g2_setMW:0.2f} "
                     f"{self.g1_set:0.2f}->{self.g1_setMW:0.2f} "
                     f"{self.g2_set:0.2f}->{self.g2_setMW:0.2f}")


class SiteLogic:
    """Manage the G1, G2, Outage, Station and bid plans."""

    def __init__(self, tags: Tags):
        """Initialize plans and set up callbacks."""
        self.min_gen = 7
        self.tags = tags
        self.gen_control = GenControl(self.tags.tp_setMW.value, TRANSPOWER)
        self.tags.lead.add_callback(self.on_lead_lag_change)
        self.tags.mpc_control.add_callback(self.on_mpc_control_change)
        self.tags.dispatch_source.add_callback(self.on_source_change)
        self.tags.tp_setMW.add_callback(self.on_tp_setMW_change)
        self.tags.mpc_result.add_callback(self.on_mpc_result_change)
        self.tags.g1_plan.add_callback(self.on_gen_plan_change)
        self.tags.g2_plan.add_callback(self.on_gen_plan_change)
        self.tags.wits_plan.add_callback(self.on_wits_plan_change)
        self.tags.bid_tool.add_callback(self.on_bid_tool_change)
        # Add callbacks for plan changes
        self.plans = [self.tags.g1_plan, self.tags.g2_plan,
            self.tags.wits_plan, self.tags.stn_plan, self.tags.outage_plan,
            self.tags.lake_plan]
        self.last_period = -1
        # Initialize all plans with default structure
        for plan in self.plans:
            standardise_plan(plan, self.tags)
        self.periodic = Periodic(self.poll, 1.0)

    def on_lead_lag_change(self, tag):
        """Callback when the lead generator changes."""
        if tag.value == FREE:
            return
        outage_pv = copy.deepcopy(self.tags.outage_plan.value)
        if tag.value == G1_LEAD:
            setpoint = FORCE_G1_LEAD
        elif tag.value == G2_LEAD:
            setpoint = FORCE_G2_LEAD
        for i in range(len(outage_pv['values'])):
            outage_pv['values'][i] = setpoint
        self.tags.outage_plan.value = outage_pv

    def on_mpc_control_change(self, tag):
        """Callback when the MPC control changes."""
        for plan in self.plans:
            standardise_plan(plan, self.tags)

    def on_source_change(self, tag):
        if tag.value == TRANSPOWER:
            logging.warning(f"Changed to Transpower src: {tag.value}")
            self.tags.dispatch_setMW.value = self.tags.tp_setMW.value
            self.gen_control.dispatch(self.tags.tp_setMW.value, TRANSPOWER)
        else:  # LOCAL
            logging.error("Not implemented")

    def on_tp_setMW_change(self, tag):
        """Callback when the Transpower setMW changes."""
        if self.tags.dispatch_source.value == TRANSPOWER:
            logging.warning(f"Transpower dispatch: {tag.value}")
            self.tags.dispatch_setMW.value = tag.value
            self.gen_control.dispatch(tag.value, TRANSPOWER)
        else:  # LOCAL
            logging.warning(f"Local but got Transpower dispatch: {tag.value}")

    def min_gen_calc(self, now: int):
        """Calculate the minimum and maximum generation limits."""
        min_flow_day = self.tags.min_flow_day.value
        min_flow_night = self.tags.min_flow_night.value
        min_gen_day = interp(min_flow_day, GEN_Q, GEN_P)
        min_gen_night = interp(min_flow_night, GEN_Q, GEN_P)
        tod = time.localtime(now)
        min_gen = min_gen_day
        if tod.tm_hour < 7 or tod.tm_hour >= 19:
            min_gen = min_gen_night
        return min_gen

    def on_mpc_result_change(self, tag):
        """Callback when the MPC result changes."""
        results = tag.value
        if not results['found']:
            return
        self.gen_control.solver_result(results)
        start_time = results['actual_time']
        solve_result = results['results']
        for mpc_tag, key in [
            (self.tags.mpc_station_power, 'Station_Power'),
            (self.tags.mpc_revenue, 'GXP'),
            (self.tags.mpc_galatea_inflow, 'Upper'),
            (self.tags.mpc_rain_inflow, 'Rainflow'),
            (self.tags.mpc_lake_level, 'Lake_Aniwhenua'),
            (self.tags.mpc_g1_power, 'G1'),
            (self.tags.mpc_g2_power, 'G2'),
            (self.tags.mpc_barrage_flow, 'Barrage'),
        ]:
            times = sorted([int(x) for x in solve_result[key].keys()])
            for t in times:
                if t >= start_time:
                    v = solve_result[key][str(t)]
                    if key == 'Lake_Aniwhenua':
                        v = int((v - 146) * 1000)
                    mpc_tag.set_value(v, int(t * 1e6))
        for plan_tag in self.plans:
            standardise_plan(plan_tag, self.tags)
        wits_pv = copy.deepcopy(self.tags.wits_plan.value)
        stn_pv = copy.deepcopy(self.tags.stn_plan.value)
        g1_pv = copy.deepcopy(self.tags.g1_plan.value)
        g2_pv = copy.deepcopy(self.tags.g2_plan.value)
        lake_pv = copy.deepcopy(self.tags.lake_plan.value)
        times = {}
        for i,t in enumerate(wits_pv['times']):
            str_t = str(t)
            if str_t in solve_result['Station_Power']:
                times[str_t] = i
        for str_t, i in times.items():
            g1_set = solve_result['G1'][str_t]
            g2_set = solve_result['G2'][str_t]
            lake_set = solve_result['Lake_Aniwhenua'][str_t]
            stn_set = solve_result['Station_Power'][str_t]
            min_gen = self.min_gen_calc(t)
            wits_set = wits_offset_bid(stn_set, lake_set, min_gen, MAX_GEN)
            # TODO look at this more closely - this edits locked period.
            if i > 2:
                wits_pv['values'][i] = wits_set
            stn_pv['values'][i] = stn_set
            g1_pv['values'][i] = g1_set
            g2_pv['values'][i] = g2_set
            lake_pv['values'][i] = lake_set
        for v, t in zip(wits_pv['values'], wits_pv['times']):
            self.tags.mpc_bid_offer.set_value(v, int(t * 1e6))
        for plan_tag, value in [
            (self.tags.wits_plan, wits_pv),
            (self.tags.stn_plan, stn_pv),
            (self.tags.g1_plan, g1_pv),
            (self.tags.g2_plan, g2_pv),
            (self.tags.lake_plan, lake_pv),
        ]:
            plan_tag.value = value
        self.tags.bid_MW.value = wits_pv['values'][0]

    def on_gen_plan_change(self, tag):
        """Callback when the generation plan changes."""
        if self.tags.mpc_control.value != STOP:
            return
        g1_pv = copy.deepcopy(self.tags.g1_plan.value)
        g2_pv = copy.deepcopy(self.tags.g2_plan.value)
        stn_pv = copy.deepcopy(self.tags.stn_plan.value)
        for i in range(len(stn_pv['values'])):
            stn_pv['values'][i] = g1_pv['values'][i] + g2_pv['values'][i]
        self.tags.stn_plan.value = stn_pv

    def on_wits_plan_change(self, tag):
        """Callback when the WITS plan changes."""
        if self.tags.dispatch_source.value == LOCAL:
            self.tags.bid_MW.value = 0
        else:  # TRANSPOWER
            self.tags.bid_MW.value = tag.value['values'][0]

    def on_bid_tool_change(self, tag):
        """Callback when the bid tool changes."""
        if tag.value == DONE:
            return
        wits_pv = copy.deepcopy(self.tags.wits_plan.value)
        stn_pv = copy.deepcopy(self.tags.stn_plan.value)
        if tag.value == COPY_STATION_TO_WITS:
            for i in range(len(wits_pv['values'])):
                wits_pv['values'][i] = stn_pv['values'][i]
            self.tags.wits_plan.value = wits_pv

    # def mean_flow_calcs(self, now: int):
    #     """Calculate the mean flow."""
    #     lake_inflow_tag = self.tags.lake_inflow
    #     flows = []
    #     for i in range(0, 28800, 600):
    #         flows.append(lake_inflow_tag.get(int((now - 600) * 1e6)))
    #     mean_flow = sum(flows) / len(flows)
    #     self.tags.lake_inflow_mean.value = mean_flow

    def min_flow_calcs(self, now: int):
        """Calculate the minimum flow limits."""
        bypass_flow = self.tags.bypass_flow.value
        if bypass_flow is None:
            bypass_flow = 0.0
        stream_flow = self.tags.stream_flow.value
        if stream_flow is None:
            stream_flow = 0.0
        falls_flow = bypass_flow + stream_flow
        lake_inflow = self.tags.lake_inflow.value
        if lake_inflow is None:
            lake_inflow = 32.0 / 0.4
        if lake_inflow >= 32.0:
            min_flow_day = 32.0 - falls_flow
            min_flow_night = 0.4 * lake_inflow - falls_flow
        else:
            min_flow_day = lake_inflow - falls_flow
            min_flow_night = 0.3 * lake_inflow - falls_flow
        op_min_day = self.tags.op_min_day.value
        op_min_night = self.tags.op_min_night.value
        if min_flow_day > op_min_day:
            min_flow_day = op_min_day
        if min_flow_night > op_min_night:
            min_flow_night = op_min_night
        self.tags.min_flow_day.value = min_flow_day
        self.tags.min_flow_night.value = min_flow_night

    def update_gen_control(self, now: int):
        gc = self.gen_control
        gc.min_gen = self.min_gen_calc(now)
        g1_tag = self.tags.g1_setMW
        g2_tag = self.tags.g2_setMW
        stn_tag = self.tags.stn_setMW
        lake_tag = self.tags.lake_level
        mp_control = self.tags.mpc_control.value
        if mp_control == STOP:
            gc.manual_step(now, self.tags.g1_plan.value, self.tags.g2_plan.value)
        else:
            gc.step(now, lake_tag.value)
        if gc.g1_setMW is not None and abs(gc.g1_setMW - g1_tag.value) > 0.02:
            g1_tag.value = gc.g1_setMW
        if gc.g2_setMW is not None and abs(gc.g2_setMW - g2_tag.value) > 0.02:
            g2_tag.value = gc.g2_setMW
        if gc.g1_setMW is not None and gc.g2_setMW is not None:
            stn_setMW = gc.g1_setMW + gc.g2_setMW
            if abs(stn_setMW - stn_tag.value) > 0.02:
                stn_tag.value = stn_setMW

    async def poll(self):
        """
        Called periodically to update plans based on current time.
        Rotates plans at the start of each bid period.
        """
        now = int(time.time())
        self.tags.HHMM.value = sec_to_hhmm(now)
        self.tags.site_time.value = now * 1000000
        if self.tags.bid_tool.value != DONE:
            self.tags.bid_tool.value = DONE
        self.min_flow_calcs(now)
        current_period = bid_period(now)
        if self.last_period != current_period:
            logging.info(f"Bid period changed from {self.last_period} to {current_period}")
            # Rotate all plans for the new period
            for plan_tag in self.plans:
                standardise_plan(plan_tag, self.tags)
            wits_pv = self.tags.wits_plan.value
            self.tags.bid_MW.value = wits_pv['values'][0]
            self.last_period = current_period
        if now % 10 == 0:
            self.update_gen_control(now)
            inflow = self.tags.lake_inflow.value
            barrage = self.tags.barrage_flow.value
            level = self.tags.lake_level.value
            g1mw = self.tags.g1_MW.value
            g2mw = self.tags.g2_MW.value
            g1sl = self.tags.g1_scr_loss.value
            g2sl = self.tags.g2_scr_loss.value
            tpmw = self.tags.tp_setMW.value
            stnmw = g1mw + g2mw
            info_str = f"Inflow {inflow:.1f}m³/s " \
                f"Barrage {barrage:.1f}m³/s\n" \
                f"Lake {level:.3f}m\n" \
                f"G1 {g1mw:.1f}MW P1 Δ {g1sl:.3f}m\n" \
                f"G2 {g2mw:.1f}MW P2 Δ {g2sl:.3f}m\n" \
                f"Transpower {tpmw:.1f} Station {stnmw:.1f}\n"
            if self.tags.sms_info.value != info_str:
                self.tags.sms_info.value = info_str

    async def start(self):
        """Start the site logic."""
        self.periodic = Periodic(self.poll, 1.0)
        await self.periodic.start()

class SiteBus:
    """Interface with bus, start logic when tags are ready."""

    def __init__(self, bus_ip: str | None = '127.0.0.1',
                 bus_port: int = 1324):
        if bus_ip is not None:
            try:
                socket.gethostbyname(bus_ip)
            except socket.gaierror:
                raise ValueError(f"Invalid bus_ip: {bus_ip}")

        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='Site Code')
        self.site_logic = None

    async def start(self):
        """Start bus connection and API polling."""
        if self.busclient is not None:
            await self.busclient.start()
        self.tags = Tags()
        await self.tags.all_ready()
        self.site_logic = SiteLogic(self.tags)
        await self.site_logic.start()


async def main():
    """Emulate a PLC supporting Modbus/TCP (registers only)."""
    site_bus = SiteBus(bus_ip='127.0.0.1', bus_port=1325)
    await site_bus.start()
    await asyncio.get_event_loop().create_future()


if __name__ == '__main__':
    asyncio.run(main())
