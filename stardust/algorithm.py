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
	
	# Ensure exact inclusion of stop (handles floating point rounding issues)
	if values[-1] < stop or math.isclose(values[-1], stop):
		values.append(stop)
	
	return values

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

def randrangef(xmin:float, xmax:float, step:float=None):
	""" Returns a random number between 'xmin' and 'xmax' with
	steps of 'step' enforced.
	
	if step = None, will not force any steps
	"""
	
	# Get float value in range
	value = random.random()*(xmax - xmin) + xmin
	
	# Round to a given step
	if step is not None:
		value = round(value/step)*step
	
	return value