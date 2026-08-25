# Python guide

`stardust.tome` gives you two functions: one to write a tome, one to read it
back.

```python
from stardust.tome import dict_to_tome, tome_to_dict
```

## Writing and reading

```python
import numpy as np

data = {
    "run_id": 4,
    "operator": "gg",
    "passed": True,
    "sweep": np.linspace(0, 1, 1001),          # stored as a native HDF5 dataset
    "labels": ["cold", "warm", "hot"],
    "settings": {"gain": 2.5, "mode": "auto"}, # nested dicts become groups
    "events": [{"t": 0.1, "kind": "start"},    # list of dicts becomes a group
               {"t": 9.4, "kind": "stop"}],
}

dict_to_tome(data, "run4.tome")

restored = tome_to_dict("run4.tome")
assert restored["sweep"].dtype == data["sweep"].dtype
assert restored["passed"] is True
```

Both functions signal failure by return value rather than by raising:
`dict_to_tome` returns `False` on any write error, and `tome_to_dict` returns
`None` if the file cannot be opened or parsed. Diagnostic text is printed to
stdout. **Check the return value** — a failed write leaves a partially written
(or empty but valid) HDF5 file on disk.

```python
if not dict_to_tome(data, path):
    raise RuntimeError(f"could not write {path}")
```

### A list of dicts as the root

The root of a tome is usually a dict, but a `list[dict]` is also allowed —
useful for record-style data where the file *is* a table of measurements.

```python
records = [{"i": i, "sq": i * i} for i in range(100)]
dict_to_tome(records, "records.tome")

back = tome_to_dict("records.tome")   # -> list of 100 dicts, in order
```

Root lists must contain *only* dicts. `dict_to_tome([1, 2, 3], path)` fails and
returns `False` rather than silently mis-encoding the data.

### JSON backup on failure

Pass `use_json_backup=True` to have a failed write fall back to a `.json`
sidecar next to the intended output (the extension is swapped, so
`run4.tome` → `run4.json`). The backup is written with `json.dump(...,
default=str)`, so unserialisable values land in it as their `repr`-ish string
form. It is a diagnostic aid for recovering data from a crashed run, not a
second supported format — `tome_to_dict` cannot read it back.

### Verbose output

`show_detail=True` prints each key as it is written, plus a note when a value
falls through to the JSON encoder. It does not change what ends up in the file.

## Supported types

These types have dedicated handling on the write path and come back as the same
type on the read path:

:::{list-table}
:header-rows: 1
:widths: 30 30 40

* - Written
  - Read back as
  - Notes
* - `dict`
  - `dict`
  - Nested arbitrarily deep. Keys are stringified — see below.
* - `list[dict]`
  - `list[dict]`
  - Order preserved. Valid at the root or as any value.
* - `list[str]`
  - `list[str]`
  - Stored as a variable-length UTF-8 dataset.
* - `list` of numbers
  - `list`
  - Stored as a numeric array; read back as a plain Python list.
* - `numpy.ndarray` (numeric/bool)
  - `numpy.ndarray`
  - `dtype` and shape preserved, including 2-D and higher.
* - `numpy.ndarray` of strings
  - `numpy.ndarray` of `str`
  - **Flattened to 1-D.** See [Limitations](#limitations).
* - `str`
  - `str`
  - UTF-8, including non-BMP characters and the empty string.
* - `bool`
  - `bool`
  - Special-cased so `True` does not return as `1`.
* - `int`, `float`, `complex`
  - `int`, `float`, `complex`
  - numpy scalars (`np.int32`, `np.float64`, …) are also accepted, and read
    back as the corresponding Python scalar.
* - anything JSON-serialisable
  - its JSON equivalent
  - Fallback path: `None`, tuples, ragged/mixed lists. See below.
:::

### The JSON fallback

Any value that matches no branch above is JSON-encoded into a single string
dataset. This is what makes `None` and tuples work, and it is applied
per-element for lists that numpy cannot turn into a clean numeric array:

```python
dict_to_tome({
    "nothing":  None,           # -> JSON "null"
    "pair":     (1, 2),         # -> JSON "[1, 2]"     (reads back as a list!)
    "mixed":    [1, "a", None], # -> per-element JSON
    "ragged":   [[1, 2], [3]],  # -> per-element JSON
}, path)
```

The fallback is only as capable as `json.dumps`. Values it cannot encode —
`set`, `bytes`, dataclass instances, custom objects — cause the whole write to
fail and return `False`.

## Limitations

The conversions below are inherent to the format. None of them raise; they just
mean what you read is not identical to what you wrote.

**Dict keys become strings.** HDF5 node names are strings, and keys are written
with `str(k)`. `{1: "one"}` reads back as `{"1": "one"}`. Keys that collide
after stringification (`{1: "a", "1": "b"}`) make the write fail.

**Keys containing `/` create nested groups.** `/` is the HDF5 path separator, so
`{"a/b": 1}` writes a group `a` containing `b`, and reads back as
`{"a": {"b": 1}}`. An empty-string key fails the write outright. Avoid `/` and
`.` in keys.

**Tuples become lists.** JSON has no tuple type, and the fallback is what
handles tuples.

**String arrays lose their shape.** A 2-D `numpy` array of strings is flattened
to 1-D on write and read back 1-D. Numeric arrays keep their full shape.

**Numeric lists come back as lists, not arrays** — and via a numpy round trip,
so `[1, 2, 3]` returns as `int64`-derived Python ints, and a list mixing ints
and floats returns as all floats. If you need an exact type, write a
`numpy.ndarray`.

**An empty list is untyped.** `[]` is stored as an empty `float64` dataset and
reads back as `[]`, regardless of what the list would have held.

**No `bytes` support.** Binary blobs are not handled; the write fails. Encode
them yourself (e.g. base64 into a `str`) if you need them.

**No streaming, chunking, or compression.** Datasets are written whole and with
default HDF5 settings, and the entire file is materialised in memory on read.
Tomes are for "a run's worth of data", not for terabyte archives.

**No append or partial read.** `dict_to_tome` truncates the target file (`'w'`
mode) and `tome_to_dict` reads everything. To touch part of a tome, open it
with `h5py` directly — see the [format specification](format.md).

**Not concurrency-safe.** No locking is performed. Do not write a tome that
another process may be reading.

## API reference

```{eval-rst}
.. automodule:: stardust.tome
   :members: dict_to_tome, tome_to_dict
```
