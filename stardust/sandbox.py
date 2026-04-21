import h5py
import numpy as np
import json
import time
from typing import Any

# ------------------------------------------------------------------
# Sentinel attribute written alongside every dataset/group so that
# hdf_to_dict knows how to reconstruct the original Python type.
# ------------------------------------------------------------------
_ATTR_TYPE = "__pytype__"

def _write_tome_value(fh: h5py.Group, key: str, value: Any, show_detail: bool = False) -> None:
	"""
	Write a single key/value pair into an open HDF5 group.
	Dispatches on the Python type of `value`.
	"""

	if show_detail:
		print(f"  Writing key={key!r}, type={type(value).__name__}")

	# ---- dict -------------------------------------------------------
	if isinstance(value, dict):
		grp = fh.create_group(key)
		grp.attrs[_ATTR_TYPE] = "dict"
		_write_tome_dict(grp, value, show_detail=show_detail)

	# ---- list of dicts → indexed subgroups -------------------------
	elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
		grp = fh.create_group(key)
		grp.attrs[_ATTR_TYPE] = "list_of_dicts"
		for i, item in enumerate(value):
			sub = grp.create_group(str(i))
			sub.attrs[_ATTR_TYPE] = "dict"
			_write_tome_dict(sub, item, show_detail=show_detail)

	# ---- numpy array ------------------------------------------------
	elif isinstance(value, np.ndarray):
		ds = fh.create_dataset(key, data=value)
		ds.attrs[_ATTR_TYPE] = "ndarray"
		ds.attrs["dtype"] = str(value.dtype)

	# ---- plain list (convert to numpy for storage) -----------------
	elif isinstance(value, list):
		arr = _list_to_array(value)
		ds = fh.create_dataset(key, data=arr)
		ds.attrs[_ATTR_TYPE] = "list"
		ds.attrs["dtype"] = str(arr.dtype)

	# ---- scalar str ------------------------------------------------
	elif isinstance(value, str):
		ds = fh.create_dataset(key, data=value.encode("utf-8"))
		ds.attrs[_ATTR_TYPE] = "str"

	# ---- scalar bool (check before int — bool is subclass of int) --
	elif isinstance(value, bool):
		ds = fh.create_dataset(key, data=int(value))
		ds.attrs[_ATTR_TYPE] = "bool"

	# ---- scalar numeric (int, float, complex) ----------------------
	elif isinstance(value, (int, float, complex, np.integer, np.floating)):
		ds = fh.create_dataset(key, data=value)
		ds.attrs[_ATTR_TYPE] = type(value).__name__

	# ---- fallback: try JSON-encoding the object --------------------
	else:
		encoded = json.dumps(value)
		ds = fh.create_dataset(key, data=encoded.encode("utf-8"))
		ds.attrs[_ATTR_TYPE] = "json"
		if show_detail:
			print(f"    Fell back to JSON encoding for type {type(value).__name__}")


def _write_tome_dict(fh: h5py.Group, data: dict, show_detail: bool = False) -> None:
	"""Iterate a dict and write each entry into the HDF5 group `fh`."""
	for k, v in data.items():
		_write_tome_value(fh, str(k), v, show_detail=show_detail)


def _list_to_array(lst: list) -> np.ndarray:
	"""
	Convert a flat list to a numpy array with a sensible dtype.
	Falls back to variable-length UTF-8 strings if the list contains str.
	"""
	if not lst:
		return np.array([])
	if all(isinstance(x, str) for x in lst):
		dt = h5py.string_dtype(encoding="utf-8")
		return np.array(lst, dtype=object)   # h5py handles vlen str from object arrays
	try:
		return np.array(lst)
	except ValueError:
		# Ragged or mixed — store as JSON-encoded strings
		return np.array([json.dumps(x) for x in lst])


# ------------------------------------------------------------------

def dict_to_tome(root_data: dict,
				save_file: str,
				use_json_backup: bool = False,
				show_detail: bool = False) -> bool:
	"""
	Write a Python dictionary to an HDF5 file, using the tome format.

	Supported value types
	---------------------
	- dict                       → HDF5 group
	- list[dict]                 → HDF5 group of indexed subgroups
	- np.ndarray                 → HDF5 dataset (dtype preserved)
	- list                       → HDF5 dataset (converted to ndarray)
	- str                        → HDF5 scalar dataset (UTF-8 bytes)
	- bool / int / float         → HDF5 scalar dataset
	- anything else              → JSON-encoded bytes dataset (fallback)

	Parameters
	----------
	root_data       : dict to serialise
	save_file       : path to output .hdf5 / .h5 file
	use_json_backup : if True and HDF5 write fails, saves a .json sidecar
	show_detail     : verbose logging

	Returns
	-------
	True on success, False on failure.
	"""
	try:
		with h5py.File(save_file, 'w') as fh:
			fh.attrs[_ATTR_TYPE] = "dict"
			_write_tome_dict(fh, root_data, show_detail=show_detail)
		return True

	except Exception as e:
		print(f"Failed to write HDF file: {e}")
		if use_json_backup:
			backup = save_file.rsplit(".", 1)[0] + ".json"
			try:
				with open(backup, "w") as f:
					json.dump(root_data, f, indent=4, default=str)
				print(f"JSON backup written to {backup}")
			except Exception as je:
				print(f"JSON backup also failed: {je}")
		return False


# ------------------------------------------------------------------

def _read_tome_value(node) -> Any:
	"""
	Reconstruct a Python value from an HDF5 node (group or dataset),
	using the __pytype__ attribute written by dict_to_hdf.
	"""
	pytype = node.attrs.get(_ATTR_TYPE, "")

	# ---- groups ----------------------------------------------------
	if isinstance(node, h5py.Group):
		if pytype == "list_of_dicts":
			# Keys are "0", "1", "2", ... — sort numerically
			return [_read_tome_dict(node[k]) for k in sorted(node.keys(), key=int)]
		else:  # plain dict (or unlabelled legacy group)
			return _read_tome_dict(node)

	# ---- datasets --------------------------------------------------
	raw = node[()]

	if pytype == "str":
		return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

	if pytype == "bool":
		return bool(raw)

	if pytype == "ndarray":
		arr = np.array(raw)
		dtype_str = node.attrs.get("dtype", "")
		if dtype_str:
			try:
				arr = arr.astype(dtype_str)
			except Exception:
				pass
		return arr

	if pytype == "list":
		arr = np.array(raw)
		# Decode bytes → str for string arrays
		if arr.dtype.kind in ('S', 'O'):
			lst = [x.decode("utf-8") if isinstance(x, bytes) else x for x in arr.flat]
		else:
			lst = arr.tolist()
		return lst

	if pytype == "json":
		payload = raw.decode("utf-8") if isinstance(raw, bytes) else raw
		return json.loads(payload)

	# ---- numeric scalars and unlabelled legacy data ----------------
	if isinstance(raw, (bytes, np.bytes_)):
		return raw.decode("utf-8")
	if isinstance(raw, np.ndarray):
		return raw.tolist()
	# numpy scalar → python scalar
	if hasattr(raw, "item"):
		return raw.item()
	return raw


def _read_tome_dict(fh: h5py.Group) -> dict:
	return {k: _read_tome_value(fh[k]) for k in fh.keys()}


def tome_to_dict(filename: str) -> dict | None:
	"""
	Read an HDF5 file written by dict_to_hdf and return a Python dict.

	Returns None if the file cannot be read.
	"""
	try:
		with h5py.File(filename, 'r') as fh:
			return _read_tome_dict(fh)
	except Exception as e:
		print(f"Failed to read HDF file: {e}")
		return None
