"""unpack() must tolerate missing fields rather than abandoning the object.

The behaviour these tests pin down was a silent data-loss bug: unpack() returned
on the first field it could not resolve, and because population runs
scalars -> nested objects -> lists -> dicts, one missing scalar prevented every
collection below it from loading. A caller saw a successful return and an empty
object. Adding a single field to a serialized class silently emptied every file
written before that addition.
"""
import pytest

from stardust.serializer import Packable, UnpackError, UnpackReport


class Leaf(Packable):
    def __init__(self, log=None):
        super().__init__(log)
        self.value = "default"

    def set_manifest(self):
        self.manifest.append("value")


class Container(Packable):
    """Mirrors the shape that caused the original bug: a scalar declared before
    the collections, so aborting on it loses everything."""

    def __init__(self, log=None):
        super().__init__(log)
        self.name = "unnamed"
        self.added_later = False        # the field that did not exist before
        self.child = Leaf()
        self.items = {}

    def set_manifest(self):
        self.manifest.append("name")
        self.manifest.append("added_later")
        self.obj_manifest.append("child")
        self.dict_manifest["items"] = Leaf()


def full_payload():
    return {
        "name": "real name",
        "added_later": True,
        "child": {"value": "child value"},
        "items": {"a": {"value": "A"}, "b": {"value": "B"}},
    }


class TestCompleteData:

    def test_everything_loads(self):
        c = Container()
        report = c.unpack(full_payload())
        assert c.name == "real name"
        assert c.child.value == "child value"
        assert len(c.items) == 2
        assert report.ok

    def test_report_is_stored_on_the_object(self):
        c = Container()
        c.unpack(full_payload())
        assert c.unpack_report.ok


class TestMissingScalarDoesNotDestroyTheRest:
    """The original failure, now the primary regression test."""

    def test_collections_still_load(self):
        data = full_payload()
        del data["added_later"]
        c = Container()
        c.unpack(data)
        assert len(c.items) == 2, "a missing scalar wiped out the collection"

    def test_nested_object_still_loads(self):
        data = full_payload()
        del data["added_later"]
        c = Container()
        c.unpack(data)
        assert c.child.value == "child value"

    def test_later_scalars_still_load(self):
        data = full_payload()
        del data["name"]
        c = Container()
        c.unpack(data)
        assert c.added_later is True

    def test_missing_field_keeps_its_default(self):
        data = full_payload()
        del data["added_later"]
        c = Container()
        c.unpack(data)
        assert c.added_later is False

    def test_missing_field_is_reported(self):
        data = full_payload()
        del data["added_later"]
        c = Container()
        report = c.unpack(data)
        assert not report.ok
        assert "added_later" in report.missing

    def test_report_is_falsey_when_incomplete(self):
        data = full_payload()
        del data["added_later"]
        assert not Container().unpack(data)


class TestNestedReporting:

    def test_missing_nested_field_is_reported_with_a_path(self):
        data = full_payload()
        del data["child"]["value"]
        report = Container().unpack(data)
        assert "child.value" in report.missing

    def test_missing_field_in_a_dict_element_is_pathed(self):
        data = full_payload()
        del data["items"]["a"]["value"]
        report = Container().unpack(data)
        assert "items.a.value" in report.missing

    def test_absent_collection_is_reported(self):
        data = full_payload()
        del data["items"]
        report = Container().unpack(data)
        assert "items" in report.missing
        assert Container().unpack(data) is not None

    def test_absent_nested_object_is_reported(self):
        data = full_payload()
        del data["child"]
        report = Container().unpack(data)
        assert "child" in report.missing


class TestStrictMode:

    def test_strict_raises_on_missing(self):
        data = full_payload()
        del data["added_later"]
        with pytest.raises(UnpackError):
            Container().unpack(data, strict=True)

    def test_strict_passes_on_complete_data(self):
        assert Container().unpack(full_payload(), strict=True).ok

    def test_error_carries_the_report(self):
        data = full_payload()
        del data["added_later"]
        with pytest.raises(UnpackError) as excinfo:
            Container().unpack(data, strict=True)
        assert "added_later" in excinfo.value.report.missing

    def test_error_message_names_the_field(self):
        data = full_payload()
        del data["added_later"]
        with pytest.raises(UnpackError, match="added_later"):
            Container().unpack(data, strict=True)


class TestExtraFieldsAreIgnored:
    """Forward compatibility: an old reader must cope with a newer file."""

    def test_unknown_fields_do_not_break_anything(self):
        data = full_payload()
        data["field_from_the_future"] = 42
        c = Container()
        report = c.unpack(data)
        assert report.ok
        assert c.name == "real name"


class TestEmptyData:

    def test_empty_dict_leaves_all_defaults(self):
        c = Container()
        report = c.unpack({})
        assert c.name == "unnamed"
        assert c.items == {}
        assert set(report.missing) >= {"name", "added_later", "child", "items"}

    def test_empty_dict_is_not_reported_as_ok(self):
        assert not Container().unpack({}).ok


class TestReportFormatting:

    def test_complete_report_reads_clearly(self):
        assert str(UnpackReport()) == "complete"

    def test_incomplete_report_lists_fields(self):
        r = UnpackReport()
        r.missing.append("legend_on")
        assert "legend_on" in str(r)

    def test_long_report_is_truncated(self):
        r = UnpackReport()
        r.missing.extend(f"field_{i}" for i in range(20))
        assert "more" in str(r)

    def test_absorb_prefixes_child_paths(self):
        parent, child = UnpackReport(), UnpackReport()
        child.missing.append("value")
        child.errors.append(("other", "bad"))
        parent.absorb(child, "child")
        assert parent.missing == ["child.value"]
        assert parent.errors == [("child.other", "bad")]

    def test_absorb_tolerates_none(self):
        r = UnpackReport()
        r.absorb(None, "child")
        assert r.ok
