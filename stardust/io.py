from colorama import Fore, Style
import sys
import os
import string
import h5py
import time
import numpy as np
import json

import base64
from typing import Dict, Any
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet, InvalidToken

def locate_drive(id:str, param:str="ID", filename="drive_id.txt", silence_output:bool=False):
	''' Returns the path to a drive containing the file `filename`, 
	which contains a line defining <param>=<id>. Used to identify a
	removable harddrive connected to various systems without trying
	to hardcode drive letters, expect a specific volumne name or similar.
	'''
	
	file_contents = f"{param}={id}"
	
	def bprint(s:str, silence:bool=False):
		if silence:
			return
		else:
			print(s)
	
	def scan_drives_windows(filename, file_contents):
		matching_drives = []
		# Check all potential drive letters (A to Z)
		for drive_letter in string.ascii_uppercase:
			drive = f"{drive_letter}:\\"
			if os.path.exists(drive):
				file_path = os.path.join(drive, filename)
				if os.path.isfile(file_path):
					try:
						with open(file_path, 'r', encoding='utf-8') as file:
							for line in file:
								if line.strip() == file_contents:
									matching_drives.append(drive)
									break
					except Exception as e:
						bprint(f"Error reading {file_path}: {e}", silence=silence_output)
		return matching_drives
	
	def scan_drives_unix(filename, file_contents):
		possible_mount_points = ['/mnt', '/media', '/Volumes']
		matching_mounts = []

		for mount_root in possible_mount_points:
			if os.path.exists(mount_root):
				for entry in os.listdir(mount_root):
					mount_path = os.path.join(mount_root, entry)
					if os.path.ismount(mount_path):
						file_path = os.path.join(mount_path, filename)
						if os.path.isfile(file_path):
							try:
								with open(file_path, 'r', encoding='utf-8') as file:
									for line in file:
										if line.strip() == file_contents:
											matching_mounts.append(mount_path)
											break
							except Exception as e:
								bprint(f"Error reading {file_path}: {e}", silence=silence_output)
		return matching_mounts
	
	if sys.platform == "win32":
		drives = scan_drives_windows(filename, file_contents=file_contents)
	elif sys.platform == "darwin" or sys.platform.startswith("linux"):
		drives = scan_drives_unix(filename, file_contents=file_contents)
	else:
		bprint(f"Unknown operating system: {sys.platform}", silence=silence_output)
		return None
	
	if len(drives) == 0:
		bprint(f"{Fore.RED}No matching drives found!{Style.RESET_ALL} Looking for file {Fore.YELLOW}{filename}{Style.RESET_ALL} with contents {Fore.GREEN}{file_contents}{Style.RESET_ALL}.", silence=silence_output)
		return None
	
	drv = drives[0]
	if len(drives) == 1:
		bprint(f"{Fore.GREEN}Found matching drive!{Style.RESET_ALL} Path = {Fore.YELLOW}{drv}{Style.RESET_ALL}.", silence=silence_output)
	else:
		bprint(f"{Fore.RED}Found multiple matching drives!{Style.RESET_ALL} Returning first matched drive. Path = {Fore.YELLOW}{drv}{Style.RESET_ALL}.", silence=silence_output)
	return drv

def dict_to_hdf(root_data:dict, save_file:str, use_json_backup:bool=False, show_detail:bool=False) -> bool:
	''' Writes a dictionary to an HDF file per the rules used by 'write_level()'. 
	
	* If the value of a key in another dictionary, the key is made a group (directory).
	* If the value of the key is anything other than a dictionary, it assumes
	  it can be saved to HDF (such as a list of floats), and saves it as a dataset (variable).
	
	Args:
		root_data (dict): Dictionary to save to file.
		save_file (str): Filename to write to.
		use_json_backup (bool): Optional parameter to save a copy of the file as a JSON dict. Default = False.
		show_detail (bool): Optional parameter to show detail while saving. Default = False.
	
	Returns:
		bool: True if successfully saved.
	'''
		
	def write_level(fh:h5py.File, level_data:dict, show_detail:bool=False):
		''' Writes a dictionary to the hdf file.
		
		Recursive function used by  '''
		
		if show_detail:
				print(f"write_level received item of type: {type(level_data)}")
		
		# Scan over each directory of root-data
		for k, v in level_data.items():
			
			if show_detail:
				print(f"Handling object key={k} of type {type(v)}")
			
			# If value is a dictionary, this key represents a directory
			if type(v) == dict:
				
				if show_detail:
					print(f"\tDetected dictionary. Creating group {k} and writing new level...")
				
				# Create a new group
				fh.create_group(k)
				
				# Write the dictionary to the group
				write_level(fh[k], v, show_detail=show_detail)
					
			else: # Otherwise try to write this datatype (ex. list of floats)
				
				if show_detail:
					print(f"\tDetected non-dictionary. Creating dataset {k} and saving value {v}")
				
				# Write value as a dataset
				try:
					fh.create_dataset(k, data=v)
				except Exception as e:
					if show_detail:
						print(f"Failed to write dataset '{k}' with value of type {type(v)}. ({e})")
					return False
		return True
	
	# Start timer
	t0 = time.time()
	
	# Open HDF
	hdf_successful = True
	exception_str = ""
	
	# Recursively write HDF file
	with h5py.File(save_file, 'w') as fh:
		
		# Try to write dictionary
		try:
			if not write_level(fh, root_data, show_detail=show_detail):
				hdf_successful = False
				exception_str = "Set show_detail to true for details"
		except Exception as e:
			hdf_successful = False
			exception_str = f"{e}"
	
	# Check success condition
	if hdf_successful:
		# print(f"Wrote file in {time.time()-t0} sec.")
		
		return True
	else:
		print(f"Failed to write HDF file! ({exception_str})")
		
		# Write JSON as a backup if requested
		if use_json_backup:
			
			# Add JSON extension
			save_file_json = save_file[:-3]+".json"
			
			# Open and save JSON file
			try:
				with open(save_file_json, "w") as outfile:
					outfile.write(json.dumps(root_data, indent=4))
			except Exception as e:
				print(f"Failed to write JSON backup: ({e}).")
				return False
		
		return True

def hdf_to_dict(filename, to_lists:bool=True, decode_strs:bool=True) -> dict:
	''' Reads a HDF file and converts the data to a dictionary '''
	
	def read_level(fh:h5py.File) -> dict:
		
		# Initialize output dict
		out_data = {}
		
		# Scan over each element on this level
		for k in fh.keys():
			
			# Read value
			if type(fh[k]) == h5py._hl.group.Group: # If group, recusively call
				out_data[k] = read_level(fh[k])
			else: # Else, read value from file
				out_data[k] = fh[k][()]
				
				# Converting to a pandas DataFrame will crash with
				# some numpy arrays, so convert to a list.
				is_list_type = False
				if type(out_data[k]) == np.ndarray and to_lists:
						out_data[k] = list(out_data[k])
						is_list_type = True
				elif type(out_data[k]) == list and not to_lists:
						out_data[k] = np.array(out_data[k])
						is_list_type = True
				
				if is_list_type and len(out_data[k]) > 0 and type(out_data[k][0]) == bytes:
					for idx, val in enumerate(out_data[k]):
						out_data[k][idx] = val.decode()
				else:
					if decode_strs and type(out_data[k]) == bytes:
						out_data[k] = out_data[k].decode()
				
		return out_data
	
	# Open file
	with h5py.File(filename, 'r') as fh:
		
		try:
			root_data = read_level(fh)
		except Exception as e:
			print(f"Failed to read HDF file! ({e})")
			return None
	
	# Return result
	return root_data

def dict_summary(x:dict, verbose:int=0, indent_level:int=0, indent_char:str="   "):
	'''
	'''
	
	color_dict = Fore.CYAN
	color_name = Fore.GREEN
	color_lines = Fore.LIGHTBLACK_EX
	color_list_type = Fore.MAGENTA
	color_type = Fore.YELLOW
	color_value = Fore.WHITE
	color_ellips = Fore.RED
	
	lvlmarker_1 = "|"
	lvlmarker_2 = "."
	
	def get_indent(indent_level:int):
		
		indent_char0 = f" {indent_char}"
		indent_char1 = f"{lvlmarker_1}{indent_char}"
		indent_char2 = f"{lvlmarker_2}{indent_char}"
		
		indent_str = ""
		for i in range(indent_level):
			if i == 0:
				indent_str += indent_char0
			elif i % 2 == 1:
				indent_str += indent_char1
			else:
				indent_str += indent_char2
		return f"{color_lines}{indent_str}{Style.RESET_ALL}"
	
	def value_to_string(val, verbose:int, indent_level, length_limit:int=50, wrap_length:int=80):
		
		# Get full value string if verbose != 0
		if verbose == 0:
			return ""
		
		val_str = f"{val}"
		
		# If verbose == 1, truncate
		if verbose == 1:
			if len(val_str) > length_limit:
				val_str = val_str[:length_limit//2] + f"{color_ellips}...{color_value}" + val_str[-(length_limit//2-3):]
		
		# If verbose == 2, indent and print full value
		if verbose == 2:
			
			# Get length of color specifier
			cvlen = len(color_value)
			
			# Get indent char
			indent = get_indent(indent_level+1)
			indent.replace('\t', "    ")
			
			# Initialize with newline, indent and color
			if type(val) == str:
				val_str = f"\n{indent}{color_value}\"{val_str}\""
			else:
				val_str = f"\n{indent}{color_value}{val_str}"
			val_str.replace('\t', "    ")
			
			# Find last newline
			nlidx = val_str.rfind('\n')
			
			# Continue to wrap line until under length limit
			while len(val_str) - nlidx - cvlen > wrap_length:
				
				# Add newline (and color specs)
				val_str = val_str[:(nlidx)+wrap_length+cvlen] + "\n" + indent + color_value + val_str[(nlidx)+wrap_length+cvlen:]
				
				# Find new index
				nlidx = val_str.rfind('\n')
		
		else:
			# Add color to string
			if type(val) == str:
				val_str = f"{color_value}\"{val_str}\"{Style.RESET_ALL}"
			else:
				val_str = f"{color_value}{val_str}{Style.RESET_ALL}"
		
		return val_str
	
	# Scan over each key
	for k in x.keys():
		
		# IF key points to dictionary, recursive call
		if type(x[k]) == dict:
			print(f"{get_indent(indent_level)}[{color_dict}{k}{Style.RESET_ALL}]")
			dict_summary(x[k], verbose=verbose, indent_level=indent_level+1)
			
		# Otherwise print data element stats
		else:
			val = x[k]
			
			if type(val) == list:
				try:
					val0 = val[0]
				except:
					val0 = None
				
				if type(val0) == list:
					val_str = value_to_string(val, verbose, indent_level)
					print(f"{get_indent(indent_level)}{color_name}{k}{Style.RESET_ALL} = {color_list_type}{type(val)}{Style.RESET_ALL}, {len(val)} x {color_list_type}{type(val0)} {val_str}{Style.RESET_ALL}")
				else:
					val_str = value_to_string(val, verbose, indent_level)
					print(f"{get_indent(indent_level)}{color_name}{k}{Style.RESET_ALL} = {color_list_type}{type(val)}{Style.RESET_ALL}, {len(val)} x {color_type}{type(val0)} {val_str}{Style.RESET_ALL}")
			else:
				val_str = value_to_string(val, verbose, indent_level)
				print(f"{get_indent(indent_level)}{color_name}{k}{Style.RESET_ALL} = {color_type}{type(val)}{Style.RESET_ALL} {val_str}{Style.RESET_ALL}")

def _derive_key(password:str, salt:bytes, iterations:int = 200_000) -> bytes:
	kdf = PBKDF2HMAC(
		algorithm=hashes.SHA256(),
		length=32,
		salt=salt,
		iterations=iterations,
	)
	return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def dumpsecure(file_pointer, encrypted:dict, password:str, plain:dict={}, indent:int=4):
	"""
	Write a JSON file containing:
	  - 'plain': unencrypted dictionary
	  - 'encrypted': password-protected dictionary
	"""
	
	salt = os.urandom(16)
	key = _derive_key(password, salt)
	fernet = Fernet(key)
	
	encrypted_bytes = json.dumps(encrypted).encode()
	ciphertext = fernet.encrypt(encrypted_bytes)
	
	out = {
		"plain": plain,
		"encrypted": {
			"salt": base64.b64encode(salt).decode(),
			"ciphertext": ciphertext.decode(),
		},
	}
	
	json.dump(out, file_pointer, indent=indent)

def loadsecure(file_pointer, password:str) -> tuple[Dict[str, Any], Dict[str, Any]]:
	"""
	Read a file created by dumpsecure.
	
	Returns:
		(plain_dict, decrypted_dict)

	Raises:
		ValueError if password is incorrect or file was tampered with
	"""
	
	data = json.load(file_pointer)
	
	plain = data["plain"]
	enc = data["encrypted"]
	
	salt = base64.b64decode(enc["salt"])
	ciphertext = enc["ciphertext"].encode()
	
	key = _derive_key(password, salt)
	fernet = Fernet(key)
	
	try:
		decrypted_bytes = fernet.decrypt(ciphertext)
	except InvalidToken:
		raise ValueError("Incorrect password or corrupted encrypted data")
	
	encrypted = json.loads(decrypted_bytes.decode())
	
	return plain, encrypted