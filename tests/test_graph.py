from datetime import datetime, timedelta
from math import pi, sin
from pathlib import Path
import pytest
import pymscada.graph_constants as gc
from pymscada.graph import Graph, GraphCanvas

RED = (255, 0, 0)
BLUE = (0, 0, 200)
YELLOW = (255, 255, 0)


def make_times(count, step_minutes):
    start = datetime(2024, 1, 1, 0, 0)
    return [start + timedelta(minutes=step_minutes * i) for i in range(count)]


def make_sawtooth(count=73, step_minutes=10):
    times = make_times(count, step_minutes)
    return [(t, min(i % 20, 20 - i % 20) * 10) for i, t in enumerate(times)]


def shifted(series, minutes):
    return [(t + timedelta(minutes=minutes), v) for t, v in series]


def make_sinusoid(count=73, step_minutes=10., period=36., phase=0.,
                  offset=0., amplitude=40.):
    times = make_times(count, step_minutes)
    return [
        (t, offset + amplitude * sin(2 * pi * (i + phase) / period))
        for i, t in enumerate(times)
    ]


def lit(image):
    return [p for p in image.pixels if p != gc.WHITE]


# GraphCanvas


def test_new_image_is_filled_with_background():
    image = GraphCanvas(3, 2, background=(1, 2, 3))
    assert image.pixels == [(1, 2, 3)] * 6


def test_set_pixel_ignores_out_of_bounds():
    image = GraphCanvas(2, 2)
    image.set_pixel(5, 5, RED)
    image.set_pixel(-1, 0, RED)
    image.set_pixel(1, 1, RED)
    assert lit(image) == [RED]


def test_draw_line_includes_both_end_points():
    image = GraphCanvas(5, 5)
    image.draw_line(0, 0, 4, 4, RED)
    assert image.pixels[0] == RED
    assert image.pixels[4 * 5 + 4] == RED
    assert len(lit(image)) == 5


def test_draw_text_scale_enlarges_glyphs():
    small, large = GraphCanvas(40, 40), GraphCanvas(40, 40)
    small.draw_text(0, 0, "A", RED, scale=1)
    large.draw_text(0, 0, "A", RED, scale=2)
    assert len(lit(large)) == 4 * len(lit(small))


def test_draw_text_rejects_unknown_anchor():
    with pytest.raises(ValueError):
        GraphCanvas(10, 10).draw_text(0, 0, "A", anchor="zz")


def test_vertical_text_rotates_counter_clockwise():
    image = GraphCanvas(8, 8)
    image.draw_vertical_text(0, 0, "L", RED)
    points = {
        (i % image.width, i // image.width)
        for i, pixel in enumerate(image.pixels) if pixel == RED
    }
    assert points == (
        {(row, 4) for row in range(6)}
        | {(6, column) for column in range(5)}
    )


def test_save_writes_png(tmp_path):
    image = GraphCanvas(2, 1)
    image.set_pixel(0, 0, RED)
    path = tmp_path / "out.png"
    image.save(path)
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(data[16:20], "big") == 2
    assert int.from_bytes(data[20:24], "big") == 1


# Graph


def plotted(series=None):
    """A plotted one-axis graph over 0..100 for checking gridlines."""
    graph = Graph(300, 200)
    graph.add_y_axis("level", (0, 100))
    graph.add_trace(series or make_sawtooth(13), "level")
    return graph


def test_set_grid_defaults_y_to_x():
    graph = plotted()
    graph.set_grid(4)
    graph.plot()
    assert len(graph.canvas.x_fractions) == len(graph.canvas.y_fractions) == 5


def test_set_y_divisions_accepts_a_count():
    graph = plotted()
    graph.set_y_divisions(5)
    graph.plot()
    assert graph.canvas.y_fractions == [0, 0.2, 0.4, 0.6, 0.8, 1]
    assert graph.lhs_axes[0].labels == ["0", "20", "40", "60", "80", "100"]


def test_set_y_divisions_accepts_axis_values():
    graph = plotted()
    graph.set_y_divisions([0, 10, 50, 90, 100])
    graph.plot()
    assert graph.canvas.y_fractions == [0, 0.1, 0.5, 0.9, 1]
    assert graph.lhs_axes[0].labels == ["0", "10", "50", "90", "100"]


def test_y_values_follow_the_first_axis_on_other_axes():
    graph = plotted()
    graph.add_y_axis("ratio", (0, 1), side="rhs")
    graph.set_y_divisions([0, 50, 100])
    graph.plot()
    assert graph.rhs_axes[0].labels == ["0.0", "0.5", "1.0"]


@pytest.mark.parametrize("text", ["30min", "30 min", "30 minutes", "0.5h"])
def test_set_x_divisions_accepts_equivalent_intervals(text):
    graph = plotted(make_sawtooth(13))  # 00:00 to 02:00
    graph.set_x_divisions(text)
    graph.plot()
    assert graph.canvas.x_fractions == [0, 0.25, 0.5, 0.75, 1]


def test_set_x_divisions_offsets_first_line_to_the_interval():
    start = datetime(2024, 1, 1, 0, 10)
    series = [(start + timedelta(minutes=10 * i), i) for i in range(10)]
    graph = plotted(series)  # 00:10 to 01:40
    graph.set_x_divisions("30 min")
    graph.plot()
    assert [t.strftime("%H:%M") for _, t in graph.x_ticks] == [
        "00:30", "01:00", "01:30"
    ]
    assert graph.canvas.x_fractions[0] == pytest.approx(20 / 90)


@pytest.mark.parametrize("action", [
    lambda g: g.set_grid(0),
    lambda g: g.set_y_divisions(0),
    lambda g: g.set_y_divisions([]),
    lambda g: g.set_x_divisions(0),
    lambda g: g.set_x_divisions("soon"),
    lambda g: g.set_x_divisions("0 min"),
    lambda g: g.set_x_divisions("30 fortnights"),
])
def test_invalid_divisions_are_rejected(action):
    with pytest.raises(ValueError):
        action(Graph())


def test_y_divisions_outside_the_axis_range_are_rejected():
    graph = plotted()
    graph.set_y_divisions([0, 150])
    with pytest.raises(ValueError):
        graph.plot()


def test_layout_stacks_boxes_one_margin_apart():
    canvas = GraphCanvas(200, 100, margin=10)
    canvas.layout(title_height=8, x_height=12, lhs_widths=[20, 30], rhs_widths=[15])
    title, x, graph = canvas.title_box, canvas.x_box, canvas.graph_box
    lhs1, lhs2 = canvas.lhs_y_boxes
    (rhs,) = canvas.rhs_y_boxes

    assert (title.top, title.bottom) == (10, 18)
    assert (x.top, x.bottom) == (100 - 10 - 12, 100 - 10)
    assert (lhs1.left, lhs1.right) == (10, 30)
    assert lhs2.left == lhs1.right + 10
    assert (rhs.left, rhs.right) == (200 - 10 - 15, 200 - 10)
    assert graph.left == lhs2.right + 10
    assert graph.right == rhs.left - 10
    assert graph.top == title.bottom + 10
    assert graph.bottom == x.top - 10


def test_y_boxes_extend_past_graph_box_to_hold_label_text():
    canvas = GraphCanvas(200, 100, margin=10)
    canvas.layout(title_height=8, x_height=12, lhs_widths=[20])
    (lhs,) = canvas.lhs_y_boxes
    assert lhs.top == canvas.graph_box.top - 3
    assert lhs.bottom == canvas.graph_box.bottom + 3


def test_layout_is_only_recalculated_on_request():
    canvas = GraphCanvas(200, 100, margin=10)
    before = canvas.graph_box.left
    canvas.margin = 20
    assert canvas.graph_box.left == before
    canvas.layout()
    assert canvas.graph_box.left == 20


def test_plot_sizes_y_boxes_from_axis_labels():
    graph = Graph(200, 100, title="T")
    graph.add_y_axis("wide", (0, 100))
    graph.add_y_axis("narrow", (0, 10), side="rhs")
    graph.add_trace(make_sawtooth(3), "wide")
    graph.add_trace(make_sawtooth(3), "narrow")
    graph.plot()
    (lhs,), (rhs,) = graph.canvas.lhs_y_boxes, graph.canvas.rhs_y_boxes
    assert lhs.width == graph.lhs_axes[0].width
    assert rhs.width == graph.rhs_axes[0].width
    assert lhs.width > rhs.width


def test_unnamed_traces_do_not_reserve_legend_space():
    graph = plotted(make_sawtooth(3))
    graph.plot()
    assert graph.canvas.legend_entries == []
    assert graph.canvas.legend_boxes == []
    assert graph.canvas.x_box.bottom == graph.canvas.height - graph.canvas.margin


def test_named_traces_wrap_and_center_legend_entries():
    graph = Graph(100, 160)
    graph.add_y_axis("level", (0, 1))
    graph.add_trace(make_sawtooth(2), "level", colour=RED, name="Level")
    graph.add_trace(make_sawtooth(2), "level", colour=BLUE, name="Ratio")
    graph.plot()
    canvas = graph.canvas
    boxes = canvas.legend_boxes
    assert [box.entries for box in boxes] == [[("Level", RED)], [
        ("Ratio", BLUE)
    ]]
    assert [box.height for box in boxes] == [gc.TEXT_HEIGHT] * 2
    assert canvas.x_box.bottom == boxes[0].top - canvas.margin
    assert boxes[0].bottom == boxes[1].top - canvas.margin
    assert boxes[1].bottom == canvas.height - canvas.margin
    rows = graph.legend_rows()
    assert len(rows) == 2
    line_width = gc.GLYPH_ADVANCE * 2
    for box, (entries, row_width) in zip(boxes, rows):
        (name, colour), = entries
        x = box.left + (box.width - row_width) // 2
        y = box.top
        assert canvas.pixels[(y + gc.LABEL_HALF_HEIGHT) * canvas.width + x] == colour
        text_x = x + line_width + gc.SPACE_ADVANCE
        assert canvas.pixels[y * canvas.width + text_x] == colour


def test_y_axis_name_is_centered_in_largest_bottom_first_gap():
    graph = Graph(300, 220)
    graph.add_y_axis("level", (0, 100), colour=BLUE)
    graph.set_y_divisions([0, 10, 20, 90, 100])
    graph.add_trace(make_sawtooth(3), "level", colour=RED)
    graph.plot()
    box = graph.canvas.lhs_y_boxes[0]
    gap_top = graph.canvas.grid_y_at(0.9)
    gap_bottom = graph.canvas.grid_y_at(0.2)
    name_pixels = [
        (i % graph.canvas.width, i // graph.canvas.width)
        for i, pixel in enumerate(graph.canvas.pixels)
        if pixel == BLUE and box.left <= i % graph.canvas.width < box.right
        and gap_top + gc.LABEL_HALF_HEIGHT < i // graph.canvas.width
        < gap_bottom - gc.LABEL_HALF_HEIGHT
    ]
    name_xs = [x for x, _ in name_pixels]
    name_ys = [y for _, y in name_pixels]
    center = graph.canvas.grid_y_at(0.55)
    assert name_pixels
    assert min(name_xs) >= box.left
    assert max(name_xs) < box.right
    assert max(name_xs) == box.right - 1
    assert abs((min(name_ys) + max(name_ys)) / 2 - center) <= 1


def test_y_axis_name_ties_choose_bottommost_gap():
    graph = Graph(300, 220)
    graph.add_y_axis("Power", (0, 20), colour=BLUE)
    graph.set_y_divisions([0, 4, 8, 12, 16, 20])
    graph.add_trace(make_sawtooth(3), "Power", colour=RED)
    graph.plot()
    box = graph.canvas.lhs_y_boxes[0]
    gap_top = graph.canvas.grid_y_at(0.2)
    gap_bottom = graph.canvas.grid_y_at(0)
    name_ys = [
        i // graph.canvas.width
        for i, pixel in enumerate(graph.canvas.pixels)
        if pixel == BLUE and box.left <= i % graph.canvas.width < box.right
        and gap_top + gc.LABEL_HALF_HEIGHT < i // graph.canvas.width
        < gap_bottom - gc.LABEL_HALF_HEIGHT
    ]
    center = graph.canvas.grid_y_at(0.1)
    assert name_ys
    assert abs((min(name_ys) + max(name_ys)) / 2 - center) <= 1


def test_rhs_y_axis_name_is_aligned_to_graph_box():
    graph = Graph(300, 220)
    graph.add_y_axis("level", (0, 100), side="rhs", colour=BLUE)
    graph.set_y_divisions([0, 10, 20, 90, 100])
    graph.add_trace(make_sawtooth(3), "level", colour=RED)
    graph.plot()
    box = graph.canvas.rhs_y_boxes[0]
    gap_top = graph.canvas.grid_y_at(0.9)
    gap_bottom = graph.canvas.grid_y_at(0.2)
    name_xs = [
        i % graph.canvas.width
        for i, pixel in enumerate(graph.canvas.pixels)
        if pixel == BLUE and box.left <= i % graph.canvas.width < box.right
        and gap_top + gc.LABEL_HALF_HEIGHT < i // graph.canvas.width
        < gap_bottom - gc.LABEL_HALF_HEIGHT
    ]
    assert name_xs
    assert min(name_xs) == box.left


def test_axis_sets_graph_box_edge_line_when_added():
    graph = Graph()
    box = graph.canvas.graph_box
    assert (box.left_line, box.right_line) == (None, None)
    graph.add_y_axis("left", (0, 1), colour=BLUE)
    graph.add_y_axis("right", (0, 1), colour=RED, side="rhs")
    assert (box.left_line, box.right_line) == (BLUE, RED)


def test_trace_sets_unset_axis_colour():
    graph = Graph()
    graph.add_y_axis("hidden", (0, 1))
    axis = graph.add_y_axis("level", (0, 1))
    assert axis.colour is None
    graph.add_trace(make_sawtooth(2), "level", colour=RED)
    assert axis.colour == RED
    assert graph.canvas.graph_box.left_line == RED


def test_axis_without_colour_is_not_plotted():
    graph = Graph()
    graph.add_y_axis("hidden", (0, 1))
    graph.add_y_axis("visible", (0, 1), side="rhs")
    graph.add_trace(make_sawtooth(2), "visible", colour=RED)
    graph.plot()
    assert graph.canvas.lhs_y_boxes == []
    assert len(graph.canvas.rhs_y_boxes) == 1
    assert graph.canvas.graph_box.left_line is None


def test_traces_never_leave_the_graph_box():
    graph = Graph(200, 200, box_background=YELLOW)
    graph.add_y_axis("level", (0, 10), colour=BLUE)
    graph.add_trace(make_sawtooth(20), "level", colour=RED)  # peaks at 100
    graph.plot()
    canvas, box = graph.canvas, graph.canvas.graph_box
    red = [
        (i % canvas.width, i // canvas.width)
        for i, p in enumerate(canvas.pixels)
        if p == RED
    ]
    assert red
    assert all(
        box.left <= x < box.right and box.top <= y < box.bottom
        for x, y in red
    )


def test_boxes_are_filled_with_their_background():
    graph = Graph(200, 100, box_background=YELLOW)
    graph.add_y_axis("level", (0, 40))
    graph.add_trace(make_sawtooth(3), "level")
    graph.plot()
    box = graph.canvas.graph_box
    corner = box.top * graph.canvas.width + box.left
    assert graph.canvas.pixels[corner] != gc.WHITE
    assert YELLOW in graph.canvas.pixels


def test_traces_are_drawn_against_named_axes():
    graph = Graph(200, 200)
    graph.add_y_axis("level", (0, 40))
    graph.add_y_axis("ratio", (-1, 1), side="rhs")
    graph.add_trace(make_sawtooth(5), "level", colour=RED)
    graph.add_trace(make_sinusoid(5), "ratio", colour=BLUE)
    graph.plot()
    assert RED in graph.canvas.pixels
    assert BLUE in graph.canvas.pixels


@pytest.mark.parametrize("action", [
    lambda g: g.add_trace([], "level"),
    lambda g: g.add_trace(make_sawtooth(2), "missing"),
    lambda g: g.add_y_axis("level", (0, 1)),
    lambda g: g.add_y_axis("other", (0, 1), side="middle"),
    lambda g: g.plot(),
])
def test_invalid_use_is_rejected(action):
    graph = Graph()
    graph.add_y_axis("level", (0, 40))
    with pytest.raises(ValueError):
        action(graph)


def test_axis_adds_decimal_places_when_range_is_small():
    graph = Graph()
    graph.add_y_axis("big", (0, 100))
    graph.add_y_axis("small", (0, 1), side="rhs")
    graph.add_y_axis("fixed", (0, 100), side="rhs", dp=2)
    big, small, fixed = graph.lhs_axes + graph.rhs_axes
    assert big.labels[1] == "10"
    assert small.labels[1] == "0.1"
    assert fixed.labels[1] == "10.00"


def test_traces_default_to_successive_palette_colours():
    graph = Graph()
    graph.add_y_axis("level", (0, 40))
    for _ in range(3):
        graph.add_trace(make_sawtooth(2), "level")
    assert [colour for _, colour, _ in graph.traces] == gc.COLORS[:3]


def test_create_image_png():
    """Builds the sample graph (one triangle, three sinusoids) to PNG."""
    graph = Graph(title="Triangle and Sinusoids")
    graph.add_y_axis("triangle", (0, 100))
    graph.add_y_axis("sinusoid", (0, 100), side="rhs")
    graph.add_y_axis("fast", (0, 200))
    graph.add_y_axis("slow", (-0.3, 0.2), side="rhs")
    graph.set_x_divisions("103 minutes")
    graph.set_y_divisions([0, 10, 50, 90, 100])
    graph.add_trace(shifted(make_sawtooth(), 12), "triangle",
                    "One long name for a colour with the intent to force wrap")
    graph.add_trace(shifted(make_sinusoid(), 12), "sinusoid",
                    "Two also long so it doesn't look weird")
    graph.add_trace(shifted(make_sinusoid(period=24, phase=6, offset=100), 12),
                    "fast", "Three")
    graph.add_trace(shifted(make_sinusoid(period=72, phase=-9, offset=-0.05,
                                          amplitude=0.25), 12),
                    "slow", "Four")
    graph.plot()
    path = Path(__file__).parent / "test_assets" / "image.png"
    graph.save(path)

    image = path.read_bytes()
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(image[16:20], "big") == gc.WIDTH
    assert int.from_bytes(image[20:24], "big") == gc.HEIGHT



