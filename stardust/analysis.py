import numpy as np
from matplotlib.collections import PathCollection
from typing import Dict, Any, List
from matplotlib.figure import Figure

def _finite_xy(x, y):
	x = np.asarray(x, dtype=float)
	y = np.asarray(y, dtype=float)
	m = np.isfinite(x) & np.isfinite(y)
	return x[m], y[m]

def _segment_bound_intersections(x0, y0, x1, y1, xlow, xhigh):
	"""Return boundary intersection points (in segment order) if the segment crosses xlow/xhigh."""
	dx = x1 - x0
	if dx == 0 or not np.isfinite(dx):
		return []
	pts = []
	for bound in (xlow, xhigh):
		# Does the segment cross this vertical line?
		if (x0 < bound and x1 > bound) or (x0 > bound and x1 < bound):
			t = (bound - x0) / dx
			if 0.0 <= t <= 1.0:
				yb = y0 + t * (y1 - y0)
				pts.append((t, bound, yb))
	# ensure in-segment order
	pts.sort(key=lambda p: p[0])
	return [(xb, yb) for _, xb, yb in pts]

def _trim_line_to_xbounds(x, y, xlow, xhigh):
	"""
	Keep all original points with x in [xlow, xhigh] and add boundary points
	where segments cross xlow/xhigh.
	"""
	x, y = _finite_xy(x, y)
	if x.size < 2:
		# nothing to interpolate; just keep if inside
		m = (x >= xlow) & (x <= xhigh)
		return x[m], y[m]

	out_x: List[float] = []
	out_y: List[float] = []

	for i in range(len(x) - 1):
		x0, y0 = x[i],   y[i]
		x1, y1 = x[i+1], y[i+1]
		x0_in = (xlow <= x0 <= xhigh)
		x1_in = (xlow <= x1 <= xhigh)

		seg_pts = []
		if x0_in:
			seg_pts.append((x0, y0))

		# add boundary intersections (0, 1 or 2), in order along the segment
		seg_pts += _segment_bound_intersections(x0, y0, x1, y1, xlow, xhigh)

		if x1_in:
			seg_pts.append((x1, y1))

		# append to output, avoiding duplicate joins
		for (xs, ys) in seg_pts:
			if not out_x or xs != out_x[-1] or ys != out_y[-1]:
				out_x.append(xs)
				out_y.append(ys)

	# Final safety filter (numeric noise, exact inclusivity)
	m = (np.asarray(out_x) >= xlow) & (np.asarray(out_x) <= xhigh)
	return np.asarray(out_x)[m], np.asarray(out_y)[m]

def extract_visible_xy(fig: Figure) -> List[Dict[str, Any]]:
	"""
	Extract X/Y data for each visible trace in a Matplotlib figure, trimmed to
	the current x-limits of each Axes.

	Returns a list of dicts, one per trace:
	  {
		'axes_index': int,           # index of the Axes in fig.get_axes()
		'type': 'line'|'scatter',
		'label': str,                # artist label
		'x': np.ndarray,             # trimmed x data
		'y': np.ndarray,             # trimmed y data
		'xlim_used': (float, float)  # x-limits applied for trimming
	  }
	"""
	results: List[Dict[str, Any]] = []
	for ax_i, ax in enumerate(fig.get_axes()):
		# Respect each axes' current x-limits; sort so bounds are [low, high]
		xmin, xmax = ax.get_xlim()
		xlow, xhigh = (xmin, xmax) if xmin <= xmax else (xmax, xmin)

		# Lines
		for line in ax.lines:
			if not line.get_visible():
				continue
			x = line.get_xdata(orig=True)
			y = line.get_ydata(orig=True)
			tx, ty = _trim_line_to_xbounds(x, y, xlow, xhigh)
			results.append({
				'axes_index': ax_i,
				'type': 'line',
				'label': line.get_label(),
				'x': tx,
				'y': ty,
				'xlim_used': (xlow, xhigh),
			})

		# Scatter collections (PathCollection)
		for col in ax.collections:
			if not col.get_visible():
				continue
			if not isinstance(col, PathCollection):
				continue
			offs = col.get_offsets()
			if offs is None or len(offs) == 0:
				continue
			offs = np.asarray(offs, dtype=float)
			if offs.ndim != 2 or offs.shape[1] != 2:
				continue
			xs = offs[:, 0]
			ys = offs[:, 1]
			xs, ys = _finite_xy(xs, ys)
			m = (xs >= xlow) & (xs <= xhigh)
			results.append({
				'axes_index': ax_i,
				'type': 'scatter',
				'label': col.get_label(),
				'x': xs[m],
				'y': ys[m],
				'xlim_used': (xlow, xhigh),
			})

	return results
