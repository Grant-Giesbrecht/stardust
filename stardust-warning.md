# Hazard: `Packable.unpack` silently discards data

**Status:** FIXED in 0.2.0 · **Affects:** `stardust/serializer.py`, `Packable.unpack`
**Severity:** high — causes silent, unbounded data loss with no error raised
**Found:** 2026-08-27, while adding one field to a class in GrAF

---

## Summary

`Packable.unpack` aborts the entire object on the **first** field it cannot
resolve, and returns normally. The caller receives a partially populated object
and no indication that anything went wrong.

Because `unpack` populates `manifest` first, then `obj_manifest`, then
`list_manifest`, then `dict_manifest`, a single missing **scalar** field prevents
every nested object and collection below it from loading at all. The scalar is
usually trivial. What is lost with it usually is not.

## The code

`stardust/serializer.py`, in `Packable.unpack`:

```python
for mi in self.manifest:
    try:
        setattr(self, mi, data[mi])
    except Exception as e:
        self.log.error(f"Failed to unpack item in object of type '{type(self).__name__}'. ({e})")
        return                      # <-- abandons the whole object
```

The same `return`-on-first-failure appears in the `obj_manifest`,
`list_manifest`, and `dict_manifest` loops that follow.

Two properties combine to make this dangerous:

1. **It is silent to the caller.** The failure goes to a `LogPile` and `unpack`
   returns `None` either way. Nothing propagates. A caller cannot distinguish a
   complete load from a 5%-complete one without inspecting the result.
2. **It fails early and stops.** The abort happens *before* the collections are
   read, so the loss is not proportional to the problem. One absent boolean can
   cost every data point in the file.

## How it actually bit

GrAF stores plots and their data. `Axis` has this manifest order:

```
manifest:      axis_type, position, span, relative_size, grid_on,
               legend_on,          <-- newly added field
               legend_location, title
obj_manifest:  x_axis, y_axis_L, y_axis_R, z_axis     <-- the axis scales
dict_manifest: traces, surfaces                        <-- ALL THE DATA
```

Adding the cosmetic `legend_on` boolean meant older files no longer contained
it. Reading one of those files:

- `setattr(self, 'legend_on', data['legend_on'])` raises `KeyError`
- the error is logged, `unpack` returns
- `x_axis`, `y_axis_L`, `y_axis_R`, `z_axis` are never read
- `traces` and `surfaces` are never read

The observed result was a file containing two traces of 40 points each loading
as a figure with **zero traces**, reported as a successful read. The only signal
was a line in the log, which application code had no reason to be watching.

A one-line cosmetic addition silently destroyed 100% of the scientific data on
load. For an archive format — where the entire promise is that the data outlives
the tool that wrote it — this is the worst available failure mode.

## Why this is not just "the caller's problem"

It is reasonable for a serializer to be strict, and reasonable for it to be
lenient. What is not reasonable is being lenient **to the caller** while being
strict **about the data**: reporting success while returning less than was
asked for.

The current behaviour also makes ordinary schema evolution unsafe. Adding an
optional field to a class is normally backward compatible. Here it is a breaking
change for every file already written, and the breakage is invisible.

## Resolution (0.2.0)

Fixed by suggestions 1-3 below, taken together. `unpack` now:

* keeps the `__init__` default for any absent field and carries on;
* records every absent field and every unusable value in an `UnpackReport`,
  returned from `unpack` and stored as `self.unpack_report`, with dotted paths
  for nested objects (`axes.Ax0.legend_on`);
* never aborts, so a failure early in the manifest can no longer prevent the
  collections from loading;
* accepts `strict=True` to raise `UnpackError` when a load was incomplete.

Adding a field to a serialized class is now backward compatible by default,
which is the property a long-lived file format needs. Suggestion 4
(`optional_manifest`) was not implemented: with defaults filled and a report
returned, per-field optionality declarations were not needed.

`tests/test_unpack_tolerance.py` covers it, including the exact shape of the
original bug (a scalar declared before a collection).

## Suggested fixes, in order of preference

### 1. Fill defaults for missing fields; never abort

`Packable` subclasses set every attribute in `__init__`, so a missing key
already has a sensible value waiting. Leave it in place and carry on:

```python
missing = []
for mi in self.manifest:
    if mi in data:
        setattr(self, mi, data[mi])
    else:
        missing.append(mi)          # keep the __init__ default
self._unpack_missing = missing
```

This makes additive schema changes automatically backward compatible, which is
the property a long-lived file format needs. Genuinely malformed values (wrong
type, unreadable nested object) should still raise.

### 2. Return a result the caller cannot ignore

Whether or not defaults are filled, `unpack` should report. Either return a
status object listing what was missing, or raise a dedicated exception
(`UnpackError`) carrying the field name and the type it was unpacking. A silent
`return` is the core of the problem; logging is not reporting.

### 3. Continue rather than abort

Even keeping strictness, do not let a scalar failure prevent the collections
from loading. Collect every failure and report them together at the end. Losing
one field is recoverable; losing the payload because of one field is not.

### 4. Offer explicit optionality

An `optional_manifest`, or per-field defaults in `set_manifest`, would let a
class state which fields may be absent — turning the current implicit,
catastrophic behaviour into an explicit, bounded one.

## What GrAF did in the meantime

Before the fix, GrAF worked around this in two ways. The first is now removable;
the second is kept as cheap defence in depth:

1. **Migrate before unpacking.** Old files are upgraded to the current schema in
   memory, so no field is ever missing. Notably, wrapping `unpack` in a
   `try/except` does **not** work — the failure is not an exception, and the
   partial load is the problem.

2. **Verify after unpacking.** After a load, GrAF compares the number of axes,
   traces, and surfaces it produced against what the raw document actually
   contained, and raises if they differ:

   ```python
   if len(got) != len(expected):
       raise GrafFormatError(
           f"axis '{key}' contains {len(expected)} {collection} but only "
           f"{len(got)} could be loaded. Data would have been silently lost."
       )
   ```

Every consumer of `stardust` needs some version of this, and most will not know
to write it. That is the argument for fixing it upstream.

## Reproducing

```python
from stardust.serializer import Packable

class Thing(Packable):
    def __init__(self, log=None):
        super().__init__(log)
        self.new_field = False       # added after some files were written
        self.payload = {}
    def set_manifest(self):
        self.manifest.append("new_field")
        self.dict_manifest["payload"] = Item()

t = Thing()
t.unpack({"payload": {"a": {...}, "b": {...}}})   # no 'new_field'

assert t.payload == {}     # passes: the payload is gone
                           # no exception was raised
```
