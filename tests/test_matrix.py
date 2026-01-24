"""Test basic pure python matrix functions."""
import pytest
import pymscada.matrix as matrix


def test_create():
    """Zeroed matrix with the correct shape."""
    assert matrix.zeros(2, 3) == [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0]
    ]
    assert matrix.identity(2) == [
        [1.0, 0.0],
        [0.0, 1.0]
    ]


def test_shape():
    """Check shape reports correctly."""
    assert len(matrix.shape(1)) == 0
    assert matrix.shape([1, 2, 3]) == [3]
    assert matrix.shape([[1, 2, 3]]) == [1, 3]
    assert matrix.shape([[1], [2], [3]]) == [3, 1]
    assert matrix.shape([[[1]], [[2]], [[3]]]) == [3, 1, 1]  # is this right?


def test_math():
    """Simple math."""
    a = [
        [1.0, 2.0],
        [4.0, 4.0]
    ]
    b = [
        [-7.0, 0.1],
        [2.0, 1.0]
    ]
    c = [
        [-7.0, 0.1, 12.0],
        [2.0, 1.0, -15.0]
    ]
    d = [
        [-7.0, 0.1],
        [2.0, 10.1],
        [2.0, 1.0]
    ]
    assert matrix.add(a, b) == [
        [-6.0, 2.1],
        [6.0, 5.0]
    ]
    assert matrix.sub(a, b) == [
        [8.0, 1.9],
        [2.0, 3.0]
    ]
    with pytest.raises(ArithmeticError):
        matrix.add(c, a)
    with pytest.raises(ArithmeticError):
        matrix.sub(d, a)
    assert matrix.dot(a, b) == [
        [-3.0, 2.1],
        [-20.0, 4.4]
    ]
    assert matrix.dot(c, d) == [
        pytest.approx([73.2, 12.31]),
        pytest.approx([-42.0, -4.7])
    ]
    assert matrix.dot(d, c) == [
        pytest.approx([49.2, -0.6, -85.5]),
        pytest.approx([6.2, 10.3, -127.5]),
        pytest.approx([-12.0, 1.2, 9.0])
    ]
    with pytest.raises(ArithmeticError):
        matrix.dot(a, d)


def test_misc():
    """Test transposition."""
    assert matrix.transpose([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0]
    ]) == [
        [1.0, 3.0, 5.0],
        [2.0, 4.0, 6.0]
    ]
    assert matrix.scale(2.0, [
        [-3.0, 2.1],
        [-20.0, 4.4]
    ]) == [
        [-6.0, 4.2],
        [-40.0, 8.8]
    ]
    m = [[1.0, 2.0], [3.0, 4.0]]
    mcopy = matrix.copy(m)
    mcopy[0][0] = 10.0
    assert m[0][0] != 10.0


def test_inverse():
    """Test matrix inverse."""
    a = [
        [-3.0, 2.0, -5.0],
        [-1.0, 0.0, -2.0],
        [3.0, -4.0, 1.0]
    ]
    ainv = [
        [4.0/3, -3.0, 2.0/3],
        [1.0/1.2, -2.0, 1.0/6],
        [-2.0/3, 1.0, -1.0/3]
    ]
    identity = matrix.identity(3)
    assert matrix.inverse(a) == [
        pytest.approx(row) for row in ainv
    ]
    assert matrix.dot(a, matrix.inverse(a)) == [
        pytest.approx(row) for row in identity
    ]
    with pytest.raises(ArithmeticError):
        matrix.inverse([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])


def test_plu():
    """Test LU factorization."""
    # Reorder the equations if the leading coefficient is 0.
    # 0 x1 + 2 x2 = r1
    # 1 x1 + 3 x2 = r2
    a = [[0.0, 2.0], [1.0, 3.0]]
    P, L, U = matrix.plu(a)
    result = matrix.dot(L, U)
    expected = [[1.0, 3.0], [0.0, 2.0]]
    assert result[0] == pytest.approx(expected[0])
    assert result[1] == pytest.approx(expected[1])
    # Reject as not a valid square system.
    with pytest.raises(ArithmeticError):
        matrix.plu([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])


def test_substitution():
    """Test forward and back substitution."""
    # Forward substitution solves:
    # 1 y1        = 1
    # 2 y1 + 1 y2 = 2
    L = [[1.0, 0.0], [2.0, 1.0]]
    b = [[1.0], [2.0]]
    y = matrix.forward_substitution(L, b)
    assert y[0][0] == pytest.approx(1.0)
    assert y[1][0] == pytest.approx(0.0)
    # Back substitution solves:
    # 2 x1 + 1 x2 = y1
    #        1 x2 = y2
    U = [[2.0, 1.0], [0.0, 1.0]]
    x = matrix.back_substitution(U, y)
    assert x[0][0] == pytest.approx(0.5)
    assert x[1][0] == pytest.approx(0.0)
    # Reject as not a valid square system.
    with pytest.raises(ArithmeticError):
        matrix.forward_substitution([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], b)
    with pytest.raises(ArithmeticError):
        matrix.forward_substitution(L, [[1.0], [2.0], [3.0]])
    with pytest.raises(ArithmeticError):
        matrix.back_substitution([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], y)
    with pytest.raises(ArithmeticError):
        matrix.back_substitution(U, [[1.0], [2.0], [3.0]])
