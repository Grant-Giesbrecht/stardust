import numpy as np
from colorama import Fore, Style
import copy

def lin_to_dB(x_lin:float, use10:bool=False) -> float:
	''' Converts a linear parameter to decibels. Will raise a warning if
	negative numbers are provided.
	
	Args:
		x_lin (float): Linear value to convert to decibels
		use10 (bool): Use 10*log(X) definition instead of 20*log(X) definition. Default is false.
	
	Returns:
		(float): Value converted to dB
	'''
	
	if use10:
		return 10*np.log10(x_lin)
	else:
		return 20*np.log10(x_lin)

def dB_to_lin(x_dB:float, use10:bool=False) -> float:
	''' Converts a linear parameter to decibels. Will raise a warning if
	negative numbers are provided.
	
	Args:
		x_dB (float): Value in dB to convert to linear units.
		use10 (bool): Use 10*log(X) definition instead of 20*log(X) definition. Default is false.
	
	Returns:
		(float): Value converted to dB
	'''
	
	if use10:
		return np.log10(10, x_dB/10)
	else:
		return np.power(10, x_dB/20)

class UnitDefinition:
	
	def __init__(self, unit_type:str, name:str, to_SI, from_SI, is_SI:bool=False):
		
		self.name = name #ex: "Vrms"
		self.conversion_to_SI = to_SI # Equation to convert to SI
		self.conversion_from_SI = from_SI # Equation to convert to SI
		self.is_SI = False # Is this the SI unit?
		self.unit_type = unit_type # Ex: "elec-potential"

ELEC_POTENTIAL = "elec-potential-dc"
ELEC_POTENTIAL_AC = "elec-potential-ac"
DISTANCE = "distance"

def make_units():
	unit_list = []
	
	# Electric potential, DC
	unit_list.append(UnitDefinition(ELEC_POTENTIAL, "V", lambda x: x, lambda x: x, True))
	unit_list.append(UnitDefinition(ELEC_POTENTIAL, "mV", lambda x: x/1e3, lambda x: x*1e3))
	unit_list.append(UnitDefinition(ELEC_POTENTIAL, "uV", lambda x: x/1e6, lambda x: x*1e6))
	
	# Electric potential, AC
	unit_list.append(UnitDefinition(ELEC_POTENTIAL_AC, "Vrms", lambda x: x, lambda x: x, True))
	unit_list.append(UnitDefinition(ELEC_POTENTIAL_AC, "Vpp", lambda x: x/1.4142135623730951/2, lambda x: x*1.4142135623730951*2)) # 1.41... = sqrt(2)
	unit_list.append(UnitDefinition(ELEC_POTENTIAL_AC, "dBu", lambda x: dB_to_lin(x)*0.7745966692414834, lambda x: lin_to_dB(x/0.7745966692414834) )) # 0.7745 = sqrt(0.6)
	unit_list.append(UnitDefinition(ELEC_POTENTIAL_AC, "dBV", lambda x: dB_to_lin(x), lambda x: lin_to_dB(x) ))
	
	# Length
	unit_list.append(UnitDefinition(DISTANCE, "m", lambda x: x, lambda x: x, True))
	unit_list.append(UnitDefinition(DISTANCE, "km", lambda x: x*1e3, lambda x: x/1e3))
	unit_list.append(UnitDefinition(DISTANCE, "mi", lambda x: x*1609.344, lambda x: x/1609.344 )) # 0.7745 = sqrt(0.6)
	unit_list.append(UnitDefinition(DISTANCE, "ft", lambda x: x*0.3048, lambda x: x/0.3048 ))
	
	return unit_list

class UnitConverter:
	
	def __init__(self):
		
		self.unit_list = []
		self.unit_list = make_units()
	
	def view_unit_list(self):
		
		for unit_ in self.unit_list:
			
			print(f"{Fore.GREEN}UNIT: {Fore.WHITE}{unit_.name}{Style.RESET_ALL}")
			print(f"{Fore.GREEN}    UNIT TYPE: {Fore.YELLOW}{unit_.unit_type}{Style.RESET_ALL}")
			# print(f"{Fore.GREEN}    UNIT: {Fore.WHITE}{unit_.name}{Style.RESET_ALL")
		
	def convert(self, value:float, from_unit:str, to_unit:str):
		
		from_obj = None
		to_obj = None
		
		# look for to and from units
		for unit_ in self.unit_list:
			
			# Look for a match
			if unit_.name == from_unit:
				from_obj = copy.copy(unit_)
			if unit_.name == to_unit:
				to_obj = copy.copy(unit_)
			
			# Quit when both are found
			if (from_obj is not None) and (to_obj is not None):
				break
		
		if from_obj is None:
			raise Exception(f"Unrecognized unit type: {from_unit}")
		
		if to_obj is None:
			raise Exception(f"Unrecognized unit type: {to_unit}")
		
		si_val = from_obj.conversion_to_SI(value)
		return to_obj.conversion_from_SI(si_val)
