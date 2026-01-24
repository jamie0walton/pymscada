"""Kalman filter, note Bu term is not working, commented out."""
import pymscada.matrix as matrix


class KalmanFilter:
    """Kalman Filter without numpy."""

    def __init__(self, F=None, B=None, H=None, Q=None, R=None,  # noqa: N803
                 P=None, x0=None, alpha=None):
        """Init with F, H at least. B, Q, R, P, x0, alpha have defaults."""
        if(F is None or H is None):
            raise ValueError("F and H cannot be None.")
        self.n = matrix.shape(F)[1]
        if self.n != matrix.shape(H)[1]:
            raise ValueError("F and H must have same number rows.")
        self.F = F
        self.H = H
        self.B = 0 if B is None else B
        self.Q = matrix.identity(self.n) if Q is None else Q
        self.R = matrix.identity(self.n) if R is None else R
        self.P = matrix.identity(self.n) if P is None else P
        self.x = matrix.zeros(self.n, 1) if x0 is None else x0
        self.alpha = 1.0 if alpha is None else alpha
        self._I = matrix.identity(self.n)  # don't alter
        self.K = matrix.zeros(self.n, 1)  # so linter sees the type
        self.x_prior = None
        self.P_prior = None
        self.x_post = None
        self.P_post = None

    def predict(self, u=0):
        """Estimate the future state."""
        # Estimate x = F x + B u  ... Bu is optional and not handled right
        self.x = matrix.dot(self.F, self.x)  # add with dot(self.B, u)
        # Estimate co-variance P = F P Ft + Q
        self.P = matrix.add(
            matrix.scale(self.alpha,
                         matrix.dot(matrix.dot(self.F, self.P),
                                    matrix.transpose(self.F))),
            self.Q
        )
        # save for ?
        self.x_prior = matrix.copy(self.x)
        self.P_prior = matrix.copy(self.P)
        return self.x

    def update(self, z):
        """Update prediction with measurement."""
        # error (residual) between measurement and prediction
        y = matrix.sub(z, matrix.dot(self.H, self.x))
        # common sub-expression
        PHT = matrix.dot(self.P, matrix.transpose(self.H))  # noqa: N806
        # co-variance / system uncertainty
        S = matrix.add(self.R, matrix.dot(self.H, PHT))  # noqa: N806
        SI = matrix.inverse(S)  # noqa: N806
        # map uncertainty into Kalman gain
        self.K = matrix.dot(self.P, matrix.dot(matrix.transpose(self.H), SI))
        # predict new x with error scaled by Kalman gain
        self.x = matrix.add(self.x, matrix.dot(self.K, y))
        # # Update estimate co-variance P = (I - K H) P
        # self.P = dot(self._I - dot(K, self.H), self.P)
        # Alternate that is more numerically stable (apparently)
        #      P = (I - KH) P (I - KH)T + K R KT
        I_KH = matrix.sub(self._I, matrix.dot(self.K, self.H))  # noqa: N806
        self.P = matrix.add(
            matrix.dot(matrix.dot(I_KH, self.P), matrix.transpose(I_KH)),
            matrix.dot(matrix.dot(self.K, self.R), matrix.transpose(self.K))
        )
        # save for ?
        self.x_post = matrix.copy(self.x)
        self.P_post = matrix.copy(self.P)
        return self.x

    def get_update(self):
        """Do I use this, check."""
        return self.x, self.P
