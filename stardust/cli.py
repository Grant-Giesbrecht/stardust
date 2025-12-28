import textwrap
from itertools import groupby

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

def settings_cli(settings: dict):
	"""
	Interactive CLI for inspecting and editing settings.

	settings format:
	{
		"setting_name": {
			"value": <any>,
			"desc": <str>
		},
		...
	}
	"""

	def print_help():
		print("""
Settings CLI commands:
  list                      List all settings
  show <name>               Show value and description
  set <name> <value>        Set a new value (type preserved)
  help                      Show this help
  exit | quit               Exit settings editor
""")
	
	def list_settings():
		for k, v in settings.items():
			print(f"{k:20} = {v['value']}  ({v['desc']})")
	
	def show_setting(name):
		if name not in settings:
			print(f"Unknown setting: {name}")
			return
		s = settings[name]
		print(f"{name}")
		print(f"  value: {s['value']} ({type(s['value']).__name__})")
		print(f"  desc : {s['desc']}")
	
	def parse_value(old_value, new_str):
		t = type(old_value)
		try:
			if t is bool:
				if new_str.lower() in ("true", "1", "yes", "on"):
					return True
				if new_str.lower() in ("false", "0", "no", "off"):
					return False
				raise ValueError
			return t(new_str)
		except Exception:
			raise ValueError(f"Could not convert '{new_str}' to {t.__name__}")
	
	print("Entering settings editor (type 'help' for commands)")
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
			print_help()
		
		elif action == "list":
			list_settings()
		
		elif action == "show":
			if len(parts) != 2:
				print("Usage: show <name>")
				continue
			show_setting(parts[1])
		
		elif action == "set":
			if len(parts) < 3:
				print("Usage: set <name> <value>")
				continue
			name = parts[1]
			value_str = " ".join(parts[2:])
			
			if name not in settings:
				print(f"Unknown setting: {name}")
				continue
			
			old_value = settings[name]["value"]
			try:
				new_value = parse_value(old_value, value_str)
			except ValueError as e:
				print(e)
				continue
			
			settings[name]["value"] = new_value
			print(f"{name} set to {new_value}")
		
		else:
			print(f"Unknown command: {action}")
