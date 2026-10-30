from datetime import timedelta
from math import ceil
from pathlib import Path
from string import ascii_lowercase
import pymscada.graph_constants as gc

def parse_interval(text):
    """Turn "30min", "30 min" or "30 minutes" into a timedelta."""
    text = str(text).strip().lower()
    number = text.rstrip(ascii_lowercase)
    unit = gc.TIME_UNITS.get(text[len(number):])
    try:
        count = float(number)
    except ValueError:
        count = 0
    if unit is None or count <= 0:
        raise ValueError(f"Unsupported time interval: {text!r}")
    return timedelta(seconds=count * unit)


def even_fractions(count):
    """Fractions 0..1 splitting an extent into `count` equal divisions."""
    return [i / count for i in range(count + 1)]


def y_fractions(divisions, axes):
    """Gridline fractions for an int or a series of values on axes[0]."""
    if isinstance(divisions, int):
        return even_fractions(divisions)
    primary = axes[0]
    fractions = [primary.fraction(v) for v in divisions]
    if not all(0 <= f <= 1 for f in fractions):
        raise ValueError(
            f"Y divisions must lie within axis {primary.name!r} "
            f"range {primary.low} to {primary.high}"
        )
    return fractions


def time_ticks(start, end, divisions):
    """(fraction, datetime) gridlines between start and end.

    An int gives equal divisions; a timedelta puts a tick at every multiple
    counted from midnight of the start day.
    """
    span = (end - start).total_seconds() or 1
    if isinstance(divisions, int):
        return [(f, start + (end - start) * f) for f in even_fractions(divisions)]
    midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
    tick = midnight + ceil((start - midnight) / divisions) * divisions
    ticks = []
    while tick <= end:
        ticks.append(((tick - start).total_seconds() / span, tick))
        tick += divisions
    return ticks


class Box:
    """Rectangle in pixel coordinates; right and bottom are exclusive.

    left_line, right_line and bottom_line are optional colours for a darker
    line drawn along that edge inside the box.
    """

    def __init__(
        self, left=0, top=0, right=0, bottom=0, background=gc.WHITE
    ):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.background = background
        self.left_line = None
        self.right_line = None
        self.bottom_line = None

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top


class GraphCanvas:
    """Pixel canvas and the sole owner of the Cartesian layout.

    Boxes keep their edges until `layout()` is called again:
      title_box    margin below the top
      lhs_y_boxes  margin from the left, then from the prior lhs box
      rhs_y_boxes  margin from the right, then from the prior rhs box
      x_box        margin above the bottom
      graph_box    margin in from the title, y and x boxes
    """

    def __init__(
        self, width, height, background=gc.WHITE, margin=gc.MARGIN,
        box_background=gc.WHITE,
    ):
        self.width = width
        self.height = height
        self.pixels = [background] * (width * height)
        self.margin = margin
        self.box_background = box_background
        self.x_fractions = even_fractions(gc.GRID_DIVISIONS)
        self.y_fractions = even_fractions(gc.GRID_DIVISIONS)
        self.grid_colour = gc.GRID_COLOUR
        self.graph_box = Box(background=box_background)
        self.layout()

    def layout(self, title_height=0, x_height=0, lhs_widths=(), rhs_widths=()):
        """Recalculate every box edge from the requested sizes."""
        m = self.margin
        bg = self.box_background
        inner_left, inner_right = m, self.width - m

        self.title_box = Box(
            inner_left, m, inner_right, m + title_height, bg
        )
        self.x_box = Box(
            inner_left,
            self.height - m - x_height,
            inner_right,
            self.height - m,
            bg,
        )
        top = self.title_box.bottom + m
        bottom = self.x_box.top - m

        # Y labels are centred on the gridlines, so the y boxes reach past
        # the graph box by half a line of text and may overlap title/x boxes.
        box_top = top - gc.LABEL_HALF_HEIGHT
        box_bottom = bottom + gc.LABEL_HALF_HEIGHT

        self.lhs_y_boxes = []
        left = m
        for width in lhs_widths:
            self.lhs_y_boxes.append(
                Box(left, box_top, left + width, box_bottom, bg)
            )
            left += width + m

        self.rhs_y_boxes = []
        right = self.width - m
        for width in rhs_widths:
            self.rhs_y_boxes.append(
                Box(right - width, box_top, right, box_bottom, bg)
            )
            right -= width + m

        # The graph box persists so its edge lines survive a new layout.
        box = self.graph_box
        box.left, box.top, box.right, box.bottom = left, top, right, bottom

    @property
    def boxes(self):
        return [
            self.title_box,
            *self.lhs_y_boxes,
            *self.rhs_y_boxes,
            self.x_box,
            self.graph_box,
        ]

    def fill_boxes(self):
        for box in self.boxes:
            for y in range(box.top, box.bottom):
                for x in range(box.left, box.right):
                    self.set_pixel(x, y, box.background)

    @property
    def left_grid(self):
        return self.graph_box.left

    @property
    def right_grid(self):
        return self.graph_box.right - 1

    @property
    def top_grid(self):
        return self.graph_box.top

    @property
    def bottom_grid(self):
        return self.graph_box.bottom - 1

    def grid_x_at(self, fraction):
        """Pixel x for a fraction (0..1) across the grid."""
        return self.left_grid + round(
            fraction * (self.right_grid - self.left_grid)
        )

    def grid_y_at(self, fraction):
        """Pixel y for a fraction (0..1) up the grid."""
        return self.bottom_grid - round(
            fraction * (self.bottom_grid - self.top_grid)
        )

    def draw_box_lines(self):
        """Draw the graph box's darker edge lines, where set."""
        box = self.graph_box
        top, bottom = box.top, box.bottom - 1
        left, right = box.left, box.right - 1
        if box.left_line:
            self.draw_line(left, top, left, bottom, box.left_line)
        if box.right_line:
            self.draw_line(right, top, right, bottom, box.right_line)
        if box.bottom_line:
            self.draw_line(left, bottom, right, bottom, box.bottom_line)

    def draw_grid(self):
        """Draw the single set of vertical and horizontal gridlines."""
        for fraction in self.x_fractions:
            x = self.grid_x_at(fraction)
            self.draw_line(
                x, self.top_grid, x, self.bottom_grid, self.grid_colour
            )
        for fraction in self.y_fractions:
            y = self.grid_y_at(fraction)
            self.draw_line(
                self.left_grid, y, self.right_grid, y, self.grid_colour
            )

    def set_pixel(self, x, y, colour):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = colour

    @staticmethod
    def text_width(text, scale=1):
        """Pixel width of a single line of text."""
        advance = sum(
            gc.SPACE_ADVANCE if char == " " else gc.GLYPH_ADVANCE
            for char in text
        )
        return (advance - 1) * scale if text else 0

    def draw_text(
        self, x, y, text, colour=gc.BLACK, scale=1, anchor="nw"
    ):
        lines = text.split("\n")
        for line_index, line in enumerate(lines):
            line_width = self.text_width(line, scale)
            cursor_x = x
            cursor_y = y + line_index * gc.TEXT_HEIGHT * scale
            if anchor == "n":
                cursor_x -= line_width // 2
            elif anchor == "e":
                cursor_x -= line_width
                cursor_y -= gc.LABEL_HALF_HEIGHT * scale
            elif anchor == "w":
                cursor_y -= gc.LABEL_HALF_HEIGHT * scale
            elif anchor != "nw":
                raise ValueError(f"Unsupported text anchor: {anchor}")

            for character in line:
                if character == " ":
                    cursor_x += gc.SPACE_ADVANCE * scale
                    continue
                glyph = gc.FONT.get(character, gc.FONT["?"]).split("/")
                for row, pattern in enumerate(glyph):
                    for column, pixel in enumerate(pattern):
                        if pixel == "1":
                            for dy in range(scale):
                                for dx in range(scale):
                                    self.set_pixel(
                                        cursor_x + column * scale + dx,
                                        cursor_y + row * scale + dy,
                                        colour,
                                    )
                cursor_x += gc.GLYPH_ADVANCE * scale

    def draw_line(self, x0, y0, x1, y1, colour, clip=None):
        """Draw a line; with `clip` (a Box) only pixels inside it are set."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            if clip is None or (
                clip.left <= x0 < clip.right and clip.top <= y0 < clip.bottom
            ):
                self.set_pixel(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                break
            doubled_error = 2 * error
            if doubled_error >= dy:
                error += dy
                x0 += sx
            if doubled_error <= dx:
                error += dx
                y0 += sy

    def save(self, path):
        with Path(path).open("w", encoding="ascii", newline="\n") as file:
            file.write(f"P3\n{self.width} {self.height}\n255\n")
            for y in range(self.height):
                start = y * self.width
                row = self.pixels[start:start + self.width]
                file.write(" ".join(f"{r} {g} {b}" for r, g, b in row))
                file.write("\n")


class Axis:
    """A value axis: its range, colour and the text that labels it.

    `fractions` are the positions (0..1 of the range) that carry a label;
    the Graph sets them from its y divisions when plotting.
    """

    def __init__(self, name, low, high, colour=gc.BLACK, dp=None):
        self.name = name
        self.low = low
        self.high = high
        self.colour = colour
        self.dp = dp
        self.fractions = even_fractions(gc.GRID_DIVISIONS)

    @property
    def values(self):
        span = self.high - self.low
        return [self.low + span * f for f in self.fractions]

    @property
    def decimals(self):
        """Fixed `dp` if given, else the fewest places that keep every
        rounded interval within 50% of the true interval."""
        if self.dp is not None:
            return self.dp
        values = self.values
        for dp in range(gc.MAX_DP + 1):
            if all(
                abs(round(b, dp) - round(a, dp) - (b - a)) <= 0.5 * abs(b - a)
                for a, b in zip(values, values[1:])
            ):
                return dp
        return gc.MAX_DP

    @property
    def labels(self):
        dp = self.decimals
        return [f"{v:.{dp}f}" for v in self.values]

    @property
    def width(self):
        """Box width needed to hold the widest label."""
        return max(GraphCanvas.text_width(label) for label in self.labels)

    def fraction(self, value):
        return (value - self.low) / ((self.high - self.low) or 1)


class Graph:
    def __init__(
        self, width=gc.DEFAULT_SIZE, height=gc.DEFAULT_SIZE,
        margin=gc.MARGIN, title="", box_background=gc.WHITE,
    ):
        self.title = title
        self.canvas = GraphCanvas(
            width, height, margin=margin, box_background=box_background
        )
        self.axis_colour = gc.BLACK
        self.canvas.graph_box.bottom_line = self.axis_colour
        self.lhs_axes = []
        self.rhs_axes = []
        self.traces = []
        self.x_divisions = gc.GRID_DIVISIONS
        self.y_divisions = gc.GRID_DIVISIONS

    def set_grid(self, x=gc.GRID_DIVISIONS, y=None, colour=gc.GRID_COLOUR):
        """Set even x and y division counts (y defaults to x) and colour."""
        self.set_x_divisions(x)
        self.set_y_divisions(x if y is None else y)
        self.canvas.grid_colour = colour

    def set_y_divisions(self, divisions):
        """Set the horizontal gridlines and y labels.

        An integer gives that many equal divisions. A series, such as
        [0, 10, 50, 90, 100], gives values on the first y axis (the first
        left axis, else the first right axis); other axes are labelled at
        the same positions.
        """
        if isinstance(divisions, int):
            if divisions < 1:
                raise ValueError("Grid divisions must be positive")
        else:
            divisions = sorted(set(divisions))
            if not divisions:
                raise ValueError("Grid divisions must not be empty")
        self.y_divisions = divisions

    def set_x_divisions(self, divisions):
        """Set the vertical gridlines and time labels.

        An integer gives that many equal divisions. A string such as
        "30min", "30 min" or "30 minutes" puts a line at every multiple of
        that interval (counted from midnight), so the first line is offset
        from the start when the start is not on an interval.
        """
        if isinstance(divisions, int):
            if divisions < 1:
                raise ValueError("Grid divisions must be positive")
        else:
            divisions = parse_interval(divisions)
        self.x_divisions = divisions

    def add_y_axis(self, name, value_range, colour=None, side="lhs", dp=None):
        if side not in ("lhs", "rhs"):
            raise ValueError(f"Unsupported axis side: {side}")
        if name in self.axes:
            raise ValueError(f"Duplicate axis name: {name}")
        low, high = value_range
        axis = Axis(name, low, high, colour or self.axis_colour, dp)
        (self.lhs_axes if side == "lhs" else self.rhs_axes).append(axis)
        # The axis nearest the graph box sets that edge's darker line.
        graph_box = self.canvas.graph_box
        if side == "lhs" and graph_box.left_line is None:
            graph_box.left_line = axis.colour
        elif side == "rhs" and graph_box.right_line is None:
            graph_box.right_line = axis.colour
        return axis

    @property
    def axes(self):
        return {a.name: a for a in self.lhs_axes + self.rhs_axes}

    def add_trace(self, series, axis, colour=None):
        """Queue a time series, drawn against the y axis called `axis`.

        Without a colour, the next entry of COLORS is used.
        """
        series = list(series)
        if not series:
            raise ValueError("Cannot plot an empty series")
        if axis not in self.axes:
            raise ValueError(f"Unknown axis: {axis}")
        if colour is None:
            colour = gc.COLORS[len(self.traces) % len(gc.COLORS)]
        self.traces.append((series, colour, self.axes[axis]))

    def plot(self):
        """Lay out the canvas, then draw everything that has been prepared."""
        if not self.traces:
            raise ValueError("Nothing to plot")
        canvas = self.canvas
        time_range = self.time_range()
        self.resolve_divisions(time_range)
        canvas.layout(
            title_height=gc.TEXT_HEIGHT if self.title else 0,
            x_height=gc.TEXT_HEIGHT,
            lhs_widths=[a.width for a in self.lhs_axes],
            rhs_widths=[a.width for a in self.rhs_axes],
        )
        canvas.fill_boxes()
        canvas.draw_grid()
        canvas.draw_box_lines()
        self.draw_x_labels()
        self.draw_y_labels()
        for series, colour, axis in self.traces:
            self.draw_trace(series, colour, axis, time_range)
        self.draw_title()

    def time_range(self):
        starts = [series[0][0] for series, _, _ in self.traces]
        ends = [series[-1][0] for series, _, _ in self.traces]
        return min(starts), max(ends)

    def resolve_divisions(self, time_range):
        """Turn the division settings into gridline and label positions."""
        axes = self.lhs_axes + self.rhs_axes
        fractions = y_fractions(self.y_divisions, axes)
        self.canvas.y_fractions = fractions
        for axis in axes:
            axis.fractions = fractions

        self.x_ticks = time_ticks(*time_range, self.x_divisions)
        self.canvas.x_fractions = [fraction for fraction, _ in self.x_ticks]

    def draw_x_labels(self):
        canvas = self.canvas
        for fraction, tick in self.x_ticks:
            canvas.draw_text(
                canvas.grid_x_at(fraction),
                canvas.x_box.top,
                tick.strftime("%H:%M"),
                self.axis_colour,
                anchor="n",
            )

    def draw_y_labels(self):
        for axis, box in zip(self.lhs_axes, self.canvas.lhs_y_boxes):
            self.draw_y_axis_labels(axis, box.right - 1, "e")
        for axis, box in zip(self.rhs_axes, self.canvas.rhs_y_boxes):
            self.draw_y_axis_labels(axis, box.left, "w")

    def draw_y_axis_labels(self, axis, x, anchor):
        """Draw each label inside the axis box, centred on its gridline."""
        for fraction, label in zip(axis.fractions, axis.labels):
            y = self.canvas.grid_y_at(fraction)
            self.canvas.draw_text(x, y, label, axis.colour, anchor=anchor)

    def draw_trace(self, series, colour, axis, time_range):
        canvas = self.canvas
        start, end = time_range
        t_span = (end - start).total_seconds() or 1
        points = [
            (
                canvas.grid_x_at((t - start).total_seconds() / t_span),
                canvas.grid_y_at(axis.fraction(v)),
            )
            for t, v in series
        ]
        for (xa, ya), (xb, yb) in zip(points, points[1:]):
            canvas.draw_line(xa, ya, xb, yb, colour, clip=canvas.graph_box)

    def draw_title(self):
        if self.title:
            box = self.canvas.title_box
            width = GraphCanvas.text_width(self.title)
            x = box.left + (box.width - width) // 2
            self.canvas.draw_text(x, box.top, self.title, self.axis_colour)

    def save(self, path):
        self.canvas.save(path)
