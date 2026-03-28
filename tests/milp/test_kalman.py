"""Kalman filter test."""
import math
from pymscada.milp import matrix
from pymscada.milp.kalmanfilter import KalmanFilter


def test_kalman():
    dt = 1
    qf = 0.00001
    rt = 1
    F = [[1, dt],
         [0, 1]]
    H = [[1, 0]]
    Q = [[qf / 3, qf / 2],
         [qf / 2, qf]]
    R = [[rt]]
    P = [[1000, 0],
         [0, 1000]]
    x0 = [[0],
          [0]]

    measurements = [
        -0.546, -1.992, 1.443, -1.273, 1.577, -0.188, 0.286, 0.747, 3.011,
        -0.589, -1.396, 0.612, 1.563, 3.285, 0.541, 0.326, 0.404, 4.040, 2.386,
        0.208, 0.066, 1.043, 2.802, 2.805, 2.777, 2.109, 3.214, 4.939, 2.315,
        1.916, 4.359, 1.673, 1.317, 4.877, 5.686, 1.429, 3.107, 4.773, 5.997,
        3.973, 1.844, 6.436, 3.962, 2.315, 3.716, 5.033, 5.445, 3.213, 5.759,
        6.163, 5.168, 4.567, 6.996, 3.872, 4.519, 7.200, 5.748, 8.015, 7.150,
        6.180,
    ]

    kf = KalmanFilter(F=F, H=H, Q=Q, R=R, P=P, x0=x0)
    predictions = []
    updates = []

    for z in measurements:
        prediction = kf.predict()
        predictions.append(matrix.dot(H, prediction)[0])
        update = kf.update([[z]])
        updates.append(update)

    assert round(predictions[-1][0], 5) == 6.43318


def test_kalman_volume_known_unknown():
    x = list(range(0, 7200, 60))
    sv = []
    sk = []
    su = []
    v = []
    k = []
    u = []

    Qk = 2.0      # ok process model  # noqa: N806
    Qu = 0.0005   # ok process model  # noqa: N806
    Rv = 0.1 * 1000000  # say 2mm  # noqa: N806
    Rk = 1.0      # say 10 cumecs  # noqa: N806
    Ru = 1.0      # not measured  # noqa: N806
    dt = 60.0     # 1 minute
    F = [  # noqa: N806
        [1, dt, dt],
        [0, 1, 0],
        [0, 0, 1]
    ]
    H = [  # noqa: N806
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 0]
    ]
    if True:
        Q = [  # noqa: N806
            [Qk**4 + Qu**4, Qk**3, Qu**3],
            [Qk**3, Qk**2, 0.],
            [Qu**3, 0., Qu**2],
        ]
    else:
        Q = [  # noqa: N806
            [(dt**5) / 20., (dt**4) / 8., (dt**3) / 6.],
            [(dt**4) / 8., (dt**3) / 3., (dt**2) / 2.],
            [(dt**3) / 6., (dt**2) / 2., dt]
        ]
    R = [  # noqa: N806
        [Rv, 0, 0],
        [0, Rk, 0],
        [0, 0, Ru]
    ]
    P = [  # noqa: N806
        [100, 0, 0],
        [0, 100, 0],
        [0, 0, 100]
    ]
    sim_volume = 0
    sim_known = -100
    sim_unknown = 90
    x0 = [
        [sim_volume],
        [sim_known],
        [0]
    ]
    kf = KalmanFilter(F=F, H=H, Q=Q, R=R, P=P, x0=x0)

    ra = 3.9
    xa = 0.5
    rb = 3.91
    xb = 0.55

    volume = 0
    known = 0
    unknown = 0
    for i in x:
        sim_known = -100 + 20 * math.sin(i * .1 + 0.5)
        if sim_volume < -5000:
            sim_unknown = 110
        if sim_volume > 5000:
            sim_unknown = 90

        xa = ra * xa * (1 - xa)
        xb = rb * xb * (1 - xb)
        sim_volume += (sim_known + sim_unknown) * dt

        sv.append(sim_volume + xa * 500)
        sk.append(sim_known + xb * 5)
        su.append(sim_unknown)
        v.append(volume)
        k.append(known)
        u.append(unknown)

        _ = kf.predict()
        update = kf.update([
            [sim_volume + xa * 500],
            [sim_known + xb * 1],
            [0]
        ])
        volume = update[0][0]
        known = update[1][0]
        unknown = update[2][0]

    assert abs(sim_volume - volume) < 5000
    assert abs(sim_known - known) < 10
    assert abs(sim_unknown - unknown) < 10

# if __name__ == '__main__':
#     test_kalman()
