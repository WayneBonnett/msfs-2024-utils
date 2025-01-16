''' This file contains the UI code for the Sim Time Rate Adjuster for MSFS 2024. '''

import datetime
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from threading import Thread
from typing import Optional

import humanize
from tkcalendar import DateEntry  # type: ignore
import win32event
import win32api

import constants
from sim_time_rate_adjuster_procmem import main, backend_state, state_lock

#pylint: disable=line-too-long,missing-function-docstring,missing-class-docstring

def sanitize_path(path):
    return path.replace('/', '\\')

class SimAdjusterUI:
    # config file under appdata
    CONFIG_FILE = "config.json"
    DEFAULT_GEOMETRY = "+0+0"

    def __init__(self, main_window):
        self.root = main_window
        self.root.title(f"Sim Time Rate Adjuster v{constants.VERSION}")

        # --- Connection Status ---
        self.connection_status_label = ttk.Label(main_window, text="Connection Status: Disconnected", foreground="red")
        self.connection_status_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # --- SimConnect Status ---
        self.simconnect_status_label = ttk.Label(main_window, text="SimConnect Status: N/A")
        self.simconnect_status_label.grid(row=1, column=0, sticky="w", padx=10, pady=5)

        # --- Time Labels ---
        self.system_time_label = ttk.Label(main_window, text="System Time: N/A")
        self.system_time_label.grid(row=2, column=0, sticky="w", padx=10, pady=5)

        self.in_sim_time_label = ttk.Label(main_window, text="In-Sim Time: N/A")
        self.in_sim_time_label.grid(row=3, column=0, sticky="w", padx=10, pady=5)

        # --- Simulation Rate ---
        self.sim_rate_label = ttk.Label(main_window, text="Simulation Rate: N/A")
        self.sim_rate_label.grid(row=4, column=0, sticky="w", padx=10, pady=5)

        # --- Seconds Offset ---
        self.seconds_offset_label = ttk.Label(main_window, text="Seconds Offset: N/A")
        self.seconds_offset_label.grid(row=5, column=0, sticky="w", padx=10, pady=5)

        button_frame = ttk.Frame(main_window)
        button_frame.grid(row=6, column=0, columnspan=3, sticky="w", padx=10, pady=5)

        # --- Expandable Output Console ---
        self.expand_button = ttk.Button(button_frame, text="Expand Console", command=self.toggle_console)
        self.expand_button.grid(row=0, column=0, padx=5)

        # -- Force Pause / Resume Buttons --
        self.force_pause_button = ttk.Button(
            button_frame,
            text="Force Pause",
            command=lambda: self.force_state_change("pause"),
            state='disabled'
        )
        self.force_pause_button.grid(row=0, column=1, padx=5)

        self.force_resume_button = ttk.Button(
            button_frame,
            text="Force Resume",
            command=lambda: self.force_state_change("resume"),
            state='disabled'
        )
        self.force_resume_button.grid(row=0, column=2, padx=5)

        # -- Reset Time Button --
        self.reset_time_button = ttk.Button(
            button_frame,
            text="Reset Time...",
            command=self.open_reset_window,
            state='disabled'
        )
        self.reset_time_button.grid(row=0, column=3, padx=5)

        self.console_frame = ttk.Frame(main_window)
        self.console_text = scrolledtext.ScrolledText(self.console_frame, wrap=tk.WORD, height=10, state='disabled')
        self.console_text.pack(fill=tk.BOTH, expand=True)
        self.auto_scroll = tk.BooleanVar(value=True)
        self.auto_scroll_check = ttk.Checkbutton(self.console_frame, text="Auto-Scroll", variable=self.auto_scroll)
        self.auto_scroll_check.pack(anchor='w')

        self.console_visible = False

        # --- Menu Bar ---
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Options", command=self.open_options_window)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        self.autoapp_path = ''
        self.autoapp_path_entry = None
        self.autoapp_enabled_var = tk.BooleanVar()
        self.options_window = None
        self.reset_window = None

        # Restore window geometry from config file
        self.restore_window_position()
        self.load_options()

        # --- Start Backend Thread ---
        self.backend_thread = Thread(target=lambda: main(True), daemon=True)
        self.backend_thread.start()

        # --- Start UI Update Loop ---
        self.update_ui()

        # --- Save window position on exit ----
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def force_state_change(self, state, custom_time: Optional[datetime.datetime] = None):
        with state_lock:
            backend_state['force_state_change'] = state
            if custom_time:
                if state == "reset":
                    backend_state['forced_seconds_offset'] = (custom_time - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                else:
                    self.log_to_console("ERROR: Custom time is only supported for reset operation.")
            else:
                backend_state['forced_seconds_offset'] = 0

    def toggle_console(self):
        if self.console_visible:
            self.console_frame.grid_forget()
            self.expand_button.config(text="Expand Console")
        else:
            self.console_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)
            self.expand_button.config(text="Collapse Console")
        self.console_visible = not self.console_visible

    def log_to_console(self, message):
        self.console_text.config(state='normal')
        self.console_text.insert(tk.END, message + "\n")
        if self.auto_scroll.get():
            self.console_text.see(tk.END)
        self.console_text.config(state='disabled')

    def open_options_window(self):
        self.options_window = tk.Toplevel(self.root)
        options_window = self.options_window
        options_window.withdraw()
        options_window.title("Options")
        options_window.grab_set()
        saved_geometry = self.load_setting("options_window_geometry", None)
        if saved_geometry:
            options_window.geometry(saved_geometry)

        notebook = ttk.Notebook(options_window)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # autoapp Tab
        autoapp_tab = ttk.Frame(notebook)
        notebook.add(autoapp_tab, text="App Restarter")

        # Path to autoapp .exe
        path_label = ttk.Label(autoapp_tab, text=".exe Path:")
        path_label.grid(row=0, column=0, padx=10, pady=10, sticky='w')

        self.autoapp_path_entry = ttk.Entry(autoapp_tab, width=50)
        self.autoapp_path_entry.grid(row=0, column=1, padx=10, pady=10)
        self.autoapp_path_entry.insert(0, self.autoapp_path)

        find_button = ttk.Button(autoapp_tab, text="Find", command=self.find_autoapp_exe)
        find_button.grid(row=0, column=2, padx=10, pady=10)

        # Auto Kill Checkbox
        auto_kill_checkbox = ttk.Checkbutton(
            autoapp_tab,
            text="Automatically kill selected application when Sim Rate is accelerated, and restart when it's at most 1x again",
            variable=self.autoapp_enabled_var
        )
        auto_kill_checkbox.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky='w')

        # OK and Cancel buttons
        button_frame = ttk.Frame(options_window)
        button_frame.pack(side='bottom', pady=10)

        ok_button = ttk.Button(button_frame, text="OK", command=self.on_options_ok)
        ok_button.pack(side='left', padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.on_options_cancel)
        cancel_button.pack(side='left', padx=5)

        # If the user presses Enter, assume they want to click OK
        options_window.bind("<Return>", lambda e: self.on_options_ok())

        # on window close, save window position
        options_window.protocol("WM_DELETE_WINDOW", self.on_options_cancel)

        options_window.after(200, options_window.deiconify)

    def find_autoapp_exe(self):
        file_path = filedialog.askopenfilename(
            title="Select autoapp Executable",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if file_path:
            self.autoapp_path_entry.delete(0, tk.END)
            self.autoapp_path_entry.insert(0, sanitize_path(file_path))

    def save_options_window_position(self):
        self.update_config({
            "options_window_geometry": "+" + str.split(self.options_window.geometry(), "+", maxsplit=1)[1]
        })

    def on_options_ok(self):
        with state_lock:
            self.autoapp_path = sanitize_path(self.autoapp_path_entry.get())
            backend_state['autoapp_path'] = self.autoapp_path
            backend_state['autoapp_enabled'] = self.autoapp_enabled_var.get()
        self.save_options()
        self.save_options_window_position()
        self.options_window.destroy()

    def on_options_cancel(self):
        self.save_options_window_position()
        self.options_window.destroy()

    def save_options(self):
        self.update_config({
            'autoapp_path': self.autoapp_path,
            'autoapp_enabled': self.autoapp_enabled_var.get()
        })

    def load_options(self):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r', encoding="utf-8") as config_file:
                try:
                    config = json.load(config_file)
                    autoapp_path = sanitize_path(config.get('autoapp_path', ''))
                    autoapp_enabled = config.get('autoapp_enabled', False)

                    self.autoapp_path = autoapp_path
                    self.autoapp_enabled_var.set(autoapp_enabled)

                    with state_lock:
                        backend_state['autoapp_path'] = autoapp_path
                        backend_state['autoapp_enabled'] = autoapp_enabled
                except json.JSONDecodeError:
                    pass

    def load_setting(self, setting, default):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r', encoding="utf-8") as config_file:
                try:
                    config = json.load(config_file)
                    return config.get(setting, default)
                except json.JSONDecodeError:
                    pass
        return default

    has_shown_thread_died_error = False

    def update_ui(self):
        if not self.backend_thread.is_alive() and not self.has_shown_thread_died_error:
            # Backend thread has exited, a fatal error must have happened
            # Bring up a dialog to inform the user, and exit
            messagebox.showerror("Sim Time Rate Adjuster for MSFS 2024", "The backend process has exited unexpectedly. Please check the logs for more information.\n\nYou will need to restart the application if you wish to continue.")
            self.has_shown_thread_died_error = True

        sim_rate = 1.0
        with state_lock:
            self.set_connection_status(backend_state['connection_status'])

            is_connected = backend_state['connection_status'] == "Connected"

            self.simconnect_status_label.config(text=f"SimConnect Status: {backend_state['simconnect_status']}" if is_connected else "SimConnect Status: Please wait...")

            sim_rate = backend_state['simulation_rate'] if is_connected else 1.0
            self.sim_rate_label.config(text=f"Simulation Rate: {backend_state['simulation_rate_display_str']}" if is_connected else "")

            system_time = datetime.datetime.now(datetime.timezone.utc)
            self.system_time_label.config(text=f"System Time (UTC): {system_time.strftime('%Y-%m-%d %H:%M:%S')}")

            seconds_offset_prefix = '- ' if backend_state['seconds_offset'] < 0 else ''
            seconds_offset_text = f"{seconds_offset_prefix}{humanize.precisedelta(backend_state['seconds_offset'])}"
            self.seconds_offset_label.config(text=f"In-Sim Time Offset: {seconds_offset_text}" if is_connected else "")

            system_time_with_offset = system_time + datetime.timedelta(seconds=backend_state['seconds_offset'])
            absolute_time = backend_state['absolute_time']
            # absolute_time is the number of seconds since midnight 1/1/1, so convert to a current datetime
            absolute_time_datetime = datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=absolute_time)
            in_sim_time_str = ""
            if is_connected:
                if abs((absolute_time_datetime - system_time_with_offset).total_seconds()) >= 2:
                    in_sim_time_str = f"In-Sim Time: {system_time_with_offset.strftime('%Y-%m-%d %H:%M:%S')} (Estimated) / {absolute_time_datetime.strftime('%Y-%m-%d %H:%M:%S')} (Reported)"
                else:
                    in_sim_time_str = f"In-Sim Time: {system_time_with_offset.strftime('%Y-%m-%d %H:%M:%S')}"
            self.in_sim_time_label.config(text=in_sim_time_str)

            while backend_state['logs']:
                self.log_to_console(backend_state['logs'].pop(0))

        refresh_rate = 1.0
        if sim_rate != 0.0:
            if sim_rate > 1.0:
                refresh_rate = sim_rate
            elif sim_rate < 1.0:
                refresh_rate = 1.0 / sim_rate
        self.root.after(int(1000 / refresh_rate), self.update_ui)

    def update_config(self, updates: dict):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                try:
                    config = json.load(f)
                except json.JSONDecodeError:
                    config = {}
        else:
            config = {}

        config.update(updates)

        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def save_window_position(self):
        self.update_config({
            "geometry": "+" + str.split(self.root.geometry(), "+", maxsplit=1)[1],
            "console_visible": self.console_visible,
            "auto_scroll": self.auto_scroll.get()
        })

    def restore_window_position(self):
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.root.geometry(config.get("geometry", self.DEFAULT_GEOMETRY))
                console_visible = config.get("console_visible", False)
                if console_visible:
                    self.toggle_console()
                self.auto_scroll.set(config.get("auto_scroll", True))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def on_exit(self):
        self.save_window_position()
        self.root.destroy()

    def update_button_states(self, connected):
        state = 'normal' if connected else 'disabled'
        self.force_pause_button.config(state=state)
        self.force_resume_button.config(state=state)
        self.reset_time_button.config(state=state)

    def set_connection_status(self, status):
        self.connection_status_label.config(
                text=f"Connection Status: {backend_state['connection_status']}",
                foreground="green" if backend_state['connection_status'] == "Connected" else ("orange" if "Scanning" in backend_state['connection_status'] else "red")
            )
        connected = status == "Connected"
        self.update_button_states(connected)

    def open_reset_window(self):
        self.reset_window = tk.Toplevel(self.root)
        reset_window = self.reset_window
        reset_window.withdraw()
        reset_window.title("Reset Time")
        reset_window.grab_set()  # Make the window modal
        saved_geometry = self.load_setting("reset_window_geometry", None)
        if saved_geometry:
            reset_window.geometry(saved_geometry)

        datetime_frame = ttk.Frame(reset_window)

        # Options: Live Time or Custom Time
        option_var = tk.StringVar(value="live")

        live_radio = ttk.Radiobutton(reset_window, text="Live Time", variable=option_var, value="live")
        live_radio.grid(row=0, column=0, padx=10, pady=10, sticky='w')
        # When clicked, disable the datetime picker
        live_radio.bind("<Button-1>", lambda e: [child.config(state='disabled') for child in datetime_frame.winfo_children()])

        custom_radio = ttk.Radiobutton(reset_window, text="Custom Time", variable=option_var, value="custom")
        custom_radio.grid(row=1, column=0, padx=10, pady=5, sticky='w')
        # When clicked, enable the datetime picker
        custom_radio.bind("<Button-1>", lambda e: [child.config(state='normal') for child in datetime_frame.winfo_children()])

        # Datetime picker (using tkcalendar)
        datetime_frame.grid(row=2, column=0, padx=10, pady=5, sticky='w')

        date_label = ttk.Label(datetime_frame, text="Select Date:")
        date_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky='w')

        system_time_with_offset = None
        with state_lock:
            system_time_with_offset = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=backend_state['seconds_offset'])

        date_entry = DateEntry(datetime_frame, width=12, background='darkblue',
                               foreground='white', borderwidth=2)
        date_entry.set_date(system_time_with_offset)
        date_entry.grid(row=0, column=1, pady=5, sticky='w')

        time_label = ttk.Label(datetime_frame, text="Select Time (HH:MM):")
        time_label.grid(row=1, column=0, padx=(0,5), pady=5, sticky='w')

        time_entry = ttk.Entry(datetime_frame)
        time_entry.insert(0, system_time_with_offset.strftime("%H:%M"))
        time_entry.grid(row=1, column=1, pady=5, sticky='w')

        # Disable all elements in the grid by default
        for child in datetime_frame.winfo_children():
            child.config(state='disabled')

        # OK and Cancel buttons
        button_frame = ttk.Frame(reset_window)
        button_frame.grid(row=3, column=0, padx=10, pady=10, sticky='e')

        def close_window():
            self.update_config({
                "reset_window_geometry": "+" + str.split(reset_window.geometry(), "+", maxsplit=1)[1]
            })
            reset_window.destroy()

        def on_ok():
            if option_var.get() == "custom":
                try:
                    selected_date = date_entry.get_date()
                    selected_time = time_entry.get()
                    try:
                        selected_datetime = datetime.datetime.combine(
                            selected_date,
                            datetime.datetime.strptime(selected_time, "%H:%M").time(),
                            tzinfo=datetime.timezone.utc
                        )
                    except ValueError:
                        selected_datetime = datetime.datetime.combine(
                            selected_date,
                            datetime.datetime.strptime(selected_time, "%H%M").time(),
                            tzinfo=datetime.timezone.utc
                        )
                    # Perform reset with selected_datetime
                    self.force_state_change("reset", selected_datetime)
                    close_window()
                except ValueError:
                    messagebox.showerror("Invalid Input", "Please enter a valid time in HH:MM or HHMM formats.")
            else:
                self.force_state_change("reset")
                close_window()

        def on_cancel():
            close_window()

        ok_button = ttk.Button(button_frame, text="OK", command=on_ok)
        ok_button.grid(row=0, column=0, padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_button.grid(row=0, column=1, padx=5)

        # If the user presses Enter, assume they want to click OK
        reset_window.bind("<Return>", lambda e: on_ok())

        # on window close, save window position
        reset_window.protocol("WM_DELETE_WINDOW", close_window)

        reset_window.after(200, reset_window.deiconify)

if __name__ == "__main__":
    # if the app is already running, bail early
    mutex = win32event.CreateMutex(None, False, "SimTimeRateAdjusterMutex") #type: ignore[arg-type]
    ERROR_ALREADY_EXISTS = 183  # Not defined in pywin32.
    if win32api.GetLastError() == ERROR_ALREADY_EXISTS:
        messagebox.showinfo("Sim Time Rate Adjuster for MSFS 2024", "The application is already running.")
        sys.exit(-1)

    root = tk.Tk()
    app = SimAdjusterUI(main_window=root)
    root.mainloop()
