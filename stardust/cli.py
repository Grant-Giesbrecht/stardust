import textwrap
from itertools import groupby
import json
import copy
from pathlib import Path

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
		if settings_file is not None:
			self.settings_file = Path(settings_file)
			self.settings = self._load_settings()
			self.autosave = autosave
		else:
			self.settings_file = settings_file
			self.settings = temp_settings
			self.autosave = False
		
		self._original_settings = copy.deepcopy(self.settings)
	
	
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

