# stardust

General tools and enhancements for Python.

Right now these docs cover the **tome** format: a self-describing container for
nested Python data built on top of HDF5.

```{toctree}
:maxdepth: 2
:caption: Tome

tome/index
tome/python
tome/format
```

```{toctree}
:maxdepth: 2
:caption: Serializer

serializer/unpacking
```

## Installation

```bash
pip install stardust-tools
```

## Quick look

```python
from stardust.tome import dict_to_tome, tome_to_dict

dict_to_tome({"run": 4, "trace": [1.0, 2.0, 3.0]}, "run4.tome")
data = tome_to_dict("run4.tome")
```

## Indices

* {ref}`genindex`
* {ref}`search`
