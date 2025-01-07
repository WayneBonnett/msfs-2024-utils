''' A script that watches for changes in the simulation rate, and adjusts the simulation time accordingly. '''

import ctypes
import logging
import os
import re
import struct
import subprocess
import sys
import threading
from time import sleep, time

import psutil
import pymem
from SimConnect import SimConnect, AircraftRequests, AircraftEvents

import constants

# Shared State Object
backend_state = {
    "connection_status": "Disconnected",
    "simconnect_status": "",
    "simulation_rate": 1.0,
    "seconds_offset": 0,
    "logs": [],
    "force_state_change": None,
    "autoapp_path": None,
    "autoapp_enabled": False
}
state_lock = threading.Lock()

def update_state(key, value):
    with state_lock:
        backend_state[key] = value

def log(message=""):
    with state_lock:
        backend_state["logs"].append(message)
    print(message)  # Keep console logging as well

log("=====================================")
log(f"MSFS2024 Sim Time Rate Adjuster v{constants.VERSION}")
log("=====================================")

# Hardcoded offset that stores the seconds offset from the real world time.
# This is quite likely to break in future MSFS updates.
HARDCODED_OFFSETS = [ 0x76f7728, 0x79670b8 ]
TRY_HARDCODED_OFFSETS_FIRST = True
POINTER_TO_WEATHER_STRUCT_SPACING = 0x20
SECONDS_OFFSET_VALUE_OFFSET_FROM_SECOND_POINTER = 0x34
SLEEP_TIME_AFTER_SIMCONNECT_EVENT = 0.5
REFRESH_INTERVAL = 0.25

def verify_seconds_offset_address(seconds_offset_address, pm, aircraft_events):
    seconds_offset = pm.read_float(seconds_offset_address)
    clock_minutes_dec_event = aircraft_events.find("CLOCK_MINUTES_DEC")
    clock_minutes_inc_event = aircraft_events.find("CLOCK_MINUTES_INC")
    clock_minutes_dec_event(1)
    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
    new_seconds_offset = pm.read_float(seconds_offset_address)
    if new_seconds_offset != seconds_offset - 60:
        return False
    clock_minutes_dec_event(1)
    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
    new_seconds_offset = pm.read_float(seconds_offset_address)
    if new_seconds_offset != seconds_offset - 120:
        return False
    clock_minutes_inc_event(1)
    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
    new_seconds_offset = pm.read_float(seconds_offset_address)
    if new_seconds_offset != seconds_offset - 60:
        return False
    clock_minutes_inc_event(1)
    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
    new_seconds_offset = pm.read_float(seconds_offset_address)
    if new_seconds_offset != seconds_offset:
        return False
    return True

def handle_autoapp(sim_rate, autoapp_path):
    autoapp_exe_name = os.path.basename(autoapp_path)
    autoapp_exe_name_lower = autoapp_exe_name.lower()
    
    def is_running():
        return any(p.name().lower() == autoapp_exe_name_lower for p in psutil.process_iter())
    
    if sim_rate > 1.0:
        if is_running():
            returncode = subprocess.run(f'taskkill /f /im "{autoapp_exe_name}"', check=False, creationflags=subprocess.CREATE_NO_WINDOW).returncode
            if returncode == 0 and not is_running():
                log(f"{autoapp_exe_name} killed.")
    else:
        if not is_running():
            dll_directory = None
            if hasattr(sys, 'frozen'):
                # If our app is 'frozen', we need to make sure the subprocess doesn't reuse our DLLs.
                # Otherwise, if we terminate before it, the DLLs will still be in use, and the temporary directory that
                # contains them will not be able to be automatically cleaned up.
                BUFFER_SIZE = 8192
                dll_directory = ctypes.create_string_buffer(BUFFER_SIZE)
                ctypes.windll.kernel32.GetDllDirectoryW(BUFFER_SIZE, dll_directory)
                ctypes.windll.kernel32.SetDllDirectoryW(None)
            subprocess.Popen(f'"{autoapp_path}"', cwd=os.path.dirname(autoapp_path), creationflags=subprocess.DETACHED_PROCESS)
            if is_running():
                log(f"{autoapp_exe_name} started.")
            if dll_directory:
                ctypes.windll.kernel32.SetDllDirectoryW(dll_directory)

def main(invoked_from_ui):
    logging.basicConfig(level=logging.INFO)
    
    while True:
        # Get the base module address for FlightSimulator2024.exe
        pm = None
        printed_waiting_to_start = False
        update_state("connection_status", "Waiting for FlightSimulator2024.exe to start...")
        while True:
            try:
                pm = pymem.Pymem("FlightSimulator2024.exe")
                break
            except pymem.exception.ProcessNotFound:
                if not printed_waiting_to_start:
                    log("Waiting for FlightSimulator2024.exe to start...")
                    printed_waiting_to_start = True
            except pymem.exception.CouldNotOpenProcess:
                log("Could not open FlightSimulator2024.exe process.")
                log("The script needs to run on the same level of elevation as MSFS 2024 itself.")
                log("If you're running the game as admin, you'll need to run this script as admin as well.")
                if not invoked_from_ui:
                    os.system("pause")
                    sys.exit(1)
            except Exception as ex:
                log(f"An error occurred: {ex}")
            sleep(1)

        base_address = pm.base_address

        simconnect = None
        printed_waiting_for_simconnect = False
        update_state("connection_status", "Waiting for SimConnect...")
        while True:
            try:
                simconnect = SimConnect()
                break
            except ConnectionError:
                if not printed_waiting_for_simconnect:
                    log("Waiting for SimConnect...")
                    printed_waiting_for_simconnect = True
            sleep(1)

        if not simconnect.ok:
            if not printed_waiting_for_simconnect:
                log("Waiting for SimConnect...")
                printed_waiting_for_simconnect = True
            while not simconnect.ok:
                sleep(1)

        if printed_waiting_for_simconnect:
            num_seconds_to_wait = 15
            while num_seconds_to_wait > 0:
                if not invoked_from_ui:
                    print(f"\rWaiting for things to settle down... {num_seconds_to_wait: 2} seconds remaining...", end="")
                else:
                    log(f"Waiting for things to settle down... {num_seconds_to_wait} seconds remaining...")
                sleep(1)
                num_seconds_to_wait -= 1
            log()

        update_state("connection_status", "Scanning...")
        
        aircraft_events = AircraftEvents(simconnect)

        log(f"Base address: 0x{base_address:X}")

        seconds_offset_address = 0x0
        seconds_offset = 0.0

        while seconds_offset_address == 0x0:
            if TRY_HARDCODED_OFFSETS_FIRST:
                for offset in HARDCODED_OFFSETS:
                    log()
                    log(f"Trying offset: 0x{offset:X}")
                    final_address = base_address + offset
                    log(f"Final address: 0x{final_address:X}")

                    # Scan the process memory for that address
                    log("Scanning process memory for the address...")
                    try:
                        found_addresses = pm.pattern_scan_all(re.escape(final_address.to_bytes(8, "little")), return_multiple=True)
                    except pymem.exception.WinAPIError:
                        continue
                    
                    # This will return a list of addresses where the pattern was found
                    for address in found_addresses:
                        log(f"Found at: {address:X}")
                    log()
                        
                    # Find the two instances that are 0x20 apart
                    for i in range(len(found_addresses) - 1):
                        if found_addresses[i + 1] - found_addresses[i] == POINTER_TO_WEATHER_STRUCT_SPACING:
                            log(f"Found base combo at: 0x{found_addresses[i]:X} and 0x{found_addresses[i + 1]:X}")
                            potential_seconds_offset_address = found_addresses[i+1] + SECONDS_OFFSET_VALUE_OFFSET_FROM_SECOND_POINTER
                            if verify_seconds_offset_address(potential_seconds_offset_address, pm, aircraft_events):
                                log("Verification successful")
                                seconds_offset_address = potential_seconds_offset_address
                            else:
                                log("Verification failed")
                                continue
                            log(f"Seconds offset address: 0x{seconds_offset_address:X}")
                            seconds_offset = pm.read_float(seconds_offset_address)
                            log(f"Current seconds offset: {int(seconds_offset)}")
                            break
                    if seconds_offset_address != 0x0:
                        break

            if seconds_offset_address == 0x0:
                # read the entire FlightSimulator2024.exe module memory
                log()
                log("Searching for the magic string in the module memory...")
                module_memory = pm.read_bytes(base_address, pm.process_base.SizeOfImage)
                lookup_string = br'Weather\Presets'
                offset = module_memory.find(lookup_string)
                if offset != -1:
                    offset -= 8
                    log(f"Trying offset: 0x{offset:X}")
                    final_address = base_address + offset
                    log(f"Final address: 0x{final_address:X}")

                    # Scan the process memory for that address
                    log("Scanning process memory for the address...")
                    try:
                        found_addresses = pm.pattern_scan_all(re.escape(final_address.to_bytes(8, "little")), return_multiple=True)
                    except pymem.exception.WinAPIError:
                        found_addresses = []
                    
                    if found_addresses:
                        for address in found_addresses:
                            log(f"Found at: {address:X}")
                        log()
                        
                    # Find the two instances that are 0x20 apart
                    for i in range(len(found_addresses) - 1):
                        if found_addresses[i + 1] - found_addresses[i] == POINTER_TO_WEATHER_STRUCT_SPACING:
                            log(f"Found base combo at: 0x{found_addresses[i]:X} and 0x{found_addresses[i + 1]:X}")
                            potential_seconds_offset_address = found_addresses[i+1] + SECONDS_OFFSET_VALUE_OFFSET_FROM_SECOND_POINTER
                            if verify_seconds_offset_address(potential_seconds_offset_address, pm, aircraft_events):
                                log("Verification successful")
                                seconds_offset_address = potential_seconds_offset_address
                            else:
                                log("Verification failed")
                                continue
                            log(f"Seconds offset address: 0x{seconds_offset_address:X}")
                            seconds_offset = pm.read_float(seconds_offset_address)
                            log(f"Current seconds offset: {int(seconds_offset)}")
                            break
            
            if seconds_offset_address == 0x0:
                log()
                log("Could not find the seconds offset address using quick methods, attempting to detect offset via events.")
                log("This requires you to be currently using real time in-sim, otherwise this method will fail.")
                log("Please wait...")
                clock_minutes_dec_event = aircraft_events.find("CLOCK_MINUTES_DEC")
                clock_minutes_inc_event = aircraft_events.find("CLOCK_MINUTES_INC")
                clock_minutes_dec_event(1)
                sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
                found_addresses = []
                try:
                    byte_array = bytearray(struct.pack("<f", -60))
                    regex_pattern = re.escape(byte_array)
                    found_addresses = pm.pattern_scan_all(regex_pattern, return_multiple=True)
                except pymem.exception.WinAPIError:
                    pass
                if found_addresses:
                    clock_minutes_dec_event(1)
                    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
                    # Check which of the found addresses now contain a float -120
                    for address in found_addresses:
                        try:
                            if pm.read_float(address) == -120:
                                # Let's double confirm by incrementing twice and checking that the value changes to -60 and 0 each time
                                clock_minutes_inc_event(1)
                                sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
                                if pm.read_float(address) != -60:
                                    clock_minutes_dec_event(1)
                                    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
                                    continue
                                clock_minutes_inc_event(1)
                                sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
                                if pm.read_float(address) != 0:
                                    clock_minutes_dec_event(2)
                                    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
                                    continue
                                seconds_offset_address = address
                                log(f"Seconds offset address: 0x{seconds_offset_address:X}")
                                seconds_offset = pm.read_float(seconds_offset_address)
                                log(f"Current seconds offset: {int(seconds_offset)}")
                                break
                        except pymem.exception.MemoryReadError:
                            continue
                else:
                    clock_minutes_inc_event(1)
                    sleep(SLEEP_TIME_AFTER_SIMCONNECT_EVENT)
            
            if seconds_offset_address == 0x0:
                log()
                log("Could not find the seconds offset address. Retrying after 5 seconds...")
                sleep(5)
            
        log("=====================================")
        log("Initialization complete.")
        log("Monitoring for sim rate and pause state changes...")

        update_state("seconds_offset", int(seconds_offset))
        update_state("simconnect_status", f"OK: {simconnect.ok} - Paused: {simconnect.paused}")
        update_state("connection_status", "Connected")

        aircraft_requests = AircraftRequests(simconnect, _time=0)

        seconds_elapsed = 0.0
        seconds_elapsed_adjusted_for_sim_rate = 0.0
        last_irl_time = time()
        cur_sim_rate = None
        diff = 0.0

        try:
            while True:
                sleep(REFRESH_INTERVAL)
                #log("=====================================")
                    
                force_state_change = None
                autoapp_enabled = False
                autoapp_path = None
                with state_lock:
                    force_state_change = backend_state["force_state_change"]
                    autoapp_enabled = backend_state["autoapp_enabled"]
                    autoapp_path = backend_state["autoapp_path"]
                
                if force_state_change is not None:
                    if force_state_change == "pause":
                        log("Forcing pause...")
                        simconnect.paused = True
                    elif force_state_change == "resume":
                        log("Forcing resume...")
                        simconnect.paused = False
                    update_state("force_state_change", None)
                    
                new_time = time()
                seconds_elapsed_this_time = new_time - last_irl_time
                last_irl_time = new_time
                
                update_state("simconnect_status", f"OK: {simconnect.ok} - Paused: {simconnect.paused}")
                
                last_sim_rate = cur_sim_rate
                additional_state = ""
                if simconnect.paused:
                    cur_sim_rate = 0.0
                    additional_state = " (Paused)"
                else:
                    is_slew_active = aircraft_requests.get("IS_SLEW_ACTIVE")
                    if is_slew_active is not None and is_slew_active:
                        cur_sim_rate = 0.0
                        additional_state = " (Slew Mode Active)"
                    else:
                        sim_rate = aircraft_requests.get("SIMULATION_RATE")
                        if sim_rate is not None:
                            cur_sim_rate = sim_rate
                if cur_sim_rate != last_sim_rate:
                    log(f"Current simulation rate: {cur_sim_rate}x{additional_state}")
                    update_state("simulation_rate", f"{cur_sim_rate}x{additional_state}")
                    first_loop = last_sim_rate is None
                    acceleration_switched = not first_loop and cur_sim_rate != 0.0 and last_sim_rate != 0.0 and ((cur_sim_rate <= 1.0) == (last_sim_rate > 1.0))
                    if first_loop or acceleration_switched:
                        if autoapp_enabled and autoapp_path is not None and os.path.exists(autoapp_path):
                            threading.Thread(target=handle_autoapp, args=(cur_sim_rate, autoapp_path), daemon=True).start()
                    
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
                    log(f"Setting new seconds offset: {int(new_seconds_offset)}")
                    update_state("seconds_offset", int(new_seconds_offset))
                else:
                    seconds_offset = pm.read_float(seconds_offset_address)
                    update_state("seconds_offset", int(seconds_offset))
        except KeyboardInterrupt:
            log("Exiting...")
            sys.exit(0)
        except OSError:
            log("MSFS process likely exited.")
            update_state("connection_status", "Disconnected")
            sleep(3)
        except pymem.exception.MemoryReadError:
            log("Memory read error. MSFS process likely exited.")
            update_state("connection_status", "Disconnected")
            sleep(3)
        except pymem.exception.MemoryWriteError:
            log("Memory write error. MSFS process likely exited.")
            update_state("connection_status", "Disconnected")
            sleep(3)

if __name__ == "__main__":
    main(invoked_from_ui=False)
