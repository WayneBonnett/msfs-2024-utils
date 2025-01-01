''' A script that watches for changes in the simulation rate, and adjusts the simulation time accordingly. '''

import os
import re
import sys
from time import sleep, time

import pymem
from SimConnect import SimConnect, AircraftRequests, AircraftEvents

version = "0.1"

print(f"MSFS2024 Sim Time Rate Adjuster v{version}")
print("=====================================")

# Hardcoded offset that stores the seconds offset from the real world time.
# This is quite likely to break in future MSFS updates.
offset = 0x76f7728

# Get the base module address for FlightSimulator2024.exe
pm = None
printed_waiting_to_start = False
while True:
    try:
        pm = pymem.Pymem("FlightSimulator2024.exe")
        break
    except pymem.exception.ProcessNotFound:
        if not printed_waiting_to_start:
            print("Waiting for FlightSimulator2024.exe to start...")
            printed_waiting_to_start = True
    except pymem.exception.CouldNotOpenProcess:
        print("Could not open FlightSimulator2024.exe process.")
        print("The script needs to run on the same level of elevation as MSFS 2024 itself.")
        print("If you're running the game as admin, you'll need to run this script as admin as well.")
        os.system("pause")
    sleep(1)

base_address = pm.base_address

simconnect = None
printed_waiting_for_simconnect = False
while True:
    try:
        simconnect = SimConnect()
        break
    except ConnectionError:
        if not printed_waiting_for_simconnect:
            print("Waiting for SimConnect...")
            printed_waiting_for_simconnect = True
    sleep(1)

if not simconnect.ok:
    if not printed_waiting_for_simconnect:
        print("Waiting for SimConnect...")
        printed_waiting_for_simconnect = True
    while not simconnect.ok:
        sleep(1)
                
print(f"Base address: 0x{base_address:X}")
print(f"Offset: 0x{offset:X}")
final_address = base_address + offset
print(f"Final address: 0x{final_address:X}")

# Scan the process memory for that address
print("Scanning process memory for the address...")
found_addresses = pm.pattern_scan_all(re.escape(final_address.to_bytes(8, "little")), return_multiple=True)
# This will return a list of addresses where the pattern was found
for address in found_addresses:
    print(f"Found at: {address:X}")
print()

seconds_offset_address = 0x0
    
# Find the two instances that are 0x20 apart
for i in range(len(found_addresses) - 1):
    if found_addresses[i + 1] - found_addresses[i] == 0x20:
        print(f"Found base combo at: 0x{found_addresses[i]:X} and 0x{found_addresses[i + 1]:X}")
        seconds_offset_address = found_addresses[i+1] + 0x34
        print(f"Seconds offset address: 0x{seconds_offset_address:X}")
        seconds_offset = pm.read_float(seconds_offset_address)
        print(f"Current seconds offset: {int(seconds_offset)}")
        break

if seconds_offset_address == 0x0:
    print("Could not find the seconds offset address.")
    sys.exit(-1)
    
print("=====================================")
print("Initialization complete.")
print("Monitoring for sim rate and pause state changes...")

aircraft_requests = AircraftRequests(simconnect, _time=0)
aircraft_events = AircraftEvents(simconnect)

seconds_elapsed = 0.0
seconds_elapsed_adjusted_for_sim_rate = 0.0
last_irl_time = time()
cur_sim_rate = 1.0
diff = 0.0

try:
    while True:
        sleep(0.25)
        #print("=====================================")
            
        new_time = time()
        seconds_elapsed_this_time = new_time - last_irl_time
        last_irl_time = new_time
        
        last_sim_rate = cur_sim_rate
        if simconnect.paused:
            cur_sim_rate = 0.0
        else:
            is_slew_active = aircraft_requests.get("IS_SLEW_ACTIVE")
            if is_slew_active is not None and is_slew_active:
                cur_sim_rate = 0.0
            else:
                sim_rate = aircraft_requests.get("SIMULATION_RATE")
                if sim_rate is not None:
                    cur_sim_rate = sim_rate
        if cur_sim_rate != last_sim_rate:
            print(f"Current simulation rate: {cur_sim_rate}")
        seconds_elapsed_this_time_adjusted_for_sim_rate = seconds_elapsed_this_time * cur_sim_rate
        
        seconds_elapsed += seconds_elapsed_this_time
        seconds_elapsed_adjusted_for_sim_rate += seconds_elapsed_this_time_adjusted_for_sim_rate
        
        diff += seconds_elapsed_this_time_adjusted_for_sim_rate - seconds_elapsed_this_time
        if int(abs(diff)) >= 1:
            diff_int = int(diff)
            diff -= diff_int
            seconds_offset = pm.read_float(seconds_offset_address)
            new_seconds_offset = seconds_offset + diff_int
            pm.write_float(seconds_offset_address, new_seconds_offset)
            print(f"Setting new seconds offset: {int(new_seconds_offset)}")
except KeyboardInterrupt:
    print("Exiting...")
    sys.exit(0)
except OSError:
    print("MSFS process likely exited. Exiting...")
    sys.exit(0)
except pymem.exception.MemoryReadError:
    print("Memory read error. MSFS process likely exited. Exiting...")
    sys.exit(0)
except pymem.exception.MemoryWriteError:
    print("Memory write error. MSFS process likely exited. Exiting...")
    sys.exit(0)
