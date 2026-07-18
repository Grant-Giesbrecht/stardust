from datetime import datetime, timezone

import numpy as np
import pytest

from stardust.serializer import (
    Serializable,
    Packable,
    to_serial_dict,
    from_serial_dict,
    dump_state,
    restore_state,
    valid_serialized_object,
    SERIALIZABLE_CLASS_REGISTRY,
)


# ------------------------------------------------------------------
# fixtures: Serializable subclasses (registered once at import time)
# ------------------------------------------------------------------

class Point(Serializable):
    __state_fields__ = ("x", "y")

    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return isinstance(other, Point) and self.x == other.x and self.y == other.y


class Line(Serializable):
    __state_fields__ = ("start", "end", "label")

    def __init__(self, start=None, end=None, label=""):
        self.start = start
        self.end = end
        self.label = label

    def __eq__(self, other):
        return (
            isinstance(other, Line)
            and self.start == other.start
            and self.end == other.end
            and self.label == other.label
        )


# ------------------------------------------------------------------
# Serializable: state dict machinery
# ------------------------------------------------------------------

def test_get_state_dict_returns_registered_fields():
    p = Point(1, 2)
    assert p.get_state_dict() == {"x": 1, "y": 2}


def test_from_state_dict_builds_object_without_init():
    p = Point.from_state_dict({"x": 9, "y": -3})
    assert p.x == 9 and p.y == -3


def test_subclass_auto_registered():
    assert "Point" in SERIALIZABLE_CLASS_REGISTRY
    assert SERIALIZABLE_CLASS_REGISTRY["Point"].cls is Point


# ------------------------------------------------------------------
# Serializable.serialize / deserialize — primitives and containers
# ------------------------------------------------------------------

def test_serialize_primitives_pass_through():
    assert Serializable.serialize(5) == 5
    assert Serializable.serialize("s") == "s"
    assert Serializable.serialize(None) is None
    assert Serializable.serialize(True) is True


def test_serialize_deserialize_list_and_dict():
    data = {"a": [1, 2, {"b": 3}], "c": (4, 5)}
    ser = Serializable.serialize(data)
    out = Serializable.deserialize(ser)
    assert out == {"a": [1, 2, {"b": 3}], "c": [4, 5]}  # tuple -> list


def test_serialize_deserialize_set():
    ser = Serializable.serialize({1, 2, 3})
    assert ser["__type__"] == "__set__"
    out = Serializable.deserialize(ser)
    assert out == {1, 2, 3}


def test_serialize_deserialize_naive_datetime():
    dt = datetime(2020, 1, 1, 12, 30, 45, 123456)
    ser = Serializable.serialize(dt)
    assert ser["__type__"] == "__datetime__"
    assert ser["naive"] is True
    out = Serializable.deserialize(ser)
    assert out == dt
    assert out.tzinfo is None


def test_serialize_deserialize_aware_datetime():
    dt = datetime(2020, 1, 1, 12, 30, 45, 123456, tzinfo=timezone.utc)
    ser = Serializable.serialize(dt)
    assert ser["naive"] is False
    assert ser["data"].endswith("Z")
    out = Serializable.deserialize(ser)
    assert out == dt
    assert out.tzinfo is not None


def test_serialize_deserialize_numpy_array():
    arr = np.arange(6).reshape(2, 3).astype(np.float32)
    ser = Serializable.serialize(arr)
    assert ser["__type__"] == "__ndarray__"
    out = Serializable.deserialize(ser)
    assert isinstance(out, np.ndarray)
    assert out.dtype == arr.dtype
    np.testing.assert_array_equal(out, arr)


def test_serialize_numpy_scalar_becomes_python_scalar():
    val = np.int64(42)
    ser = Serializable.serialize(val)
    assert ser == 42
    assert isinstance(ser, int)


# ------------------------------------------------------------------
# Registered-class round trip (nested custom objects)
# ------------------------------------------------------------------

def test_registered_class_roundtrip_simple():
    p = Point(3, 4)
    ser = Serializable.serialize(p)
    assert ser["__type__"] == "Point"
    out = Serializable.deserialize(ser)
    assert out == p


def test_registered_class_roundtrip_nested_object():
    line = Line(start=Point(0, 0), end=Point(1, 1), label="diag")
    ser = Serializable.serialize(line)
    out = Serializable.deserialize(ser)
    assert out == line
    assert isinstance(out.start, Point)


def test_registered_class_in_list_and_dict():
    data = {"points": [Point(1, 1), Point(2, 2)], "origin": Point(0, 0)}
    ser = Serializable.serialize(data)
    out = Serializable.deserialize(ser)
    assert out["points"] == [Point(1, 1), Point(2, 2)]
    assert out["origin"] == Point(0, 0)


def test_unregistered_class_type_returns_raw_dict(capsys):
    p = Point(1, 2)
    ser = Serializable.serialize(p)
    info = SERIALIZABLE_CLASS_REGISTRY.pop("Point")
    try:
        out = Serializable.deserialize(ser)
        captured = capsys.readouterr()
        assert "not in SERIALIZABLE_CLASS_REGISTRY" in captured.out
        assert out == ser  # falls through to "ordinary dict" handling
    finally:
        SERIALIZABLE_CLASS_REGISTRY["Point"] = info


def test_valid_serialized_object():
    p = Point(1, 2)
    ser = Serializable.serialize(p)
    assert valid_serialized_object(ser) is True
    assert valid_serialized_object({"foo": "bar"}) is False


# ------------------------------------------------------------------
# to_serial_dict / from_serial_dict
# ------------------------------------------------------------------

def test_to_serial_dict_from_serial_dict_roundtrip():
    line = Line(start=Point(0, 0), end=Point(5, 5), label="segment")
    packed = to_serial_dict(line)
    assert packed["__serializer_format__"]["name"] == "stardust.Serializable"
    restored = from_serial_dict(packed)
    assert restored == line


# ------------------------------------------------------------------
# dump_state / restore_state — file round trip
# ------------------------------------------------------------------

def test_dump_state_restore_state_roundtrip(tmp_path):
    line = Line(start=Point(1, 2), end=Point(3, 4), label="l")
    path = str(tmp_path / "state.json")
    dump_state(line, path)
    restored = restore_state(path)
    assert restored == line


# ------------------------------------------------------------------
# Packable
# ------------------------------------------------------------------

class PackableLeaf(Packable):
    def set_manifest(self):
        self.manifest = ["val"]
        self.val = 0


class PackableContainer(Packable):
    def set_manifest(self):
        self.manifest = ["name"]
        self.obj_manifest = ["child"]
        self.list_manifest = {"items": PackableLeaf()}
        self.dict_manifest = {"lookup": PackableLeaf()}
        self.name = ""
        self.child = PackableLeaf()
        self.items = []
        self.lookup = {}


def test_packable_pack_unpack_roundtrip():
    c = PackableContainer()
    c.name = "root"
    c.child.val = 1
    leaf_a = PackableLeaf()
    leaf_a.val = 10
    leaf_b = PackableLeaf()
    leaf_b.val = 20
    c.items = [leaf_a, leaf_b]
    c.lookup = {"a": leaf_a}

    packed = c.pack()
    assert packed == {
        "name": "root",
        "child": {"val": 1},
        "items": [{"val": 10}, {"val": 20}],
        "lookup": {"a": {"val": 10}},
    }

    c2 = PackableContainer()
    c2.unpack(packed)
    assert c2.name == "root"
    assert c2.child.val == 1
    assert [x.val for x in c2.items] == [10, 20]
    assert c2.lookup["a"].val == 10


def test_packable_leaf_pack_unpack():
    leaf = PackableLeaf()
    leaf.val = 99
    packed = leaf.pack()
    assert packed == {"val": 99}

    leaf2 = PackableLeaf()
    leaf2.unpack(packed)
    assert leaf2.val == 99
