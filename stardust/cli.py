import textwrap
from itertools import groupby
import json
import copy
from pathlib import Path

import math

_SI_PREFIXES = {
	-24: "y",
	-21: "z",
	-18: "a",
	-15: "f",
	-12: "p",
	-9:  "n",
	-6:  "µ",
	-3:  "m",
	 0:  "",
	 3:  "k",
	 6:  "M",
	 9:  "G",
	12:  "T",
	15:  "P",
	18:  "E",
	21:  "Z",
	24:  "Y",
}

def rde(
	x: float,
	sigfigs: int = 3,
	use_si_prefix: bool = False,
	exp_suffix: bool = True,
	unit: str = "",
) -> str:
	"""
	Pretty-print a number using engineering notation or SI prefixes.

	Parameters
	----------
	x : float
		Value to format
	sigfigs : int
		Number of significant figures
	use_si_prefix : bool
		Use SI prefixes (k, M, µ, etc.) instead of exponents
	exp_suffix : bool
		If False, uses ×10^N instead of eN (ignored if use_si_prefix=True)
	unit : str
		Optional unit string

	Returns
	-------
	str
	"""
	if x == 0 or not math.isfinite(x):
		return f"{x:g}{unit}"

	sign = "-" if x < 0 else ""
	x = abs(x)

	# Engineering exponent
	exp = int(math.floor(math.log10(x) / 3) * 3)
	mant = x / (10 ** exp)

	# Significant-figure rounding
	digits = sigfigs - int(math.floor(math.log10(mant))) - 1
	mant = round(mant, digits)

	# Handle rounding overflow
	if mant >= 1000:
		mant /= 1000
		exp += 3

	mant_str = f"{mant:g}"

	# SI prefix path
	if use_si_prefix and exp in _SI_PREFIXES:
		prefix = _SI_PREFIXES[exp]
		return f"{sign}{mant_str}{prefix}{unit}"

	# Engineering notation fallback
	if exp == 0:
		return f"{sign}{mant_str}{unit}"

	if exp_suffix:
		return f"{sign}{mant_str}e{exp}{unit}"
	else:
		return f"{sign}{mant_str}×10^{exp}{unit}"


def rd(x:float, num_decimals:int=2):
	
	if x is None:
		return "NaN"
	
	return f"{round(x*10**num_decimals)/(10**num_decimals)}"

def ensureWhitespace(s:str, targets:str, whitespace_list:str=" \t", pad_char=" "):
	""" """
	
	# Remove duplicate targets
	targets = "".join(set(targets))
	
	# Add whitespace around each target
	for tc in targets:
		
		start_index = 0
		
		# Find all instances of target
		while True:
			
			# Find next instance of target
			try:
				idx = s[start_index:].index(tc)
				idx += start_index
			except ValueError as e:
				break # Break when no more instances
			
			# Update start index
			start_index = idx + 1
			
			# Check if need to pad before target
			add0 = True
			if idx == 0:
				add0 = False
			elif s[idx-1] in whitespace_list:
				add0 = False
			
			# Check if need to pad after target
			addf = True
			if idx >= len(s)-1:
				addf = False
			elif s[idx+1] in whitespace_list:
				addf = False
			
			# Add required pad characters
			if addf:
				s = s[:idx+1] + pad_char + s[idx+1:]
				start_index += 1 # Don't scan pad characters
			if add0:
				s = s[:idx] + pad_char + s[idx:]
	
	return s

class StringIdx():
	def __init__(self, val:str, idx:int, idx_end:int=-1):
		self.str = val
		self.idx = idx
		self.idx_end = idx_end

	def __str__(self):
		return f"[{self.idx}]\"{self.str}\""

	def __repr__(self):
		return self.__str__()

def parse_idx(input:str, delims:str=" ", keep_delims:str=""):
	""" Parses a string, breaking it up into an array of words. Separates at delims. """
	
	def parse_two_idx(input:str, delims:str):
		p = 0
		for k, g in groupby(input, lambda x:x in delims):
			q = p + sum(1 for i in g)
			if not k:
				yield (p, q) # or p, q-1 if you are really sure you want that
			p = q
	
	out = []
	
	sections = list(parse_two_idx(input, delims))
	for s in sections:
		out.append(StringIdx(input[s[0]:s[1]], s[0], s[1]))
	return out

def barstr(text:str, width:int=80, bc:str='*', pad:bool=True):

		s = text;

		# Pad input if requested
		if pad:
			s = " " + s + " ";

		pad_back = False;
		while len(s) < width:
			if pad_back:
				s = s + bc
			else:
				s = bc + s
			pad_back = not pad_back

		return s

def wrap_text(text:str, width:int=80):
	""" Accepts a string, and wraps it over multiple lines. Honors line breaks. Returns a single string."""
	
	# Break at \n and form list of strings without \n
	split_lines = text.splitlines()
	
	all_lines = []
	
	# Loop over each split string, apply standard wrap
	for sl in split_lines:
		
		wt = textwrap.wrap(sl, width=width)
		for wtl in wt:
			all_lines.append(wtl)
	
	# Join with newline characters
	return '\n'.join(all_lines)

class SettingsCLI:
	"""
	Interactive settings editor for a dict-of-dicts settings structure.

	File format (JSON):
	{
		"setting_name": {
			"value": <any>,
			"desc": "<description>"
		}
	}
	"""
	
	def __init__(self, settings_file: str | Path, autosave: bool = False, temp_settings:dict={}):
		'''
		Provide a settings_file to be able to save settings. Otherwise, set None for settings_file and
		provide data to temp_settings. If a settings_file is provided, temp_settings is ignored.
		'''
		
		if settings_file is not None:
			self.settings_file = Path(settings_file)
			self.settings = self._load_settings()
			self.autosave = autosave
		else:
			self.settings_file = settings_file
			self.settings = temp_settings
			self.autosave = False
		
		self._original_settings = copy.deepcopy(self.settings)
	
	def get(self, param:str):
		''' Attempts to access parameter. Returns None if not 
		present, then creates field for that entry.'''
		
		if param in self.settings:
			return self.settings[param]
		else:
			self.settings[param] = None
			return None
	
	def _load_settings(self) -> dict:
		if self.settings_file is None:
			print(f"Cannot load when in temporary mode.")
			return {}
		
		if not self.settings_file.exists():
			raise FileNotFoundError(self.settings_file)
	
		with self.settings_file.open("r", encoding="utf-8") as f:
			return json.load(f)
	
	def save(self):
		
		if self.settings_file is None:
			print(f"Cannot save when in temporary mode.")
			return
		
		with self.settings_file.open("w", encoding="utf-8") as f:
			json.dump(self.settings, f, indent=2)
		self._original_settings = copy.deepcopy(self.settings)
	
	def undo(self):
		self.settings = copy.deepcopy(self._original_settings)
	
	def _print_help(self):
		print("""
Settings CLI commands:
  list                      List all settings
  show <name>               Show value and description
  set <name> <value>        Set value (type preserved)
  save                      Save settings to file
  undo                      Revert to last saved state
  help                      Show this help
  exit | quit               Exit editor
""")
	
	def _list_settings(self):
		for k, v in self.settings.items():
			print(f"{k:20} = {v['value']}  ({v['desc']})")
	
	def _show_setting(self, name):
		if name not in self.settings:
			print(f"Unknown setting: {name}")
			return
		
		s = self.settings[name]
		print(name)
		print(f"  value: {s['value']} ({type(s['value']).__name__})")
		print(f"  desc : {s['desc']}")
		
	def _parse_value(self, old_value, new_str):
		t = type(old_value)
		
		if t is bool:
			if new_str.lower() in ("true", "1", "yes", "on"):
				return True
			if new_str.lower() in ("false", "0", "no", "off"):
				return False
			raise ValueError("Invalid boolean")
		
		return t(new_str)
	
	def run(self):
		print("Entering settings editor (type 'help' for commands)")
		dirty = False
		
		while True:
			try:
				cmd = input("settings> ").strip()
			except (EOFError, KeyboardInterrupt):
				print()
				break
			
			if not cmd:
				continue
			
			parts = cmd.split()
			action = parts[0].lower()
			
			if action in ("exit", "quit"):
				break
			
			elif action == "help":
				self._print_help()
			
			elif action == "list":
				self._list_settings()
			
			elif action == "show":
				if len(parts) != 2:
					print("Usage: show <name>")
					continue
				self._show_setting(parts[1])
			
			elif action == "set":
				if len(parts) < 3:
					print("Usage: set <name> <value>")
					continue
				
				name = parts[1]
				value_str = " ".join(parts[2:])
				
				if name not in self.settings:
					print(f"Unknown setting: {name}")
					continue
				
				try:
					old = self.settings[name]["value"]
					new = self._parse_value(old, value_str)
				except Exception as e:
					print(f"Error: {e}")
					continue
				
				self.settings[name]["value"] = new
				dirty = True
				print(f"{name} set to {new}")
				
				if self.autosave:
					self.save()
					dirty = False
			
			elif action == "save":
				self.save()
				dirty = False
				print("Settings saved.")
			
			elif action == "undo":
				self.undo()
				dirty = False
				print("Reverted to last saved state.")
			
			else:
				print(f"Unknown command: {action}")
		
		if dirty and not self.autosave:
			choice = input("Keep changes? [Y/n] ").strip().lower()
			if choice != "n":
				if self.settings_file is not None:
					self.save()
					print("Settings saved.")
				else:
					print(f"Changes kept.")
			else:
				self.undo()
				print("Changes discarded.")

