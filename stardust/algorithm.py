import math

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