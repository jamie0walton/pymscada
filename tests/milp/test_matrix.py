"""Test basic pure python matrix functions."""
import pytest
from pymscada.milp import matrix


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
