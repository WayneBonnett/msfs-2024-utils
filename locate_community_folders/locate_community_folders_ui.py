import os
import re
import tkinter as tk
from tkinter import ttk, messagebox


# Function to locate MSFS Community folder
def locate_community_folder(paths: dict):
    for type, path in paths.items():
        if os.path.exists(path):
            with open(path, 'r') as file:
                for line in file:
                    match = re.search(r'InstalledPackagesPath\s*"(.+?)"', line)
                    if match:
                        return type, os.path.abspath(os.path.join(match.group(1), 'Community'))
            return type, os.path.abspath(os.path.join(os.path.dirname(path), 'Packages', 'Community'))
    return None, None


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


# Copy to clipboard function
def copy_to_clipboard(path):
    root.clipboard_clear()
    root.clipboard_append(path)
    root.update()
    tk.messagebox.showinfo("Copied", "Path copied to clipboard!")


# Update paths in UI
def update_paths():
    # MSFS 2020
    cfg20_type, cfg20_path = locate_community_folder(msfs_2020_paths)
    if cfg20_path:
        msfs2020_label_var.set(f"MSFS 2020 ({cfg20_type})")
        msfs2020_var.set(cfg20_path)
    else:
        msfs2020_label_var.set("MSFS 2020 (Not Found)")
        msfs2020_var.set("Community folder not found.")

    # MSFS 2024
    cfg24_type, cfg24_path = locate_community_folder(msfs_2024_paths)
    if cfg24_path:
        msfs2024_label_var.set(f"MSFS 2024 ({cfg24_type})")
        msfs2024_var.set(cfg24_path)
    else:
        msfs2024_label_var.set("MSFS 2024 (Not Found)")
        msfs2024_var.set("Community folder not found.")


# GUI Application
root = tk.Tk()
root.title("MSFS Community Folder Locator")
root.geometry("700x250")
root.resizable(False, False)

# Title Label
title_label = tk.Label(root, text="Microsoft Flight Simulator Community Folder Locator", font=("Arial", 14))
title_label.pack(pady=10)

# MSFS 2020 Section
msfs2020_label_var = tk.StringVar(value="MSFS 2020")
msfs2020_label = tk.Label(root, textvariable=msfs2020_label_var, font=("Arial", 10, "bold"))
msfs2020_label.pack(anchor="w", padx=20)

msfs2020_frame = tk.Frame(root)
msfs2020_frame.pack(padx=20, pady=5, fill="x")

msfs2020_var = tk.StringVar()
msfs2020_entry = ttk.Entry(msfs2020_frame, textvariable=msfs2020_var, width=70, state='readonly')
msfs2020_entry.pack(side="left", fill="x", expand=True)

msfs2020_copy_btn = tk.Button(msfs2020_frame, text="Copy", command=lambda: copy_to_clipboard(msfs2020_var.get()))
msfs2020_copy_btn.pack(side="right", padx=5)

# MSFS 2024 Section
msfs2024_label_var = tk.StringVar(value="MSFS 2024")
msfs2024_label = tk.Label(root, textvariable=msfs2024_label_var, font=("Arial", 10, "bold"))
msfs2024_label.pack(anchor="w", padx=20)

msfs2024_frame = tk.Frame(root)
msfs2024_frame.pack(padx=20, pady=5, fill="x")

msfs2024_var = tk.StringVar()
msfs2024_entry = ttk.Entry(msfs2024_frame, textvariable=msfs2024_var, width=70, state='readonly')
msfs2024_entry.pack(side="left", fill="x", expand=True)

msfs2024_copy_btn = tk.Button(msfs2024_frame, text="Copy", command=lambda: copy_to_clipboard(msfs2024_var.get()))
msfs2024_copy_btn.pack(side="right", padx=5)

# Buttons
button_frame = tk.Frame(root)
button_frame.pack(pady=20)

refresh_btn = tk.Button(button_frame, text="Refresh Paths", command=update_paths)
refresh_btn.grid(row=0, column=0, padx=10)

quit_btn = tk.Button(button_frame, text="Quit", command=root.quit)
quit_btn.grid(row=0, column=1, padx=10)

# Initial path detection
update_paths()

# Start GUI Loop
root.mainloop()
