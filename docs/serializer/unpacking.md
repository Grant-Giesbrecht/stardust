# Unpacking behaviour

`Packable.unpack` reconstructs an object from a dict produced by `pack()`. Its
central design decision is that **a missing field is not an error** — it keeps
whatever value `__init__` gave it, and the load continues.

That is deliberate, and it is load-bearing. This page explains what the contract
is, why it is shaped that way, and what it means for evolving a serialized
class over time.

## The contract

```python
report = obj.unpack(data)
```

For each entry in the object's manifests, in order — scalars (`manifest`),
nested objects (`obj_manifest`), lists (`list_manifest`), then dicts
(`dict_manifest`):

* **Present and usable** → assigned.
* **Absent from `data`** → the value from `__init__` is kept, and the field name
  is recorded in `report.missing`.
* **Present but unusable** (cannot be assigned; a nested object that cannot be
  interpreted) → recorded in `report.errors`, and the load continues.

`unpack` never abandons an object partway through. Whatever can be recovered is
recovered, and the report says what could not be.

Fields in `data` that the object does not declare are ignored. An older reader
can therefore read a newer file, provided the fields it needs are still there.

## The report

`unpack` returns an `UnpackReport`, also stored as `obj.unpack_report`:

```python
report = obj.unpack(data)

report.ok        # True when nothing was missing and nothing failed
report.missing   # ['legend_on', 'style.title_font.family', ...]
report.errors    # [('items.a.value', 'reason'), ...]

if not report:                       # falsey when incomplete
    print(f"loaded with gaps: {report}")
```

Paths are dotted and index-qualified, so a gap deep in a tree is identifiable:
`axes.Ax0.legend_on`, `items[3].value`.

Tolerating absence is only safe if the caller can discover what was tolerated.
The report is that channel — without it, an incomplete load is indistinguishable
from a complete one, which is the failure this whole design exists to prevent.

## Strict mode

When a caller needs a load to be all-or-nothing:

```python
try:
    obj.unpack(data, strict=True)
except UnpackError as e:
    print(e.report.missing)
```

Strict mode still **completes** the load before raising. It is not a return to
aborting early — it changes how an incomplete load is *reported*, not how much
of it happens.

## Why absence is tolerated

The rule exists because of a specific failure, which is worth recording so it is
not reintroduced.

`unpack` used to abandon the whole object on the first field it could not
resolve, and return normally. Two properties combined badly:

1. **It was silent to the caller.** The failure went to a log; `unpack` returned
   `None` either way. Nothing propagated. A caller could not distinguish a
   complete load from a 5%-complete one without inspecting the result.

2. **It failed early and stopped.** Because population runs scalars → nested
   objects → lists → dicts, the abort happened *before* the collections were
   read. The loss was not proportional to the problem: one absent boolean could
   cost every data point in the file.

The case that surfaced it, in GrAF (a plot archive format built on stardust):

```
manifest:      axis_type, position, span, relative_size, grid_on,
               legend_on,          <-- newly added field
               legend_location, title
obj_manifest:  x_axis, y_axis_L, y_axis_R, z_axis     <-- the axis scales
dict_manifest: traces, surfaces                        <-- all the data
```

Adding the cosmetic `legend_on` boolean meant older files no longer contained
it. Reading one:

* `setattr(self, 'legend_on', data['legend_on'])` raised `KeyError`
* the error was logged and `unpack` returned
* the four scales were never read
* `traces` and `surfaces` were never read

A file containing two traces of forty points each loaded as a figure with
**zero traces**, reported as a successful read. The only signal was a log line
that application code had no reason to be watching.

A one-line cosmetic addition silently destroyed all of the payload on load.

## What this means for evolving a class

The reason the current behaviour matters is not that missing fields are common —
it is that **adding a field is the ordinary way a serialized class grows**, and
it must not invalidate existing files.

Adding a field is safe:

```python
def __init__(self, log=None):
    super().__init__(log)
    self.existing = 0
    self.new_thing = "sensible default"     # <- files without it get this

def set_manifest(self):
    self.manifest.append("existing")
    self.manifest.append("new_thing")
```

Old files load; `new_thing` takes its default and appears in
`report.missing`. Nothing else is affected.

Two things to keep in mind:

* **Give every field a meaningful default in `__init__`.** That default is what
  old files will get, so it should be the value that best represents "this file
  predates the field" — not merely a placeholder. Prefer a default that
  reproduces how such a file previously behaved over one that invents new
  behaviour.

* **Removing or renaming a field is still breaking.** Tolerance covers absence,
  not disappearance: old files carrying the removed field will load (the extra
  key is ignored), but its value is dropped. If the value matters, read it and
  translate it before it is lost, or provide a tool that rewrites affected files.

### Verifying a load

For formats where losing data silently is unacceptable, check what came back
against what the document contained. GrAF, for example, compares the number of
axes, traces and surfaces it produced against the raw document and raises if
they differ. That is cheap defence in depth, and worth having even though
`unpack` no longer abandons objects.

## Do not restore abort-on-missing

The lenient behaviour can look sloppy at a glance, and the temptation to
"tighten it up" is the exact path back to the bug above. If strictness is wanted
for a particular call, it already exists — pass `strict=True`, which reports the
problem without throwing away the data.
