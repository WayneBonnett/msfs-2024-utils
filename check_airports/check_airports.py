# Walk through the root community folder and all its subfolders, finding files with the name 'contenthistory.json'.
# Parse those files as JSON, and find the "items" field, then the "type" field inside it. If it's "Airport", note
# the "content" field, which is going to be the airport's ICAO code.
# Then, look for any subfolder in the root streamed packages folder that contiains that ICAO code in its name.
# Make sure that a subfolder with the same name exists in the root community folder. Report if there is or not.
version = '0.2'

import argparse
import os
import json

def find_airports_in_community_folder(root_folder, verbose):
    airports = []
    for root, dirs, files in os.walk(root_folder):
        if 'gsx' in root.lower():
            continue
        for file in files:
            if file.lower() == 'contenthistory.json':
                with open(os.path.join(root, file), 'r') as f:
                    contentinfo = json.load(f)
                    if 'items' in contentinfo:
                        for item in contentinfo['items']:
                            if 'type' in item and item['type'] == 'Airport':
                                airports.append(item['content'])
                                root_two_levels_up = os.path.dirname(os.path.dirname(root))
                                if verbose:
                                    print(f"INFO: Found modded airport {item['content']} in {root_two_levels_up}")
    return airports

def find_airport_in_streamed_packages_folder(root_folder, airport):
    for dir in os.listdir(root_folder):
        if 'landingchallenge' in dir.lower():
            continue
        if airport.lower() in dir.lower():
            return dir
    return None

# For any airports in the community folder that does have a streamed package equivalent, make sure the streamed
# package folder also exists in the community folder.
def check_airports_in_streamed_packages_folder(root_community_folder, root_streamed_packages_folder, verbose):
    missing_streamed_package_overrides = []
    print(f"PROGRESS: Finding airports in the community folder...")
    airports = find_airports_in_community_folder(root_community_folder, verbose)
    print(f"PROGRESS: Checking streamed package overrides in the community folder...")
    for airport in airports:
        streamed_package_folder = find_airport_in_streamed_packages_folder(root_streamed_packages_folder, airport)
        if streamed_package_folder:
            if not os.path.exists(os.path.join(root_community_folder, streamed_package_folder)):
                if verbose:
                    print(f"WARNING: Modded airport {airport} has a streamed package ({streamed_package_folder}), but no override in the community folder.")
                missing_streamed_package_overrides.append(streamed_package_folder)
            else:
                if verbose:
                    print(f"INFO: Modded airport {airport} has a streamed package override in the community folder.")
        else:
            if verbose:
                print(f"INFO: Modded airport {airport} has no streamed package.")
    return missing_streamed_package_overrides
   
def main():
    print(f"check_airports.py v{version}")
    print()
    # use argparse to allow the user to specify the root folder
    parser = argparse.ArgumentParser(description='Check if streamed package overrides are present in the community folder.')
    parser.add_argument('--community', type=str, help='The root community folder to check.')
    parser.add_argument('--streamedpackages', type=str, help='The root streamed packages folder to check.')
    parser.add_argument('--verbose', action='store_true', help='Print verbose output.')
    parser.add_argument('--autofix', action='store_true', help='Automatically create missing streamed package overrides to the community folder.')
    args = parser.parse_args()
    
    root_community_folder = args.community
    if not root_community_folder:
        # try to automatically determine the community folder by parsing 
        # '%localappdata%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalCache\usercfg.opt' 
        # and looking for the 'InstalledPackagesPath' key
        usercfg_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Packages', 'Microsoft.Limitless_8wekyb3d8bbwe', 'LocalCache', 'usercfg.opt')
        if os.path.exists(usercfg_path):
            with open(usercfg_path, 'r') as f:
                for line in f:
                    if 'InstalledPackagesPath' in line:
                        root_installed_packages_folder = line.split(' ', 1)[1].strip().replace('"', '')
                        root_community_folder = os.path.join(root_installed_packages_folder, 'Community')
                        break
                    
    if not root_community_folder or not os.path.exists(root_community_folder):
        print("ERROR: No community folder specified, nor could one be found automatically.")
        print()
        parser.print_help()
        return
    print(f"INFO: Using community folder {root_community_folder}")
    
    root_streamed_packages_folder = args.streamedpackages
    if not root_streamed_packages_folder:
        # check if %localappdata%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalState\StreamedPackages exists
        root_streamed_packages_folder = os.path.join(os.getenv('LOCALAPPDATA'), 'Packages', 'Microsoft.Limitless_8wekyb3d8bbwe', 'LocalState', 'StreamedPackages')
    if not root_streamed_packages_folder or not os.path.exists(root_streamed_packages_folder):
        print("ERROR: No streamed packages folder specified, nor could one be found automatically.")
        print()
        parser.print_help()
        return
    print(f"INFO: Using streamed packages folder {root_streamed_packages_folder}")
    
    missing_streamed_package_overrides = check_airports_in_streamed_packages_folder(root_community_folder, root_streamed_packages_folder, args.verbose)
    print("PROGRESS: Scan complete.")
    print()
    print("SUMMARY")
    if missing_streamed_package_overrides:
        print(f"WARNING: The following streamed package overrides are missing from the community folder:")
        for missing_streamed_package_override in missing_streamed_package_overrides:
            print(f"  {missing_streamed_package_override}")
            if args.autofix:
                print(f"    INFO: Automatically creating missing streamed package override {missing_streamed_package_override} in the community folder.")
                os.makedirs(os.path.join(root_community_folder, missing_streamed_package_override))
    else:
        print("INFO: All necessary streamed package overrides are present in the community folder.")
    print()
    # pause before exiting
    input("Press Enter to exit...")

if __name__ == '__main__':    
    main()
