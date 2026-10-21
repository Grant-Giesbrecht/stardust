import math
import os
import numpy as np
import random

def linstep(start, stop, step):
	"""
	Generate numbers from start to stop inclusive, spaced by step.
	
	Params:
		start (float): The starting value of the sequence.
		stop (float): The end value of the sequence (inclusive).
		step (float): The spacing between values.
	
	Returns:
		list: Values from start to stop (inclusive).
	"""
	
	# Error check step size
	if step <= 0:
		raise ValueError("step must be positive")
	
	# Generate list
	n_steps = int(math.floor((stop - start) / step))
	values = [start + i * step for i in range(n_steps + 1)]

	# Ensure exact inclusion of stop (handles floating point rounding issues).
	# If the last generated value already lands on stop (within floating
	# point tolerance), snap it to the exact value instead of appending a
	# duplicate.
	if math.isclose(values[-1], stop):
		values[-1] = stop
	elif values[-1] < stop:
		values.append(stop)

	return values

def logstep(start:float, stop:float, N:int, per_decade:bool=True, input_exp:bool=False):
	"""
	Generate logarithmically spaced values. `start` and `stop` take actual start/stop
	values by default (not exponents), and N specifies number of points per decade
	by default.
	
	Params:
		start (float): The starting value of the sequence.
		stop (float): The end value of the sequence (inclusive).
		N (float): Number of points per decade. If `per_decade` is set to false, 
			then `N` specifies the total number of points.
		per_decade (bool): Controls if N sets the total number of points, or
			points per decade.
		input_exp (bool): Controls if `start` and `stop` specify actaul values
			(default option), or are interpreted as exponents (ie. -1 to specify
			0.1).
	
	Returns:
		list: Values from start to stop (inclusive).
	"""
	
	# Get start/stop values
	start_exp = start if input_exp else np.log10(start)
	stop_exp = stop if input_exp else np.log10(stop)
	
	if per_decade:
		num_decades = abs(stop_exp - start_exp)
		total_points = int(round(num_decades * N)) + 1
	else:
		total_points = N
	
	return np.logspace(start_exp, stop_exp, total_points)

def has_ext(path:str, exts:list):
	''' Checks if the given path ends with any of the provided extensions.
	
	Args:
		path (str): Path to file whose extension to check.
		exts (list): List of strings. If any match the file extension, will
			return True.
	
	Returns:
		(bool): True if the file matches any of the provided extensions.
	
	'''
	return os.path.splitext(path)[1].lower() in [e.lower() for e in exts]

def bounded_interp(x, y, x_target):
	''' Interpolation with protection such that None is returned if requested
	value is out of bounds.
	'''
	
	if x_target < x[0] or x_target > x[-1]:
		return None
	return np.interp(x_target, x, y) 

def randrange(start:float, stop:float, bin_size:float=None):
	"""
	Generate a random number between `start` and `stop`.
	
	Params:
		start (float): The starting value for the range.
		stop (float): The end value for the range.
		bin_size (float): If not None, bins random numbers, rounding to the
			closest bin value. Size of value to round to is bin_size.
	
	Returns:
		float: Random number
	"""
	
	# Get random number is requested range
	rval = random.random()*(stop-start) + start
	
	# Round to nearest bin (if requested)
	if (bin_size is not None) and (bin_size > 0):
		rval = np.round(rval/bin_size)*bin_size
	
	return rval

def closest_indices(freq, target):
	freq = np.asarray(freq)
	target = np.asarray(target)

	# positions where each target value would be inserted to keep freq sorted
	idx = np.searchsorted(freq, target)

	# clip so we can safely look at idx-1 and idx
	idx = np.clip(idx, 1, len(freq) - 1)

	left = freq[idx - 1]
	right = freq[idx]

	# choose whichever neighbor is actually closer
	closer_left = np.abs(target - left) <= np.abs(target - right)
	result = np.where(closer_left, idx - 1, idx)

	return result.tolist()

def merge_lists(*arrays, decimals=9):
	"""
	Merge multiple 1D arrays (e.g. a coarse sweep + one or more fine-resolution
	regions) into a single sorted array with duplicate values removed.

	Parameters
	----------
	*arrays : array_like
		Any number of 1D arrays to merge.
	decimals : int, optional
		Rounding precision used to detect "duplicate" values, since
		floating-point values from different linspace calls that are
		conceptually equal (e.g. 5.0 from both arrays) may differ in the
		last bit. Default 9.

	Returns
	-------
	np.ndarray
		Sorted, de-duplicated union of all input arrays.
	"""
	combined = np.concatenate([np.asarray(a).ravel() for a in arrays])
	combined = np.sort(combined)

	# Round for duplicate detection but keep original (unrounded) values
	rounded = np.round(combined, decimals)
	_, unique_idx = np.unique(rounded, return_index=True)

	return combined[np.sort(unique_idx)]

def nanlen(x):
	"""
	Returns the length of a list, excluding all np.nan values.

	Parameters
	----------
	x: array_like
		1D array to count
	
	Returns
	-------
	int
		Length of array excluding np.nan elements.
	"""
	return np.count_nonzero(~np.isnan(x))