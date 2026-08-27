# Changelog

Notable changes to **stardust-tools**. This project follows
[Semantic Versioning](https://semver.org/).

Entries begin at 0.2.0; earlier releases predate this file.

## [0.2.0]

### Fixed

- **`Packable.unpack` no longer discards data when a field is missing.**

  It previously abandoned the entire object on the first field it could not
  resolve, and returned normally — the caller got a partly populated object and
  no indication anything had gone wrong. Because population runs in manifest
  order (scalars, then nested objects, then lists, then dicts), a single missing
  scalar prevented every collection below it from loading at all.

  The practical effect was that **adding one field to a serialized class
  silently emptied every file written before that addition**. A file holding two
  data series loaded as an object with none, reported as success.

  `unpack` now keeps the value `__init__` gave a field when the data does not
  contain it, and carries on. Genuinely unusable values are recorded and also do
  not abort the load, so a partial recovery comes with an honest account of what
  was lost rather than silence.

  See [Unpacking behaviour](docs/serializer/unpacking.md) for the full rationale.

### Added

- **`UnpackReport`**, returned by `unpack` and stored as `obj.unpack_report`.
  Lists every absent field and every value that could not be used, with dotted
  paths through nested objects (`axes.Ax0.legend_on`). Falsey when the load was
  incomplete, so `if not obj.unpack(data):` reads naturally.
- **`unpack(data, strict=True)`**, which raises `UnpackError` when a load was
  incomplete. `UnpackError.report` carries the details. Note that strict mode
  still completes the load before raising — it is not a return to the old
  abort-early behaviour, which lost data.
- `tests/test_unpack_tolerance.py`, covering the above, including the exact
  shape of the original bug (a scalar declared ahead of a collection).
- `algorithm.closest_indices`: Function for translating a list of desired 
  targets into indices of available values in a larger list.

### Changed

- Adding a field to a serialized class is now **backward compatible by
  default**. Files written before the field existed continue to load; the new
  field takes its default and is listed in the report. This is the property a
  long-lived file format needs, and it did not hold before.

### Upgrading from 0.1.0

No API changes are required. `unpack` still accepts the same arguments and can
still be called for its side effects; it now also returns a report.

Behaviour differs only where 0.1.0 was losing data:

| Data | 0.1.0 | 0.2.0 |
|---|---|---|
| Complete | loads fully, returns `None` | loads fully, returns a report where `ok` is true |
| Missing a field | **stops there**, later fields and all collections left empty, returns `None` | field keeps its default, load completes, report lists it |
| Missing a field, `strict=True` | n/a | load completes, then raises `UnpackError` |

If your code depended on a partly populated object after a failed unpack, it was
depending on data loss. Use `strict=True` to turn incomplete loads into errors.
