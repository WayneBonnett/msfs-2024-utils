''' A script that watches for changes in the simulation rate, and adjusts the simulation time accordingly. 
    This doesn't work, but I wanted to keep a history of my attempt here, since it helped me realize just how
    broken the ZULU_..._SET events are in MSFS2024.
'''

import datetime
from time import sleep, time
from SimConnect import SimConnect, AircraftRequests, AircraftEvents

# Connect to the SimConnect server
simconnect = SimConnect()
aircraft_requests = AircraftRequests(simconnect, _time=0)
aircraft_events = AircraftEvents(simconnect)

original_zulu_time = None
original_zulu_day_of_year = None
original_zulu_year = None
is_original_zulu_year_leap_year = False
zulu_year_set = None
zulu_day_of_year_set = None
zulu_hours_set = None
zulu_minutes_set = None
clock_seconds_zero = None

# Request the current simulation rate
while original_zulu_time is None or original_zulu_day_of_year is None or original_zulu_year is None or zulu_year_set is None or zulu_day_of_year_set is None or zulu_hours_set is None or zulu_minutes_set is None:
    sleep(1)
    
    if original_zulu_day_of_year is None:
        zulu_day_of_year = int(aircraft_requests.get("ZULU_DAY_OF_YEAR"))
        if zulu_day_of_year is not None:
            print(f"Zulu day of year: {zulu_day_of_year}")
            original_zulu_day_of_year = zulu_day_of_year
    if original_zulu_year is None:
        zulu_year = int(aircraft_requests.get("ZULU_YEAR"))
        if zulu_year is not None:
            print(f"Zulu year: {zulu_year}")        
            original_zulu_year = zulu_year
            is_original_zulu_year_leap_year = zulu_year % 4 == 0 and (zulu_year % 100 != 0 or zulu_year % 400 == 0)
    if original_zulu_time is None:
        zulu_time = aircraft_requests.get("ZULU_TIME")
        if zulu_time is not None:
            print(f"Zulu time: {zulu_time}")
            original_zulu_time = zulu_time
    if zulu_year_set is None:
        zulu_year_set = aircraft_events.find("ZULU_YEAR_SET")
    if zulu_day_of_year_set is None:
        zulu_day_of_year_set = aircraft_events.find("ZULU_DAY_SET")
    if zulu_hours_set is None:
        zulu_hours_set = aircraft_events.find("ZULU_HOURS_SET")
    if zulu_minutes_set is None:
        zulu_minutes_set = aircraft_events.find("ZULU_MINUTES_SET")
    if clock_seconds_zero is None:
        clock_seconds_zero = aircraft_events.find("CLOCK_SECONDS_ZERO")

# convert original_zulu_day_of_year to month and day
month = 1
day = original_zulu_day_of_year
while day > 31:
    if month == 2:
        if is_original_zulu_year_leap_year:
            day -= 29
        else:
            day -= 28
    elif month in [4, 6, 9, 11]:
        day -= 30
    else:
        day -= 31
    month += 1
    
# convert original_zulu_time to hours, minutes, and seconds
original_zulu_time_int = int(original_zulu_time)
hours = original_zulu_time_int // 3600
minutes = (original_zulu_time_int % 3600) // 60
seconds = original_zulu_time_int % 60
print(f"Original zulu datetime: {month}/{day}/{original_zulu_year} {hours}:{minutes:02}:{seconds:02}")
seconds_elapsed = 0
last_irl_time = time()
last_sim_rate = 1.0
last_diff_in_minutes = 0

while True:
    sleep(0.25)
    #print("=====================================")
    
    real_life_zulu_time = datetime.datetime.now(datetime.timezone.utc)
    real_life_hour = real_life_zulu_time.hour
    real_life_zulu_time_top_of_hour = datetime.datetime(real_life_zulu_time.year, real_life_zulu_time.month, real_life_zulu_time.day, real_life_hour, 0, 0, tzinfo=datetime.timezone.utc)
    
    new_time = time()
    seconds_elapsed_this_time = new_time - last_irl_time
    last_irl_time = new_time
    
    sim_rate = aircraft_requests.get("SIMULATION_RATE")
    if sim_rate is not None:
        #print(f"Current simulation rate: {sim_rate}")
        last_sim_rate = sim_rate
        
    #print(f"Seconds elapsed this time: {seconds_elapsed_this_time:.1f}")
    seconds_elapsed_this_time *= last_sim_rate
    #print(f"Seconds elapsed this time (adjusted for sim rate): {seconds_elapsed_this_time:.1f}")
    seconds_elapsed += seconds_elapsed_this_time
    #print(f"Seconds elapsed: {seconds_elapsed:.1f}")
    
    new_zulu_time = round(original_zulu_time + seconds_elapsed)
    new_zulu_day_of_year = original_zulu_day_of_year
    new_zulu_year = original_zulu_year
    while new_zulu_time >= 24 * 60 * 60:
        new_zulu_time -= 24 * 60 * 60
        new_zulu_day_of_year += 1
        if new_zulu_day_of_year >= 365 + is_original_zulu_year_leap_year:            
            new_zulu_day_of_year -= 365 + is_original_zulu_year_leap_year
            new_zulu_year += 1
    
    # convert new_zulu_day_of_year to month and day
    month = 1
    day = new_zulu_day_of_year
    while day > 31:
        if month == 2:
            if new_zulu_year % 4 == 0 and (new_zulu_year % 100 != 0 or new_zulu_year % 400 == 0):
                day -= 29
            else:
                day -= 28
        elif month in [4, 6, 9, 11]:
            day -= 30
        else:
            day -= 31
        month += 1
        
    # convert new_zulu_time to hours, minutes, and seconds
    hours = new_zulu_time // 3600
    minutes = (new_zulu_time % 3600) // 60
    seconds = new_zulu_time % 60
    
    #print(f"New zulu datetime: {month}/{day}/{new_zulu_year} {hours}:{minutes:02}:{seconds:02}")
    
    new_zulu_datetime = datetime.datetime(new_zulu_year, month, day, hours, minutes, seconds, tzinfo=datetime.timezone.utc)
    
    # Why? WHY DOES ANY OF THIS WORK LIKE THAT? WHY DOES ZULU_MINUTES_SET SET A MINUTE OFFSET OFF OF THE TOP OF THE REAL LIFE HOUR?!?!
    diff_in_minutes = int((new_zulu_datetime - real_life_zulu_time_top_of_hour).total_seconds() // 60)
    if diff_in_minutes != last_diff_in_minutes:
        print("=====================================")
        print(f"New zulu datetime: {month}/{day}/{new_zulu_year} {hours}:{minutes:02}:{seconds:02}")
        print(f"Diff in minutes: {diff_in_minutes}")
        last_diff_in_minutes = diff_in_minutes
        zulu_minutes_set(diff_in_minutes)
        clock_seconds_zero() # This does nothing, womp womp
    
    #if new_zulu_year != original_zulu_year:
    #    zulu_year_set(new_zulu_year)
    #if new_zulu_day_of_year != original_zulu_day_of_year:
    #    zulu_day_of_year_set(new_zulu_day_of_year)
    #if seconds == 0 and new_zulu_time // 60 != original_zulu_time_int // 60:
    #    clock_seconds_zero()
    #    zulu_minutes_set(hours * 60 + minutes)
    
