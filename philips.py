import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
import pystray
import threading
import requests
import keyboard
import time
import json
import sys
import os

def setup_tray_icon(root):
    def show_app(icon, item):
        root.after(0, root.deiconify)

    def quit_app(icon, item):
        icon.stop()
        root.destroy()
        sys.exit()
    
    def create_image():
        image = Image.new('RGB', (64, 64), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill=(0, 0, 0))
        return image

    try:
        tray_icon_image = Image.open("icon.png")  # use PNG for pystray
    except Exception as e:
        print(f"Failed to load tray icon image: {e}")
        tray_icon_image = create_image()  # fallback to basic black circle

    icon = pystray.Icon("Hue Controller", tray_icon_image, menu=pystray.Menu(
        pystray.MenuItem("Restore", show_app),
        pystray.MenuItem("Toggle Light", toggle_light),
        pystray.MenuItem("Exit", quit_app)
    ))

    threading.Thread(target=icon.run, daemon=True).start()
    return icon

# ------------------------
# SETTINGS FILE HANDLING
SETTINGS_FILE = "hue_settings.json"
def default_settings():
    return {
        "bridge_ip": "",
        "username": "",
        "light_id": "1",
        "hotkeys": {
            "toggle": None,
            "increase": None,
            "decrease": None
        }
    }

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return default_settings()

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

# ------------------------
# GLOBAL STATE
settings = load_settings()
current_brightness = 128

# ------------------------
# PHILIPS HUE FUNCTIONS
def set_brightness(level):
    level = max(0, min(254, level))
    url = f"http://{settings['bridge_ip']}/api/{settings['username']}/lights/{settings['light_id']}/state"
    try:
        requests.put(url, json={"bri": level})
        print(f"Brightness set to {level}")
    except:
        print("Failed to send brightness request.")
    return level

def toggle_light():
    try:
        url = f"http://{settings['bridge_ip']}/api/{settings['username']}/lights/{settings['light_id']}"
        r = requests.get(url)
        current_state = r.json()['state']['on']
        new_state = not current_state
        requests.put(f"{url}/state", json={"on": new_state})
        print(f"Light turned {'on' if new_state else 'off'}")
    except:
        messagebox.showerror("Error", "Failed to connect to Hue Bridge.")

# ------------------------
# BACKGROUND THREADS
def adjust_brightness_loop():
    global current_brightness
    delay = 0.2
    acceleration = 0.95
    while True:
        if settings['hotkeys']['increase'] and keyboard.is_pressed(settings['hotkeys']['increase']):
            direction = 1
        elif settings['hotkeys']['decrease'] and keyboard.is_pressed(settings['hotkeys']['decrease']):
            direction = -1
        else:
            time.sleep(0.05)
            continue
        current_brightness += direction * 5
        current_brightness = set_brightness(current_brightness)
        time.sleep(delay)
        delay = max(0.01, delay * acceleration)

def toggle_listener():
    last_state = False
    while True:
        hk = settings['hotkeys']['toggle']
        if hk and keyboard.is_pressed(hk):
            if not last_state:
                toggle_light()
            last_state = True
        else:
            last_state = False
        time.sleep(0.1)

# ------------------------
# GUI

def start_gui():
    root = tk.Tk()
    root.title("Hue Light Controller")
    root.geometry("400x300")

    notebook = ttk.Notebook(root)
    control_tab = ttk.Frame(notebook)
    setup_tab = ttk.Frame(notebook)
    hotkeys_tab = ttk.Frame(notebook)

    notebook.add(control_tab, text="Control")
    notebook.add(setup_tab, text="Setup")
    notebook.add(hotkeys_tab, text="Hotkeys")
    notebook.pack(expand=1, fill="both")

    # --- Minimize ---
    
    # Set icon
    try:
        root.iconbitmap("default_icon.ico")  # must be .ico for Windows
    except:
        pass

    icon = setup_tray_icon(root)
    
    def on_close():
        root.withdraw()
    
    root.protocol("WM_DELETE_WINDOW", on_close)

    # --- Control Tab ---
    tk.Label(control_tab, text=f"Hold {settings['hotkeys']['increase']} to increase brightness, and {settings['hotkeys']['increase']} to decrease.", pady=10).pack()
    tk.Button(control_tab, text="Toggle Light", command=toggle_light, height=2, width=20).pack(pady=5)
    tk.Button(control_tab, text="Help >>", command=lambda: messagebox.showinfo("Help",
        "Set up your Bridge IP, username, and hotkeys in the other tabs.")).pack(pady=5)

    # --- Setup Tab ---
    ip_var = tk.StringVar(value=settings['bridge_ip'])
    username_var = tk.StringVar(value=settings['username'])

    tk.Label(setup_tab, text="Bridge IP:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
    ip_entry = tk.Entry(setup_tab, textvariable=ip_var, width=30)
    ip_entry.grid(row=0, column=1)

    tk.Label(setup_tab, text="Username:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
    tk.Entry(setup_tab, textvariable=username_var, width=30).grid(row=1, column=1)

    def generate_username():
        bridge_ip = ip_var.get().strip()
        if not bridge_ip:
            messagebox.showwarning("Missing IP", "Please enter the Bridge IP first.")
            return
        try:
            response = requests.post(f"http://{bridge_ip}/api", json={"devicetype": "hue_app_setup"})
            data = response.json()
            if "success" in data[0]:
                username_var.set(data[0]['success']['username'])
                messagebox.showinfo("Success", f"Username created:\n{username_var.get()}")
            else:
                messagebox.showerror("Failed", f"Error: {data[0]['error']['description']}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to bridge.\n{e}")

    def apply_settings():
        settings['bridge_ip'] = ip_var.get().strip()
        settings['username'] = username_var.get().strip()
        save_settings(settings)
        messagebox.showinfo("Saved", "Settings applied.")
    
    import requests

    def get_hue_internal_ip():
        url = "https://discovery.meethue.com"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for bad status codes

            data = response.json()
            if data and 'internalipaddress' in data[0]:
                print(data)
                return data[0]['internalipaddress']
            else:
                print("No Hue Bridge found.")
                return None
        except requests.RequestException as e:
            print("Error connecting to Hue Discovery service:", e)
            messagebox.showwarning("Error", f"{e}\n Try again later.")
            return None

    ip_address = settings['bridge_ip'] if 'bridge_ip' in settings else get_hue_internal_ip()
    if not ip_address or ip_address == "":
        ip_entry.insert(0, ip_address)

    tk.Button(setup_tab, text="Generate Username", command=generate_username).grid(row=2, column=1, pady=5, sticky="e")
    tk.Button(setup_tab, text="Apply Settings", command=apply_settings).grid(row=3, column=1, pady=5, sticky="e")
    tk.Button(setup_tab, text="Get Bridge IP", command=get_hue_internal_ip).grid(row=4, column=1, pady=5, sticky="e")

    # --- Hotkeys Tab ---
    def listen_for_hotkey(var, label):
        def inner():
            label.config(text="Waiting...")

            pressed_keys = set()
            result = []

            def on_event(e):
                nonlocal result

                if e.event_type == "down":
                    pressed_keys.add(e.name)
                elif e.event_type == "up":
                    if e.name not in {"shift", "ctrl", "alt"}:
                        # Final key released — commit combo
                        result = sorted(
                            k for k in pressed_keys if k is not None
                        )
                        keyboard.unhook_all()
            
            keyboard.hook(on_event)

            # Wait until result is populated
            while not result:
                time.sleep(0.05)

            # Ensure modifiers come first
            ordered = []
            for mod in ["ctrl", "shift", "alt"]:
                if mod in result:
                    ordered.append(mod)
            for key in result:
                if key not in ordered:
                    ordered.append(key)

            combo = "+".join(ordered)
            var.set(combo)
            label.config(text=f"Key: {combo}")
        threading.Thread(target=inner, daemon=True).start()

    toggle_key_var = tk.StringVar(value=settings['hotkeys']['toggle'] or "")
    inc_key_var = tk.StringVar(value=settings['hotkeys']['increase'] or "")
    dec_key_var = tk.StringVar(value=settings['hotkeys']['decrease'] or "")

    def create_hotkey_row(row, label_text, var, label_widget):
        tk.Label(hotkeys_tab, text=label_text).grid(row=row, column=0, padx=10, pady=5, sticky="e")
        label_widget.grid(row=row, column=1)
        tk.Button(hotkeys_tab, text="Set", command=lambda: listen_for_hotkey(var, label_widget)).grid(row=row, column=2)

    lbl_toggle = tk.Label(hotkeys_tab, text=f"Key: {toggle_key_var.get() or 'None'}")
    lbl_inc = tk.Label(hotkeys_tab, text=f"Key: {inc_key_var.get() or 'None'}")
    lbl_dec = tk.Label(hotkeys_tab, text=f"Key: {dec_key_var.get() or 'None'}")

    create_hotkey_row(0, "Toggle Light:", toggle_key_var, lbl_toggle)
    create_hotkey_row(1, "Increase Brightness:", inc_key_var, lbl_inc)
    create_hotkey_row(2, "Decrease Brightness:", dec_key_var, lbl_dec)

    def save_hotkeys():
        settings['hotkeys']['toggle'] = toggle_key_var.get()
        settings['hotkeys']['increase'] = inc_key_var.get()
        settings['hotkeys']['decrease'] = dec_key_var.get()
        save_settings(settings)
        messagebox.showinfo("Saved", "Hotkeys updated.")

    tk.Button(hotkeys_tab, text="Save Hotkeys", command=save_hotkeys).grid(row=3, column=2, pady=10, sticky="e")

    root.mainloop()

# Start threads
threading.Thread(target=adjust_brightness_loop, daemon=True).start()
threading.Thread(target=toggle_listener, daemon=True).start()

# Start GUI
start_gui()
