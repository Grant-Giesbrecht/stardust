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


# ------------------------------------------------------------------
# String handling
# ------------------------------------------------------------------
# h5py 3.x returns variable-length string data as `bytes` (scalars) or
# object arrays of `bytes` (datasets), NOT `str`. Any read path that does
# not explicitly decode will therefore hand back byte strings, which then
# surface as b'...' reprs downstream (e.g. matplotlib tick labels). The
# helpers below decode consistently, and the writer stores strings as
# proper vlen UTF-8 so they always round-trip.
# ------------------------------------------------------------------

def _decode_scalar(x: Any) -> Any:
	"""Decode a single bytes/np.bytes_ value to str; pass everything else through."""
	if isinstance(x, (bytes, bytearray, np.bytes_)):
		try:
			return bytes(x).decode("utf-8")
		except Exception:
			return bytes(x).decode("latin-1", "replace")
	return x


def _decode_iterable(values) -> list:
	"""Decode every element of an iterable of scalars to str where applicable."""
	return [_decode_scalar(x) for x in values]


def _is_string_array(arr: np.ndarray) -> bool:
	"""True if a numpy array holds (byte or unicode) strings.

	kind 'S' = fixed-length bytes, 'U' = unicode, 'O' = object (h5py hands vlen
	strings back as object arrays of bytes)."""
	return arr.dtype.kind in ("S", "U", "O")


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

	# ---- list of strings → vlen UTF-8 dataset ----------------------
	# Handled explicitly (before the generic list branch) so the string
	# dtype is actually applied — otherwise h5py stores them ambiguously
	# and they read back as bytes.
	elif isinstance(value, list) and value and all(isinstance(v, str) for v in value):
		ds = fh.create_dataset(key, data=np.array(value, dtype=object),
							   dtype=h5py.string_dtype(encoding="utf-8"))
		ds.attrs[_ATTR_TYPE] = "list"
		ds.attrs["dtype"] = "str"

	# ---- numpy array ------------------------------------------------
	elif isinstance(value, np.ndarray):
		if value.dtype.kind in ("U", "S"):
			# String arrays: numpy 'U' (unicode) has no native HDF5 type and
			# would raise, so store as vlen UTF-8. (Shapes here are 1-D lists
			# of labels; flattened on write, restored 1-D on read.)
			flat = [_decode_scalar(x) if isinstance(x, (bytes, np.bytes_)) else str(x)
					for x in value.ravel().tolist()]
			ds = fh.create_dataset(key, data=np.array(flat, dtype=object),
								   dtype=h5py.string_dtype(encoding="utf-8"))
			ds.attrs[_ATTR_TYPE] = "ndarray"
			ds.attrs["dtype"] = "str"
		else:
			ds = fh.create_dataset(key, data=value)
			ds.attrs[_ATTR_TYPE] = "ndarray"
			ds.attrs["dtype"] = str(value.dtype)

	# ---- plain list (convert to numpy for storage) -----------------
	elif isinstance(value, list):
		arr = _list_to_array(value)
		if arr.dtype == object:
			# Ragged/mixed fell back to string encoding → store as vlen UTF-8.
			ds = fh.create_dataset(key, data=arr,
								   dtype=h5py.string_dtype(encoding="utf-8"))
			ds.attrs[_ATTR_TYPE] = "list"
			ds.attrs["dtype"] = "str"
		else:
			ds = fh.create_dataset(key, data=arr)
			ds.attrs[_ATTR_TYPE] = "list"
			ds.attrs["dtype"] = str(arr.dtype)

	# ---- scalar str ------------------------------------------------
	elif isinstance(value, str):
		ds = fh.create_dataset(key, data=value, dtype=h5py.string_dtype(encoding="utf-8"))
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
		ds = fh.create_dataset(key, data=encoded, dtype=h5py.string_dtype(encoding="utf-8"))
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
		# Object array of str; the caller stores it with an explicit
		# h5py.string_dtype so it round-trips as text.
		return np.array(lst, dtype=object)
	try:
		arr = np.array(lst)
		if arr.dtype.kind in ("U", "S", "O"):
			# numpy chose a string/object dtype (e.g. mixed types) — encode as
			# JSON strings so the values survive as an object (vlen) array.
			return np.array([json.dumps(x) for x in lst], dtype=object)
		return arr
	except ValueError:
		# Ragged or mixed — store as JSON-encoded strings
		return np.array([json.dumps(x) for x in lst], dtype=object)


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
	- list[str]                  → HDF5 vlen UTF-8 dataset
	- np.ndarray                 → HDF5 dataset (dtype preserved; str arrays vlen)
	- list                       → HDF5 dataset (converted to ndarray)
	- str                        → HDF5 scalar dataset (UTF-8)
	- bool / int / float         → HDF5 scalar dataset
	- anything else              → JSON-encoded dataset (fallback)

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
	using the __pytype__ attribute written by dict_to_tome.

	All string data is decoded to `str` here — h5py returns vlen strings as
	`bytes`, so every dataset branch that can hold text decodes explicitly.
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
		s = _decode_scalar(raw)
		return s if isinstance(s, str) else str(s)

	if pytype == "bool":
		return bool(raw)

	if pytype == "ndarray":
		arr = np.asarray(raw)
		if _is_string_array(arr):
			# byte/object/unicode string array → decode to a unicode str array
			decoded = np.array(_decode_iterable(arr.ravel().tolist()))
			try:
				return decoded.reshape(arr.shape)
			except Exception:
				return decoded
		# numeric: restore the original dtype
		dtype_str = node.attrs.get("dtype", "")
		if dtype_str and dtype_str != "str":
			try:
				arr = arr.astype(dtype_str)
			except Exception:
				pass
		return arr

	if pytype == "list":
		arr = np.asarray(raw)
		if _is_string_array(arr):
			return _decode_iterable(arr.ravel().tolist())
		return arr.tolist()

	if pytype == "json":
		payload = _decode_scalar(raw)
		if not isinstance(payload, str):
			payload = str(payload)
		return json.loads(payload)

	# ---- numeric scalars and unlabelled legacy data ----------------
	if isinstance(raw, (bytes, np.bytes_, bytearray)):
		return _decode_scalar(raw)
	if isinstance(raw, np.ndarray):
		if _is_string_array(raw):
			return _decode_iterable(raw.ravel().tolist())
		return raw.tolist()
	# numpy scalar → python scalar
	if hasattr(raw, "item"):
		return raw.item()
	return raw


def _read_tome_dict(fh: h5py.Group) -> dict:
	return {k: _read_tome_value(fh[k]) for k in fh.keys()}


def tome_to_dict(filename: str) -> dict | None:
	"""
	Read an HDF5 file written by dict_to_tome and return a Python dict.

	Returns None if the file cannot be read.
	"""
	try:
		with h5py.File(filename, 'r') as fh:
			return _read_tome_dict(fh)
	except Exception as e:
		print(f"Failed to read HDF file: {e}")
		return None
