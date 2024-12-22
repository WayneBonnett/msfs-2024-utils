""" Figure out max number of passengers and freight for a given simbrief plan """

# pylint: disable=line-too-long

import argparse
import json
import locale
import math
import requests
import os.path
import sys

VERSION = "0.1.1"

locale.setlocale(locale.LC_ALL, '')

print("=================================================")
print(f"Simbrief Passenger2 Calculator v{VERSION}")
print("=================================================")

# Load known airframes
known_airframes = {}
bundled_exe_dir = os.path.abspath(os.path.dirname(sys.executable))
airframes_path = os.path.join(bundled_exe_dir, "airframes.json")
if not os.path.exists(airframes_path):
    airframes_path = "airframes.json"
if not os.path.exists(airframes_path):
    airframes_path = ""
if airframes_path:
    try:
        with open(airframes_path, "r", encoding="utf8") as f:
            known_airframes = json.load(f)
            print(f"Loaded {len(known_airframes)} known airframes from airframes.json")
            print("=================================================")
    except Exception as e:
        print(f"Failed to load known airframes from airframes.json: {e}")

# Read arguments
parser = argparse.ArgumentParser()
parser.add_argument("--username", type=str, default=None)
parser.add_argument("--airframe", type=str, default=None)
parser.add_argument("--desired_pax", type=int, default=None)
parser.add_argument("--desired_freight", type=int, default=None)
parser.add_argument("--update", type=int, nargs=2, default=None)
args = parser.parse_args()

if args.desired_pax is not None and args.desired_freight is not None:
    raise ValueError("You can't specify both desired_pax and desired_freight")

any_args = args.username is not None or args.airframe is not None or args.desired_pax is not None or args.desired_freight is not None
if args.username is None:
    # Prompt the user for their SimBrief username
    args.username = input("Enter your SimBrief username: ")

airframe : dict[str, object] | None = {}
max_pax = 0
if args.airframe is None:
    # Prompt the user for the airframe
    args.airframe = input("Enter the airframe id (empty for custom): ")
    if args.airframe == "":
        # Prompt the user for the details of the custom airframe
        max_pax = int(input("Enter the maximum number of passengers: "))

if args.airframe != "":
    # Get airframe data
    # Find the airframe in the known_airframes dictionary via the airframe argument, either as the dictionary key or the "id" value
    airframe = known_airframes.get(args.airframe) or next((airframe for airframe in known_airframes.values() if airframe["id"] == args.airframe), None)
    if airframe is None:
        raise ValueError(f"Unknown airframe: {args.airframe}")
    max_pax = int(airframe["max_pax"])

show_prompt = not any_args

while True:
    if show_prompt:
        # Reset these on a subsequent loop
        args.desired_pax = None
        args.desired_freight = None
        while True:
            print("=================================================")
            print("Select one of the following:")
            print("(1) Calculate max number of passengers and freight based on max passengers")
            print("(2) Calculate max freight based on desired number of passengers")
            print("(3) Calculate max number of passengers based on desired freight")
            print("(4) Update Simbrief OFP with final values from P2")
            print("(0) Exit")
            input_value = input("Select option: ")
            if input_value == "0":
                import sys
                sys.exit(0)
            elif input_value == "1":
                break
            elif input_value == "2":
                args.desired_pax = int(input("Enter the desired number of passengers: "))
                break
            elif input_value == "3":
                args.desired_freight = int(input("Enter the desired freight: "))
                break
            elif input_value == "4":
                pax = int(input("Enter the final number of passengers: "))
                freight = int(input("Enter the final freight: "))
                args.update = (pax, freight)
                break

    if args.update:
        simbrief_dispatch_update_url = f"https://dispatch.simbrief.com/options/latest?pax={args.update[0]}&cargo={args.update[1]/1000.0}"
        # launch default browser with the URL
        import webbrowser
        webbrowser.open(simbrief_dispatch_update_url)
        import sys
        sys.exit(0)

    # get the latest simbrief ofp json
    simbrief_ofp_url = f"https://www.simbrief.com/api/xml.fetcher.php?username={args.username}&json=1"
    response = requests.get(simbrief_ofp_url, timeout=10)
    response.raise_for_status()
    simbrief_ofp = response.json()

    print("=================================================")
    print("Simbrief OFP Info")
    print("=================================================")    
    max_zerofuel_weight = float(simbrief_ofp["weights"]["max_zfw"])
    print(f"Max zero fuel weight: {int(max_zerofuel_weight):n}")
    ezfw = float(simbrief_ofp["weights"]["est_zfw"])
    print(f"Estimated zero fuel weight: {int(ezfw):n}")
    remaining_zerofuel_weight = max_zerofuel_weight - ezfw
    print(f"Remaining zero fuel weight: {int(remaining_zerofuel_weight):n}")
    
    block_fuel = int(simbrief_ofp["fuel"]["taxi"]) + int(simbrief_ofp["fuel"]["enroute_burn"]) + int(simbrief_ofp["fuel"]["contingency"]) + int(simbrief_ofp["fuel"]["alternate_burn"]) + int(simbrief_ofp["fuel"]["reserve"]) + int(simbrief_ofp["fuel"]["etops"]) + int(simbrief_ofp["fuel"]["extra"])
    print(f"Block fuel: {block_fuel:n}")
    
    zfw_to_block_fuel_ratio = ezfw / block_fuel
    print(f"Zero fuel weight to block fuel ratio: {zfw_to_block_fuel_ratio:.2f}")
    
    max_takeoff_weight = float(simbrief_ofp["weights"]["max_tow"])
    print(f"Max takeoff weight: {int(max_takeoff_weight):n}")
    etow = float(simbrief_ofp["weights"]["est_tow"])
    print(f"Estimated takeoff weight: {int(etow):n}")
    remaining_takeoff_weight = max_takeoff_weight - etow
    print(f"Remaining takeoff weight: {int(remaining_takeoff_weight):n}")
    
    cargo_per_pax = float(simbrief_ofp["weights"]["bag_weight"])
    print(f"Cargo per pax: {cargo_per_pax}")
    person_weight_per_pax = float(simbrief_ofp["weights"]["pax_weight"])
    print(f"Person weight per pax: {person_weight_per_pax}")
    total_zfw_per_pax = person_weight_per_pax + cargo_per_pax
    print(f"Total zero fuel weight per pax: {total_zfw_per_pax:.2f}")    
    total_tow_per_pax = total_zfw_per_pax + (total_zfw_per_pax / zfw_to_block_fuel_ratio)
    print(f"Total takeoff weight per pax: {total_tow_per_pax:.2f}")

    pax = int(simbrief_ofp["weights"]["pax_count_actual"])
    print(f"Actual pax: {pax}")
    bags = int(simbrief_ofp["weights"]["bag_count_actual"])
    print(f"Actual bags: {bags}")
    freight = int(simbrief_ofp["weights"]["freight_added"])
    print(f"Freight: {freight:n}")
    extra_cargo = float(simbrief_ofp["weights"]["cargo"]) - freight - bags * cargo_per_pax
    print(f"Extra cargo: {math.ceil(extra_cargo):n}")
    
    def tow_to_zfw(tow : float):
        return tow * zfw_to_block_fuel_ratio / (1 + zfw_to_block_fuel_ratio)
        
    def min_remaining_weight():
        return min(tow_to_zfw(remaining_takeoff_weight), remaining_zerofuel_weight)
    
    def modify_remaining_weights_by_zfw_delta(delta : float, do_print : bool = True):
        global remaining_zerofuel_weight, remaining_takeoff_weight
        remaining_zerofuel_weight += delta
        
        remaining_takeoff_weight += delta        
        block_fuel_removed = delta / zfw_to_block_fuel_ratio
        remaining_takeoff_weight += block_fuel_removed
        
        if do_print:
            print(f"Remaining zero fuel weight: {int(remaining_zerofuel_weight):n}")
            print(f"Remaining takeoff weight: {int(remaining_takeoff_weight):n}")

    print("=================================================")
    print("Calculations")
    print("=================================================")
    # We want every passenger to be able to bring a checked bag
    if bags < pax:
        print("Adjusting passengers so that everyone can bring a checked bag")
        removed_passengers = pax - bags
        print(f"Removing {removed_passengers} passengers")
        pax -= removed_passengers
        print(f"New pax: {pax}")
        modify_remaining_weights_by_zfw_delta(removed_passengers * person_weight_per_pax)
        print("=================================================")

    if args.desired_freight is None:
        final_freight = float(freight)        
        final_pax = pax
        
        # How many additional passengers with baggage could we add?
        additional_pax = int(min(min_remaining_weight() // total_zfw_per_pax, max_pax - pax))
        if additional_pax != 0:
            print(f"There's room for {additional_pax} extra passengers with baggage")

            final_pax = pax + additional_pax
            print(f"New pax: {final_pax}")
            
            # Assuming we take on the maximum number of additional passengers, do we still have room for freight?
            modify_remaining_weights_by_zfw_delta(-additional_pax * total_zfw_per_pax)
            
            additional_freight = min_remaining_weight()
            print(f"There's room for {int(additional_freight):n} extra freight")
            modify_remaining_weights_by_zfw_delta(-additional_freight)
            final_freight = freight + additional_freight
            print(f"New freight: {int(final_freight):n}")
            print("=================================================")

        # SimBrief likes to mess around with the average passenger weight instead of using a consistent average weight per passenger,
        # so our calculation might result in fewer passengers than the already valid simbrief flight plan
        if final_freight < 0 and additional_pax <= 0:
            final_pax = pax
            final_freight = 0

        # if max_freight is negative, we need to adjust the number of passengers until the freight is at least 0    
        if final_freight < 0:
            print("Removing passengers because we're overweight")
            removed_passengers = math.ceil(-final_freight / total_zfw_per_pax)
            print(f"Removing {removed_passengers} passengers")
            final_pax -= removed_passengers
            final_freight += removed_passengers * total_zfw_per_pax
            print("=================================================")

        if args.desired_pax is not None:
            print(f"New pax: {final_pax}")
            desired_pax = int(args.desired_pax)
            print(f"Desired pax: {desired_pax}")
            extra_pax = desired_pax - final_pax
            print(f"Extra pax: {extra_pax}")
            final_pax += extra_pax
            final_freight -= extra_pax * total_zfw_per_pax
            print(f"New freight: {int(final_freight):n}")
            print("=================================================")

            # if max_freight is negative, we need to adjust the number of passengers until the freight is at least 0
            if final_freight < 0:
                print("Removing passengers because we're overweight")
                removed_passengers = math.ceil(-final_freight / total_zfw_per_pax)
                print(f"Removing {removed_passengers} passengers")
                final_pax -= removed_passengers
                final_freight += removed_passengers * total_zfw_per_pax
                print("=================================================")
    else:
        desired_freight = int(args.desired_freight)
        print(f"Desired freight: {desired_freight:n}")
        extra_freight = desired_freight - freight
        print(f"Extra freight: {extra_freight:n}")
        modify_remaining_weights_by_zfw_delta(-extra_freight)
        additional_pax = int(min(min_remaining_weight() // total_zfw_per_pax, max_pax - pax))
        print(f"There's room for {additional_pax} extra passengers with baggage")
        modify_remaining_weights_by_zfw_delta(-additional_pax * total_zfw_per_pax)
        final_pax = pax + additional_pax
        final_freight = freight + extra_freight + min_remaining_weight()
        modify_remaining_weights_by_zfw_delta(-min_remaining_weight())
        print("=================================================")

    print(f"Final pax: {int(final_pax)}")
    print(f"Final max freight: {int(final_freight):n}")
    print("=================================================")
    input("Press Enter to continue...")
