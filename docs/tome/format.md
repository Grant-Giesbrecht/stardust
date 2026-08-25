# Format specification

This page describes the on-disk tome format in implementation-independent
terms, so that readers and writers can be built in other languages. It
describes the format as produced by stardust 0.1.0.

## 1. Container

A tome is an ordinary **HDF5 file**. No custom bytes, headers, or superblock
extensions are used, and no HDF5 features beyond groups, datasets, scalar and
simple dataspaces, attributes, and variable-length strings are required.

* Any HDF5 library version that can read a file written by libhdf5 1.10+ will
  do. Contiguous, uncompressed, unchunked datasets are what a stardust writer
  produces; a reader should not assume this, since HDF5 makes layout
  transparent anyway.
* File extension: `.tome` by convention; `.h5` and `.hdf5` are equally valid.
* Every string in the format — dataset payloads and attribute values alike — is
  **UTF-8**.

## 2. Type tagging

Every node that a tome writer creates carries the attribute:

```
__pytype__ : string
```

This is the sole mechanism by which structure is recovered. The **root group**
(`/`) carries it too, and its value determines the type of the whole document.

Two auxiliary attributes appear on some datasets:

:::{list-table}
:header-rows: 1
:widths: 22 78

* - Attribute
  - Meaning
* - `dtype`
  - The element type of an array-like dataset, as a NumPy dtype name
    (`"int64"`, `"float32"`, `"complex128"`, `"bool"`, …) or the literal
    `"str"`. Informational for restoring an exact numeric width; a reader in a
    language without NumPy dtypes may use the HDF5 datatype instead.
* - `elem_encoding`
  - Present with the value `"json"` only. Marks a string dataset whose
    *elements are individually JSON documents* rather than plain text.
:::

## 3. Type table

`__pytype__` values, the node kind each applies to, and how the payload is
stored:

:::{list-table}
:header-rows: 1
:widths: 18 12 70

* - `__pytype__`
  - Node
  - Payload
* - `dict`
  - group
  - Zero or more child nodes. Each child's link name is the dict key; each
    child is itself tagged.
* - `list_of_dicts`
  - group
  - Child **groups** named `"0"`, `"1"`, `"2"`, … each tagged `dict`. The
    numeric value of the name is the list index. Names are *not* zero-padded,
    so a reader MUST order them by integer value, not lexicographically.
* - `str`
  - dataset
  - Scalar dataspace, variable-length UTF-8 string.
* - `bool`
  - dataset
  - Scalar integer; `0` = false, any nonzero = true.
* - `int`, `float`, `complex`, or a NumPy scalar type name (`int64`, `float32`, …)
  - dataset
  - Scalar dataspace holding the number in its native HDF5 datatype. Complex
    numbers use the HDF5 compound type `{double r; double i;}` that h5py emits
    for `complex128`. A reader SHOULD dispatch on the HDF5 datatype here rather
    than on the tag, since the tag is simply the writer's Python type name and
    is open-ended.
* - `ndarray`
  - dataset
  - **Numeric/bool:** simple dataspace of any rank, native element type; the
    `dtype` attribute repeats it. **String:** 1-D variable-length UTF-8 string
    dataset with `dtype = "str"` (the source array is flattened; its original
    shape is not recorded).
* - `list`
  - dataset
  - 1-D (or higher, if the source list was rectangular and nested) dataset.
    Numeric lists use the native element type with the `dtype` attribute set.
    String lists use variable-length UTF-8 with `dtype = "str"`. If
    `elem_encoding = "json"` is also present, each string element is a JSON
    document to be decoded individually.
* - `json`
  - dataset
  - Scalar dataspace, variable-length UTF-8 string containing one JSON
    document that encodes the entire value.
:::

An empty Python list is stored as a zero-length dataset (a stardust writer uses
`float64`); it carries no information about the intended element type.

## 4. Document root

The root group's `__pytype__` is one of:

* `"dict"` — the document is a mapping; the root group's children are its
  entries.
* `"list_of_dicts"` — the document is a sequence; the root group's children are
  groups named `"0"`, `"1"`, … as in the type table.

Any other value, or a missing attribute, SHOULD be treated as `"dict"` by a
lenient reader.

## 5. Writer algorithm

A conforming writer dispatches on the value's type **in this order**. The order
matters: several branches overlap, and an implementation that reorders them
will produce different (though still readable) files.

1. **mapping** → create a group, tag `dict`, recurse over its entries with the
   key stringified.
2. **non-empty sequence whose elements are all mappings** → create a group, tag
   `list_of_dicts`, write each element as a group named by its index.
3. **non-empty sequence whose elements are all strings** → create a 1-D
   variable-length UTF-8 dataset, tag `list`, set `dtype = "str"`.
   *This must precede the general sequence branch*, or the string type is lost.
4. **n-dimensional array** → tag `ndarray`. String arrays are flattened to 1-D
   variable-length UTF-8 with `dtype = "str"`; everything else is written with
   its native element type and `dtype` set to that type's name.
5. **any other sequence** → attempt to convert to a rectangular numeric array.
   * If that succeeds, write it natively, tag `list`, set `dtype`.
   * If it fails or yields a non-numeric element type (ragged, mixed types),
     JSON-encode **each element** into a variable-length UTF-8 dataset, tag
     `list`, and set `dtype = "str"` and `elem_encoding = "json"`.
6. **string** → scalar variable-length UTF-8 dataset, tag `str`.
7. **boolean** → scalar integer `0`/`1`, tag `bool`. *This must precede the
   numeric branch* in languages where booleans are a numeric subtype.
8. **number** (integer, float, complex) → scalar dataset in the native type,
   tag with the type's name.
9. **anything else** → JSON-encode the whole value into a scalar
   variable-length UTF-8 dataset, tag `json`. If it cannot be JSON-encoded, the
   write fails.

A write failure is expected to abort the whole document rather than skip the
offending value.

## 6. Reader algorithm

Given a node:

1. **If it is a group:** tag `list_of_dicts` → return a sequence built from
   children `"0"`, `"1"`, … ordered by integer name. Otherwise → return a
   mapping of link name to the decoded child.
2. **If it is a dataset**, switch on `__pytype__`:
   * `str` → decode the scalar as UTF-8 text.
   * `bool` → truth value of the scalar.
   * `ndarray` → if the element type is a string type, decode every element to
     text and return a 1-D string array; otherwise return the array, coerced to
     the `dtype` attribute if the host language distinguishes widths.
   * `list` → if the element type is a string type: decode each element, then,
     if `elem_encoding == "json"`, JSON-decode each decoded element. Otherwise
     return the array as a plain sequence.
   * `json` → decode the scalar as UTF-8, then parse it as JSON.
   * anything else (including a missing tag) → return the value natively:
     decode byte strings as UTF-8, convert arrays to sequences, and unwrap
     one-element/scalar numeric types to a plain number.

The last clause is what lets a reader open a plain HDF5 file that was never
written by a tome writer, and get something sensible back.

Readers SHOULD be lenient: an unrecognised `__pytype__` is a hint, not an
error, and the HDF5 datatype is always available as a fallback.

## 7. Worked example

```python
{
    "run_id": 4,
    "passed": True,
    "note": "ok",
    "sweep": np.array([0.0, 0.5, 1.0]),
    "labels": ["cold", "hot"],
    "mixed": [1, "a", None],
    "nothing": None,
    "settings": {"gain": 2.5},
    "events": [{"t": 0.1}, {"t": 9.4}],
}
```

produces this structure (attributes in braces):

```text
/                       {__pytype__: "dict"}
├── run_id              dataset  scalar int64        {__pytype__: "int"}
├── passed              dataset  scalar int64  (=1)  {__pytype__: "bool"}
├── note                dataset  scalar vlen-utf8    {__pytype__: "str"}
├── sweep               dataset  (3,) float64        {__pytype__: "ndarray", dtype: "float64"}
├── labels              dataset  (2,) vlen-utf8      {__pytype__: "list",    dtype: "str"}
├── mixed               dataset  (3,) vlen-utf8      {__pytype__: "list",    dtype: "str",
│                                ["1", "\"a\"", "null"]  elem_encoding: "json"}
├── nothing             dataset  scalar vlen-utf8    {__pytype__: "json"}
│                                "null"
├── settings            group                        {__pytype__: "dict"}
│   └── gain            dataset  scalar float64      {__pytype__: "float"}
└── events              group                        {__pytype__: "list_of_dicts"}
    ├── 0               group                        {__pytype__: "dict"}
    │   └── t           dataset  scalar float64      {__pytype__: "float"}
    └── 1               group                        {__pytype__: "dict"}
        └── t           dataset  scalar float64      {__pytype__: "float"}
```

Inspect any real tome the same way with `h5dump -A file.tome` or
`h5ls -vr file.tome`.

## 8. Constraints and reserved names

* **Link names.** Keys become HDF5 link names. `/` is the HDF5 path separator,
  so a key containing it silently creates intermediate groups and changes the
  document's shape; `.` is also reserved by HDF5; an empty name is invalid.
  Writers are not required to escape these, and a stardust writer does not.
* **Duplicate keys.** Two source keys that stringify identically collide on the
  same link name and MUST cause the write to fail rather than overwrite.
* **Index names.** Under a `list_of_dicts` group, names other than
  non-negative decimal integers are undefined; a reader may reject them.
* **Reserved attributes.** `__pytype__`, `dtype`, and `elem_encoding` are
  reserved on nodes created by a tome writer. User data is never stored in
  attributes, only in datasets and group structure.
* **No user attributes.** There is currently no way to attach arbitrary
  metadata to a node; put it in the data.

## 9. Versioning

The format carries **no version attribute**. Files written by stardust 0.1.0
are identified only by the presence of `__pytype__` on the root group.

Implementers should therefore:

* treat an unrecognised `__pytype__` value as "decode natively" rather than as
  an error, and
* expect that a future format revision will introduce a root-level version
  attribute; a reader that ignores unknown root attributes today will keep
  working.

## 10. Conformance checklist

A reader implementation is complete when it handles:

* [ ] both root types (`dict`, `list_of_dicts`)
* [ ] numeric ordering of `list_of_dicts` index names past index 9
* [ ] `bool` distinguished from integer
* [ ] variable-length UTF-8 strings, scalar and 1-D, including non-BMP
      characters and the empty string
* [ ] multi-dimensional numeric arrays with dtype restored from `dtype`
* [ ] `elem_encoding = "json"` per-element decoding
* [ ] scalar `json` payloads, including `null`
* [ ] complex numbers (HDF5 compound `{r, i}`)
* [ ] zero-length datasets (empty lists/arrays)
* [ ] untagged nodes, decoded natively
