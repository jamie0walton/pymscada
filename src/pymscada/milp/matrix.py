"""Pure Python matrices without numpy."""
from copy import deepcopy


def copy(m):
    """Just a copy of copy.deepcopy, TODO prune this."""
    return deepcopy(m)


def zeros(rows, cols):
    """Return a array of zeros."""
    m = [[0.0 for _ in range(cols)] for _ in range(rows)]
    return m


def identity(size):
    """Return identify matrix."""
    m = zeros(size, size)
    for i in range(size):
        m[i][i] = 1.0
    return m


def add(m1, m2):
    """Return the sum of two matrices."""
    if len(m1) != len(m2) or len(m1[0]) != len(m2[0]):
        raise ArithmeticError('matrices different shapes')
    m = zeros(len(m1), len(m1[0]))
    for row in range(len(m1)):
        for col in range(len(m1[0])):
            m[row][col] = m1[row][col] + m2[row][col]
    return m


def sub(m1, m2):
    """Return the difference between two matrices."""
    if len(m1) != len(m2) or len(m1[0]) != len(m2[0]):
        raise ArithmeticError('matrices different shapes')
    m = zeros(len(m1), len(m1[0]))
    for row in range(len(m1)):
        for col in range(len(m1[0])):
            m[row][col] = m1[row][col] - m2[row][col]
    return m


def transpose(m1):
    """Return a transposed matrix."""
    m = [[m1[row][col] for row in range(len(m1))] for col in range(len(m1[0]))]
    return m


def dot(m1, m2):
    """Return the dot product."""
    if len(m1[0]) != len(m2):
        raise ArithmeticError('matrices wrong shape to multiply')
    m = zeros(len(m1), len(m2[0]))
    for row in range(len(m1)):
        for col in range(len(m2[0])):
            for x in range(len(m1[0])):
                m[row][col] += m1[row][x] * m2[x][col]
    return m


def scale(x1, m2):
    """Return the scaled matrix."""
    m = zeros(len(m2), len(m2[0]))
    for row in range(len(m2)):
        for col in range(len(m2[0])):
            m[row][col] += x1 * m2[row][col]
    return m


def shape(m):
    """Return list of dimensions."""
    dims = []

    def _len_list(m):
        if type(m) is list:
            dims.append(len(m))
            _len_list(m[0])

    _len_list(m)
    return dims


# https://johnfoster.pge.utexas.edu/numerical-methods-book/LinearAlgebra_LU.html
def plu(A, abs_tol=1e-5):  # noqa: N803
    """LU factorisation with Pivot."""
    n = len(A)
    if n != len(A[0]):
        raise ArithmeticError('matrix A not square')
    # Allocate space for P, L, and U
    U = deepcopy(A)  # noqa: N806
    L = identity(n)  # noqa: N806
    P = identity(n)  # noqa: N806
    # Loop over rows
    for i in range(n):
        # Permute rows if needed
        for row in range(i, n):
            if abs(U[i][i]) > abs_tol:
                break
            U[row], U[row+1] = U[row+1], U[row]
            P[row], P[row+1] = P[row+1], P[row]
        # Eliminate entries below i with row
        # operations on U and reverse the row
        # operations to manipulate L
        for row in range(i + 1, n):
            L[row][i] = U[row][i] / U[i][i]
            for col in range(0, n):
                U[row][col] -= L[row][i] * U[i][col]
    return P, L, U


def inverse(A):  # noqa: N803
    """Calculate the inverse of A, not always possible."""
    n = len(A)
    if n != len(A[0]):
        raise ArithmeticError('matrix A not square')
    b = identity(n)
    Ainv = zeros(n, n)  # noqa: N806
    P, L, U = plu(A)  # noqa: N806
    for i in range(n):
        s = dot(P, [[j[i]] for j in b])
        y = forward_substitution(L, s)
        x = back_substitution(U, y)
        for j in range(n):
            Ainv[j][i] = x[j][0]
    return Ainv


def forward_substitution(L, b):  # noqa: N803
    """Solve for y in Ly=b."""
    n = len(L)
    if n != len(L[0]):
        raise ArithmeticError('matrix L not square')
    if len(b) != n:
        raise ArithmeticError('matrix b not len of L')
    y = [[0.0] for _ in b]
    # Initialise with the first row
    y[0][0] = b[0][0] / L[0][0]
    # Loop from second row down
    for i in range(1, n):
        s = b[i][0]
        for j in range(0, i):
            s -= L[i][j] * y[j][0]
        y[i][0] = s / L[i][i]
    return y


def back_substitution(U, y):  # noqa: N803
    """Solve for x in Ux=y."""
    n = len(U)
    if n != len(U[0]):
        raise ArithmeticError('matrix U not square')
    if len(y) != n:
        raise ArithmeticError('matrix y not len of U')
    x = [[0] for _ in y]
    # Initialise with the last row
    x[-1][0] = y[-1][0] / U[-1][-1]
    # Loop from the second last up
    for i in range(n-2, -1, -1):
        s = y[i][0]
        for j in range(n-1, i, -1):
            s -= U[i][j] * x[j][0]
        x[i][0] = s / U[i][i]
    return x
