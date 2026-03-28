"""Random useful stuff."""
import time


def interp(xvalue: float, xs: list, ys: list) -> float:
    """
    Interpolate inside and outside the range.

    given an X value, xs strictly increasing, ys OK
    interpolate and extrapolate past x[0] and x[len - 1]
    """
    i = 1
    if xvalue > xs[0]:
        for (i, v) in enumerate(xs):  # noqa: B007
            if xvalue < v:
                break
    return (xvalue - xs[i - 1]) / (xs[i] - xs[i - 1]) * \
        (ys[i] - ys[i - 1]) + ys[i - 1]


def interp_step(xvalue: float, xs: list, ys: list) -> float:
    """
    Interpolate as step value.

    given an X value, xs strictly increasing, ys any order
    find y given X assuming a stepwize function. Assumes ys[0]
    if xvalue < xs[0].
    """
    i = 1
    if xvalue > xs[0]:
        for (i, v) in enumerate(xs):  # noqa: B007
            if xvalue < v:
                break
    return ys[i - 1]


def tod_to_xs_ys(timeofday):
    """Convert (time, value)[] to xs[times], ys[values]."""
    tod = []
    tod.append(timeofday[len(timeofday) - 1].copy())
    tod[0][0] -= 86400
    [tod.append(x) for x in timeofday]
    tod.append(timeofday[0].copy())
    tod[len(tod) - 1][0] += 86400
    tod_xs = [x[0] for x in tod]
    tod_ys = [x[1] for x in tod]
    return tod_xs, tod_ys


def as_list(*args) -> list:
    """Concatenates tuples, lists and values into one list."""
    row = []
    for arg in args:
        if type(arg) in [tuple, list]:
            for item in arg:
                if type(arg) == tuple or type(arg) == list:
                    row += as_list(item)
                else:
                    row += [item]
        elif type(arg) in [float, int, str]:
            row += [arg]
        elif hasattr(arg, '__iter__'):
            row += [*arg]
        else:
            raise ValueError(f"{arg} invalid from MILP {args}")
    return row


def merge_list(*args) -> list:
    """Merge two or more lists as a list of unique values."""
    merged = []
    for arg in args:
        if arg is None:
            continue
        merged = list(set().union(merged, arg))
    return merged


def bid_period(time_s: int) -> int:
    """Convert UTC seconds to a bid period 1-46,48,50 depending on DST."""
    tp = time.localtime(time_s)  # get struct
    t0 = int(time.mktime((  # get start of day
        tp.tm_year,
        tp.tm_mon,
        tp.tm_mday,
        0,
        0,
        0,
        tp.tm_wday,
        tp.tm_yday,
        -1  # tp.tm_isdst
    )))
    sec_into_day = time_s - t0
    period = sec_into_day // 1800 + 1
    # periodstart = t0 + (period - 1) * 1800
    return int(period)


def bid_time(time_s: int, p: int) -> int:
    """Convert a bid period 1-46,48,50 depending on DST to UTC seconds."""
    tp = time.localtime(time_s)  # get struct
    t0 = int(time.mktime((  # get start of day
        tp.tm_year,
        tp.tm_mon,
        tp.tm_mday,
        0,
        0,
        0,
        tp.tm_wday,
        tp.tm_yday,
        -1  # tp.tm_isdst
    )))
    sec_utc = t0 + (p - 1) * 1800
    return sec_utc


def day_seconds(time_s: int):
    """For UCT find seconds since midnight."""
    tp = time.localtime(time_s)
    daystart = int(time.mktime((
        tp.tm_year, tp.tm_mon, tp.tm_mday,
        0, 0, 0,
        tp.tm_wday, tp.tm_yday, -1
    )))
    return time_s - daystart


def find_node(find: str, tree):
    """Return list of dicts at the level of the first match."""
    found = []

    def delve(subtree):
        nonlocal found
        if type(subtree) == dict:
            if find in subtree:
                found.append(subtree)
                return
            for i in subtree:
                delve(subtree[i])
        elif type(subtree) == list:
            for i in subtree:
                delve(i)

    delve(tree)
    return found


def find_value(find: str, tree):
    """Return list of dicts at the level of the first match."""
    found = None

    def delve(subtree):
        nonlocal found
        if type(subtree) == dict:
            if find in subtree.values():
                found = subtree
                return True
            for i in subtree:
                if delve(subtree[i]):
                    return True
        elif type(subtree) == list:
            if find in subtree:
                found = subtree
                return
            for i in subtree:
                if delve(i):
                    return True

    delve(tree)
    return found


def find_node_iter(find: str, tree):
    """Return list of dicts at the level of the first match."""
    if type(tree) == dict:
        if find in tree:
            yield tree
            return
        for i in tree:
            yield from find_node_iter(find, tree[i])
    elif type(tree) == list:
        for i in tree:
            yield from find_node_iter(find, i)


def find_nodes(key: str, tree):
    """Return all subtrees that have a matching key."""
    if isinstance(tree, dict):
        for i in tree:
            if i == key:
                yield tree
            yield from find_nodes(key, tree[i])
    elif isinstance(tree, list):
        for i in tree:
            yield from find_nodes(key, i)
