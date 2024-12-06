# Walk through the root community folder and all its subfolders, finding files with the name 'contenthistory.json'.
# Parse those files as JSON, and find the "items" field, then the "type" field inside it. If it's "Airport", note
# the "content" field, which is going to be the airport's ICAO code.
# Then, look for any subfolder in the root streamed packages folder that contiains that ICAO code in its name.
# Make sure that a subfolder with the same name exists in the root community folder. Report if there is or not.
version = '0.4.3'

import argparse
import os
import json
import sys

def os_walk_long_path(root_path):
    list = os.listdir(root_path)
    dirs = [x for x in list if os.path.isdir(os.path.join(root_path, x))]
    files = [x for x in list if os.path.isfile(os.path.join(root_path, x))]
    yield root_path, dirs, files
    for dir in dirs:
        for root, dirs, files in os_walk_long_path(os.path.join(root_path, dir)):
            yield root, dirs, files

def redirect_print(output_func=None):
    """
    Helper to redirect print statements.
    If `output_func` is provided, all print statements will call `output_func` instead of writing to stdout.
    """
    class PrintRedirector:
        def write(self, message):
            if output_func:
                output_func(message)
            else:
                sys.__stdout__.write(message)
        def flush(self):  # Required to support file-like behavior
            pass

    sys.stdout = PrintRedirector()
    sys.stderr = PrintRedirector()

def find_airports_in_community_folder(root_folder, verbose):
    airports = {}
    for root, dirs, files in os_walk_long_path(root_folder):
        if '-gsx-' in root.lower() or '-asobo-' in root.lower() or '-microsoft-' in root.lower():
            continue
        for file in files:
            if file.lower() == 'contenthistory.json':
                with open(os.path.join(root, file), 'r') as f:
                    contentinfo = json.load(f)
                    if 'items' in contentinfo:
                        for item in contentinfo['items']:
                            if 'type' in item and item['type'] == 'Airport':
                                root_two_levels_up = os.path.dirname(os.path.dirname(root.replace("\\\\?\\", ""))).split('\\')[-1]
                                airports[item['content']] = root_two_levels_up
                                if verbose:
                                    print(f"INFO: Found modded airport {item['content']} in {root_two_levels_up}")
    return airports

def find_airport_in_streamed_packages_folder(root_folder, airport):
    for dir in os.listdir(root_folder):
        if 'landingchallenge' in dir.lower():
            continue
        if f'-{airport.lower()}-' in dir.lower():
            return dir
    return None

# For any airports in the community folder that does have a streamed package equivalent, make sure the streamed
# package folder also exists in the community folder.
def check_airports_in_streamed_packages_folder(root_community_folder, root_streamed_packages_folder, report_existing, verbose):
    missing_streamed_package_overrides = {}
    existing_streamed_package_overrides = {}
    print(f"PROGRESS: Finding airports in the community folder...")
    airports = find_airports_in_community_folder(root_community_folder, verbose)
    print(f"PROGRESS: Checking streamed package overrides in the community folder...")
    for airportICAO in airports.keys():
        streamed_package_folder = find_airport_in_streamed_packages_folder(root_streamed_packages_folder, airportICAO)
        if streamed_package_folder:
            if not os.path.exists(os.path.join(root_community_folder, streamed_package_folder)):
                missing_streamed_package_overrides[streamed_package_folder] = airports[airportICAO]
                if verbose:
                    print(f"WARNING: Modded airport {airportICAO} has a streamed package ({streamed_package_folder}), but no override in the community folder.")
            else:
                existing_streamed_package_overrides[streamed_package_folder] = airports[airportICAO]
                if verbose:
                    print(f"INFO: Modded airport {airportICAO} has a streamed package override in the community folder.")
        else:
            if verbose:
                print(f"INFO: Modded airport {airportICAO} has no streamed package.")
    return existing_streamed_package_overrides if report_existing else missing_streamed_package_overrides

def autodetect_community_folder():
    root_community_folder = None
    # try to automatically determine the community folder by parsing 
    # '%localappdata%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalCache\usercfg.opt' 
    # and looking for the 'InstalledPackagesPath' key
    usercfg_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Packages', 'Microsoft.Limitless_8wekyb3d8bbwe', 'LocalCache', 'usercfg.opt')
    if not os.path.exists(usercfg_path):
        usercfg_path = os.path.join(os.getenv('APPDATA'), 'Microsoft Flight Simulator 2024', 'usercfg.opt')
    if os.path.exists(usercfg_path):
        with open(usercfg_path, 'r') as f:
            for line in f:
                if 'InstalledPackagesPath' in line:
                    root_installed_packages_folder = line.split(' ', 1)[1].strip().replace('"', '')
                    root_community_folder = os.path.join(root_installed_packages_folder, 'Community')
                    break
    return root_community_folder

def autodetect_streamed_packages_folder():
    root_streamed_packages_folder = None
    # try to automatically determine the streamed packages folder by looking for 
    # '%localappdata%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalState\StreamedPackages'
    root_streamed_packages_folder = os.path.join(os.getenv('LOCALAPPDATA'), 'Packages', 'Microsoft.Limitless_8wekyb3d8bbwe', 'LocalState', 'StreamedPackages')
    if not os.path.exists(root_streamed_packages_folder):
        root_streamed_packages_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft Flight Simulator 2024', 'StreamedPackages')
    return root_streamed_packages_folder
   
def main():
    print(f"check_airports.py v{version}")
    print()
    # use argparse to allow the user to specify the root folder
    parser = argparse.ArgumentParser(description='Check if streamed package overrides are present in the community folder.')
    parser.add_argument('--community', type=str, help='The root community folder to check.')
    parser.add_argument('--streamedpackages', type=str, help='The root streamed packages folder to check.')
    parser.add_argument('--verbose', action='store_true', help='Print verbose output.')
    parser.add_argument('--autofix', action='store_true', help='Automatically create missing streamed package overrides to the community folder as empty folders.')
    parser.add_argument('--autolink', action='store_true', help='Automatically create missing streamed package overrides to the community folder as links.')
    parser.add_argument('--delete', action='store_true', help='Delete all streamed package overrides in the community folder.')
    parser.add_argument('--noinput', action='store_true', help='Disable user input prompts.')
    args = parser.parse_args()
    
    if int(args.autofix) + int(args.autolink) + int(args.delete) > 1:
        print("ERROR: Only one of --autofix, --autolink, or --delete can be specified.")
        print()
        parser.print_help()
        return
    
    root_community_folder = args.community
    if not root_community_folder:
        root_community_folder = autodetect_community_folder()                    
    if not root_community_folder or not os.path.exists(root_community_folder):
        print("ERROR: No community folder specified, nor could one be found automatically.")
        print()
        parser.print_help()
        return
    print(f"INFO: Using community folder {root_community_folder}")
    root_community_folder = u"\\\\?\\" + root_community_folder.replace("/", "\\")
    
    root_streamed_packages_folder = args.streamedpackages
    if not root_streamed_packages_folder:
        root_streamed_packages_folder = autodetect_streamed_packages_folder()
    if not root_streamed_packages_folder or not os.path.exists(root_streamed_packages_folder):
        print("ERROR: No streamed packages folder specified, nor could one be found automatically.")
        print()
        parser.print_help()
        return
    print(f"INFO: Using streamed packages folder {root_streamed_packages_folder}")
    root_streamed_packages_folder = u"\\\\?\\" + root_streamed_packages_folder.replace("/", "\\")
    
    if args.delete:
        print()
        # for each folder in community that matches the name of a folder in streamedpackages and is a symlink or an empty folder, delete it
        print("PROGRESS: Deleting all streamed package overrides in the community folder...")
        for dir in os.listdir(root_community_folder):
            if os.path.isdir(os.path.join(root_community_folder, dir)) and os.path.exists(os.path.join(root_streamed_packages_folder, dir)):
                if os.path.islink(os.path.join(root_community_folder, dir)):
                    print(f"INFO: Unlinking override {dir}.")
                    os.rmdir(os.path.join(root_community_folder, dir))
                elif not os.listdir(os.path.join(root_community_folder, dir)):
                    print(f"INFO: Deleting empty folder override {dir}.")
                    os.rmdir(os.path.join(root_community_folder, dir))
    else:
        streamed_package_overrides = check_airports_in_streamed_packages_folder(root_community_folder, root_streamed_packages_folder, False, args.verbose)
        print("PROGRESS: Scan complete.")
        print()
        print("SUMMARY")
        if streamed_package_overrides:
            print(f"WARNING: The following streamed package overrides are missing from the community folder:")
            for streamed_package in streamed_package_overrides.keys():
                print(f"  {streamed_package}")
                if args.autolink:
                    print(f"    INFO: Creating link override for {streamed_package} in the community folder.")
                    os.symlink(os.path.join(root_community_folder, streamed_package_overrides[streamed_package]), os.path.join(root_community_folder, streamed_package), target_is_directory=True)
                elif args.autofix:
                    print(f"    INFO: Creating empty folder override for {streamed_package} in the community folder.")
                    os.makedirs(os.path.join(root_community_folder, streamed_package))
        else:
            print("INFO: All necessary streamed package overrides are present in the community folder.")
    if not args.noinput:
        print()
        # pause before exiting
        input("Press Enter to exit...")

if __name__ == '__main__':    
    main()
