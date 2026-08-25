# The tome format

A **tome** is an HDF5 file that stores a nested Python `dict` (or a list of
dicts) in a self-describing way: every group and dataset carries a
`__pytype__` attribute recording the Python type it came from, so a read
returns the same shapes and types that were written rather than a pile of raw
HDF5 nodes.

It exists to sit between two unhappy alternatives:

* **JSON** — round-trips types poorly, has no binary array support, and is slow
  and bulky for large numeric data.
* **Raw HDF5** — excellent for arrays, but has no concept of `bool`, `None`,
  tuples, lists of dicts, or heterogeneous lists, so every project reinvents
  its own conventions for encoding them.

A tome is *just an HDF5 file*. Any HDF5 reader in any language can open it and
see the data; the `__pytype__` attributes are what let a reader reconstruct the
original Python-side structure exactly.

## Which page do I want?

:::{list-table}
:header-rows: 1
:widths: 30 70

* - Page
  - Read it if…
* - [Python guide](python.md)
  - You want to read and write tomes from Python: the API, the supported
    types, and the conversions and limitations to be aware of.
* - [Format specification](format.md)
  - You want to read or write tomes from another language, or you need to know
    exactly what bytes and attributes end up in the file.
:::

## Conventions

* File extension: `.tome` by convention. Nothing in the code enforces it —
  `.h5` and `.hdf5` work identically.
* The format is versionless as of stardust 0.1.0. There is no format-version
  attribute in the file; see [Format specification § Versioning](format.md#9-versioning).

```{toctree}
:hidden:

python
format
```
