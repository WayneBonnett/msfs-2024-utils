import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from check_airports import redirect_print, main, autodetect_community_folder, autodetect_streamed_packages_folder, version
import sys
import threading
import json

class AirportCheckerUI:
    def __init__(self, root):
        self.CONFIG_FILE = "config.json"
        
        self.root = root
        self.root.title(f"Airport Override Checker for MSFS 2024 - v{version}")
        
        # Restore window geometry from config file
        self.restore_window_position()
        
        # Community Folder Selection
        tk.Label(root, text="Community Folder:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.community_folder_var = tk.StringVar()
        tk.Entry(root, textvariable=self.community_folder_var, width=130).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(root, text="Browse", command=self.browse_community_folder).grid(row=0, column=2, padx=5, pady=5)
        
        # Streamed Packages Folder Selection
        tk.Label(root, text="Streamed Packages Folder:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.streamed_folder_var = tk.StringVar()
        tk.Entry(root, textvariable=self.streamed_folder_var, width=130).grid(row=1, column=1, padx=5, pady=5)
        
        self.restore_last_used_paths()
        if not self.community_folder_var.get():
            self.community_folder_var.set(autodetect_community_folder() or "")
            
        if not self.streamed_folder_var.get():
            # If we don't have a last used streamed folder, try to autodetect it
            self.streamed_folder_var.set(autodetect_streamed_packages_folder() or "")
        else:
            # If we have a last used streamed folder, see if it needs to be upgraded for SU1
            auto_streamed_folder_su1 = autodetect_streamed_packages_folder(["su1"])
            if auto_streamed_folder_su1 and auto_streamed_folder_su1 != self.streamed_folder_var.get():
                self.streamed_folder_var.set(auto_streamed_folder_su1)
        
        tk.Button(root, text="Browse", command=self.browse_streamed_folder).grid(row=1, column=2, padx=5, pady=5)
        
        # Options
        self.verbose_var = tk.BooleanVar()
        self.mode_var = tk.StringVar()
        self.mode_var.set("check")
        
        tk.Checkbutton(root, text="Verbose Output", variable=self.verbose_var).grid(row=2, column=0, padx=5, pady=0, sticky="w")
        tk.Radiobutton(root, text="Check For Missing Overrides", variable=self.mode_var, value="check").grid(row=2, column=1, padx=5, pady=0, sticky="w")
        tk.Radiobutton(root, text="Add Overrides: Links (Recommended)", variable=self.mode_var, value="autolink").grid(row=3, column=1, padx=5, pady=0, sticky="w")
        tk.Radiobutton(root, text="Add Overrides: Empty Folders", variable=self.mode_var, value="autofix").grid(row=4, column=1, padx=5, pady=0, sticky="w")
        tk.Radiobutton(root, text="Add Overrides: Disable in Content.xml", variable=self.mode_var, value="autodisable").grid(row=5, column=1, padx=5, pady=0, sticky="w")
        tk.Radiobutton(root, text="Remove non-Content.xml Overrides", variable=self.mode_var, value="delete").grid(row=6, column=1, padx=5, pady=0, sticky="w")
        
        # Run Button
        self.run_button = tk.Button(root, text="Run", command=self.run_check)
        self.run_button.grid(row=7, column=0, padx=5, pady=10, sticky="w")
        tk.Button(root, text="Save Log", command=self.save_log).grid(row=7, column=2, padx=5, pady=10)
        
        # Output Area
        self.output_area = scrolledtext.ScrolledText(root, width=70, height=20, wrap=tk.WORD)
        self.output_area.configure(font=("Consolas", 10))
        # make it read-only
        self.output_area.bind("<Key>", lambda e: "break")
        # make the output area's size span the rest of the window
        self.output_area.grid(row=8, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        root.grid_rowconfigure(8, weight=1)
        root.grid_columnconfigure(0, weight=1)
        self.output_area.grid_propagate(False)
        
        # Save window position on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        
    def save_log(self):
        filename = filedialog.asksaveasfilename(title="Save Log As", defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if filename:
            with open(filename, "w") as f:
                f.write(self.output_area.get("1.0", tk.END))
        
    def restore_window_position(self):
        try:
            with open(self.CONFIG_FILE, "r") as f:
                config = json.load(f)
                geometry = config.get("geometry", "1024x768")
                self.root.geometry(geometry)
        except (FileNotFoundError, json.JSONDecodeError):
            self.root.geometry("1024x768")  # Default geometry
            
    def restore_last_used_paths(self):
        try:
            with open(self.CONFIG_FILE, "r") as f:
                config = json.load(f)
                self.community_folder_var.set(config.get("community_folder", ""))
                self.streamed_folder_var.set(config.get("streamed_folder", ""))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def on_exit(self):
        config = {}
        # Save window geometry
        config["geometry"] = self.root.geometry()
        # Add the two paths last used to the config
        config["community_folder"] = self.community_folder_var.get()
        config["streamed_folder"] = self.streamed_folder_var.get()
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f)
        self.root.destroy()  # Close the application
    
    def browse_community_folder(self):
        folder = filedialog.askdirectory(title="Select Community Folder")
        if folder:
            self.community_folder_var.set(folder)
    
    def browse_streamed_folder(self):
        folder = filedialog.askdirectory(title="Select Streamed Packages Folder")
        if folder:
            self.streamed_folder_var.set(folder)
    
    def run_check(self):
        # Input validation
        community_folder = self.community_folder_var.get()
        streamed_folder = self.streamed_folder_var.get()
        verbose = self.verbose_var.get()
        mode = self.mode_var.get()

        if not community_folder or not os.path.exists(community_folder):
            messagebox.showerror("Error", "Please select a valid Community Folder.")
            return

        if not streamed_folder or not os.path.exists(streamed_folder):
            messagebox.showerror("Error", "Please select a valid Streamed Packages Folder.")
            return

        # Clear the output area
        self.output_area.delete("1.0", tk.END)

        # Redirect print output to the UI
        def print_to_ui(message):
            """Write captured print output to the text area."""
            self.output_area.insert(tk.END, message)
            self.output_area.see(tk.END)  # Auto-scroll to the bottom

        redirect_print(print_to_ui)  # Redirect prints to the UI
        self.run_button.config(state=tk.DISABLED)
        
        # Run check_airports logic in a separate thread to keep UI responsive
        def run_task():
            try:
                sys.argv = ["check_airports.py"]
                if verbose:
                    sys.argv.append("--verbose")
                if mode == "autofix":
                    sys.argv.append("--autofix")
                elif mode == "autolink":
                    sys.argv.append("--autolink")
                elif mode == "autodisable":
                    sys.argv.append("--autodisable")
                elif mode == "delete":
                    sys.argv.append("--delete")
                sys.argv.extend(["--community", community_folder, "--streamedpackages", streamed_folder])
                sys.argv.extend(["--noinput"])  # Disable user input prompts

                main()
            except Exception as e:
                print_to_ui(f"Error: {e}\n")
            finally:
                self.run_button.config(state=tk.NORMAL)
                redirect_print(None)  # Restore default behavior

        threading.Thread(target=run_task, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AirportCheckerUI(root)
    root.mainloop()
