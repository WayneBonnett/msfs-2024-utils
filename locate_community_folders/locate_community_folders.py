import os
import re

# Function to locate MSFS Community folder
def locate_community_folder(paths : dict):
    for type, path in paths.items():
        if os.path.exists(path):
            with open(path, 'r') as file:
                for line in file:
                    match = re.search(r'InstalledPackagesPath\s*"(.+?)"', line)
                    if match:
                        return type, os.path.abspath(os.path.join(match.group(1), 'Community'))
            return type, os.path.abspath(os.path.join(os.path.dirname(path), 'Packages', 'Community'))
    return None

# Paths for MSFS 2020 UserCfg.opt
msfs_2020_paths = {
    "Steam": os.path.expandvars('%APPDATA%/Microsoft Flight Simulator/UserCfg.opt'),
    "MS Store": os.path.expandvars('%LOCALAPPDATA%/Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/UserCfg.opt')
}

# Paths for MSFS 2024 UserCfg.opt
msfs_2024_paths = {
    "Steam": os.path.expandvars('%APPDATA%/Microsoft Flight Simulator 2024/UserCfg.opt'),
    "MS Store": os.path.expandvars('%LOCALAPPDATA%/Packages/Microsoft.Limitless_8wekyb3d8bbwe/LocalCache/UserCfg.opt')
}

# Locate MSFS 2020 Community folder
cfg20_type, cfg20_path = locate_community_folder(msfs_2020_paths)
if cfg20_path:
    print(f'Your MSFS 2020 ({cfg20_type}) Community folder location: {cfg20_path}')
else:
    print("I can't find the MSFS 2020 Community folder.")

# Locate MSFS 2024 Community folder
cfg24_type, cfg24_path = locate_community_folder(msfs_2024_paths)
if cfg24_path:
    print(f'Your MSFS 2024 ({cfg24_type}) Community folder location: {cfg24_path}')
else:
    print("I can't find the MSFS 2024 Community folder.")

input("Press Enter to exit...")
