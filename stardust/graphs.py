import numpy as np
from matplotlib.collections import QuadMesh
from matplotlib.image import AxesImage

try:  # matplotlib >= 3.5
	from matplotlib.collections import PolyQuadMesh
	_MESH_TYPES = (QuadMesh, PolyQuadMesh)
except ImportError:
	PolyQuadMesh = ()
	_MESH_TYPES = (QuadMesh,)


def flip_imgplot_axes(ax, artist=None):
	"""Swap the x and y axes of an imshow, pcolormesh, or pcolor plot (a transpose).

	Data, extent/coordinates, view limits, scales, and labels are swapped, and
	each axis keeps its direction. Returns the artist now on the axes. For
	pcolormesh/pcolor this is a new object, since mesh coordinates can't be
	replaced in place.
	"""
	
	if artist is None:
		meshes = [c for c in ax.collections if isinstance(c, _MESH_TYPES)]
		if ax.images:
			artist = ax.images[0]
		elif meshes:
			artist = meshes[0]
		else:
			raise ValueError("No imshow image, pcolormesh, or pcolor found on this axes.")

	# Record view state before changing anything
	xlim, ylim = ax.get_xlim(), ax.get_ylim()
	x_inv, y_inv = xlim[0] > xlim[1], ylim[0] > ylim[1]
	xscale, yscale = ax.get_xscale(), ax.get_yscale()
	xlabel, ylabel = ax.get_xlabel(), ax.get_ylabel()
	aspect = ax.get_aspect()

	if isinstance(artist, AxesImage):
		l, r, b, t = artist.get_extent()
		artist.set_data(np.swapaxes(artist.get_array(), 0, 1))  # also fine for RGB
		artist.set_extent((t, b, r, l) if artist.origin == "upper" else (b, t, l, r))
		new = artist

	elif isinstance(artist, _MESH_TYPES):
		coords = np.asarray(artist.get_coordinates())      # (ny+1, nx+1, 2) for flat shading
		data = np.ma.asarray(artist.get_array())
		flat = data.size == (coords.shape[0] - 1) * (coords.shape[1] - 1)
		data = data.reshape((coords.shape[0] - 1, coords.shape[1] - 1) if flat
							else coords.shape[:2])
		X, Y = coords[..., 0], coords[..., 1]

		ec = artist.get_edgecolor()
		lw = np.ravel(artist.get_linewidth())
		kwargs = dict(
			cmap=artist.cmap, norm=artist.norm, alpha=artist.get_alpha(),
			edgecolors=ec if len(ec) else "none",
			linewidth=lw[0] if lw.size else 0,
			antialiased=artist.get_antialiased(),
			rasterized=artist.get_rasterized(),
			zorder=artist.get_zorder(),
			label=artist.get_label(),
		)
		if isinstance(artist, QuadMesh):
			new = ax.pcolormesh(Y.T, X.T, data.T,
								shading="flat" if flat else "gouraud", **kwargs)
		else:  # PolyQuadMesh, i.e. created with ax.pcolor
			new = ax.pcolor(Y.T, X.T, data.T, shading="flat", **kwargs)
		artist.remove()
	else:
		raise TypeError(f"Unsupported artist type: {type(artist).__name__}")

	# Swap scales, labels, and view limits, preserving each axis's direction
	ax.set_xscale(yscale)
	ax.set_yscale(xscale)
	ax.set_xlabel(ylabel)
	ax.set_ylabel(xlabel)

	def orient(lim, inverted):
		lo, hi = sorted(lim)
		return (hi, lo) if inverted else (lo, hi)

	ax.set_xlim(orient(ylim, x_inv))
	ax.set_ylim(orient(xlim, y_inv))

	if isinstance(aspect, (int, float)) and aspect:
		ax.set_aspect(1 / aspect)

	ax.figure.canvas.draw_idle()
	return new