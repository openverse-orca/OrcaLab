from orcalab.math import Transform

import pytest
import numpy as np
import math


def test_default_constructor():
    t = Transform()
    np.testing.assert_array_equal(t.position, np.zeros(3))
    np.testing.assert_array_equal(t.rotation, np.array([1, 0, 0, 0]))
    assert t.scale == 1.0


def test_position_setter_type():
    with pytest.raises(TypeError):
        Transform(position=[1, 2, 3])


def test_rotation_setter_type():
    with pytest.raises(TypeError):
        Transform(rotation=[1, 0, 0, 0])


def test_rotation_setter_shape():
    with pytest.raises(TypeError):
        Transform(rotation=np.array([1, 0, 0]))


def test_rotation_unit_quaternion():
    with pytest.raises(ValueError):
        Transform(rotation=np.array([2, 0, 0, 0]))


def test_scale_setter_type():
    with pytest.raises(TypeError):
        Transform(scale="not_a_float")


def test_transform_point_identity():
    identity = Transform()
    point = np.array([1.0, 2.0, 3.0])
    result = identity.transform_point(point)
    np.testing.assert_array_almost_equal(result, point)


def test_transform_point_translation():
    t = Transform(
        position=np.array([1, 2, 3]), rotation=np.array([1, 0, 0, 0]), scale=1.0
    )
    point = np.array([0.0, 0.0, 0.0])
    result = t.transform_point(point)
    np.testing.assert_array_almost_equal(result, np.array([1, 2, 3]))


def test_transform_point_scale():
    t = Transform(position=np.zeros(3), rotation=np.array([1, 0, 0, 0]), scale=2.0)
    point = np.array([1.0, 1.0, 1.0])
    result = t.transform_point(point)
    np.testing.assert_array_almost_equal(result, np.array([2.0, 2.0, 2.0]))


def test_transform_vector():
    t = Transform(position=np.zeros(3), rotation=np.array([1, 0, 0, 0]), scale=3.0)
    vector = np.array([1.0, 0.0, 0.0])
    result = t.transform_vector(vector)
    np.testing.assert_array_almost_equal(result, np.array([3.0, 0.0, 0.0]))


def test_transform_direction():
    t = Transform(position=np.zeros(3), rotation=np.array([1, 0, 0, 0]), scale=5.0)
    direction = np.array([0.0, 1.0, 0.0])
    result = t.transform_direction(direction)
    np.testing.assert_array_almost_equal(result, direction)


def test_transform_point_type_error():
    t = Transform()
    with pytest.raises(TypeError):
        t.transform_point([1, 2, 3])


def test_transform_vector_type_error():
    t = Transform()
    with pytest.raises(TypeError):
        t.transform_vector([1, 2, 3])


def test_transform_direction_type_error():
    t = Transform()
    with pytest.raises(TypeError):
        t.transform_direction([1, 2, 3])


def test_multiply_identity():
    t = Transform(
        position=np.array([1, 2, 3]), rotation=np.array([1, 0, 0, 0]), scale=2.0
    )
    result = t.multiply(Transform())
    assert np.allclose(result.position, t.position)
    assert np.allclose(result.rotation, t.rotation)
    assert math.isclose(result.scale, t.scale)


def test_multiply_type_error():
    t = Transform()
    with pytest.raises(TypeError):
        t.multiply("not_a_transform")


def test_inverse_identity():
    t = Transform()
    inv = t.inverse()
    assert np.allclose(inv.position, np.zeros(3))
    assert np.allclose(inv.rotation, np.array([1, 0, 0, 0]))
    assert math.isclose(inv.scale, 1.0)


def test_inverse_roundtrip():
    t = Transform(
        position=np.array([1, 2, 3]), rotation=np.array([1, 0, 0, 0]), scale=2.0
    )
    inv = t.inverse()
    roundtrip = t.multiply(inv)
    np.testing.assert_allclose(roundtrip.position, np.zeros(3), atol=1e-6)
    np.testing.assert_allclose(roundtrip.rotation, np.array([1, 0, 0, 0]), atol=1e-6)
    assert math.isclose(roundtrip.scale, 1.0, abs_tol=1e-6)


def test_eq_and_ne():
    t1 = Transform()
    t2 = Transform()
    t3 = Transform(position=np.array([1, 0, 0]))
    assert t1 == t2
    assert not (t1 != t2)
    assert not (t1 == t3)
    assert t1 != t3


def test_hash():
    t1 = Transform()
    t2 = Transform()
    assert hash(t1) == hash(t2)
