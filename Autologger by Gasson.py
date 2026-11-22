import tkinter as tk
from tkinter import messagebox
import pyautogui
import pygetwindow as gw
import customtkinter as ctk
from PIL import Image
import subprocess
import threading
import time
import json
import os
import sys
import base64
import ctypes
import logging
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

LOG_FILE = "autologger.log"       # diagnostic log (window positions, steps, errors; no credentials)
MIN_WINDOW_SIZE = 300            # a real Riot Client window is never smaller than this (pixels)
ACCOUNTS_FILE = "accounts.json"  # OLD plain-text file; only read once to migrate it
ENCRYPTED_FILE = "accounts.enc"  # encrypted accounts (usernames, passwords, games)
KDF_PARAMS = {"n": 2 ** 15, "r": 8, "p": 1}  # scrypt cost (makes guessing the master password slow)
MIN_PASSWORD_LENGTH = 8
GAMES_FILE = "games.json"        # JSON file that describes how to launch each game
NO_GAME = "Login only"           # Dropdown value for "just log in, don't launch anything"

# Games available the first time the app runs (games.json is created from this).
# Supported "type" values:
#   riot  -> launches a Riot product through RiotClientServices.exe; add "play_image" (a PNG of the
#            Play button) if the client only selects the game and you need to click Play as well
#   image -> waits for one or more PNGs to appear on screen and clicks them in order
#   exe   -> runs any executable ("target", optional "args")
#   uri   -> opens any URI/path with Windows (e.g. steam://rungameid/730)
# Optional on every type: "delay" = seconds to wait after the login finishes (default 3)
DEFAULT_GAMES = {
    "Valorant": {"type": "riot", "product": "valorant", "patchline": "live"},
    "League of Legends": {"type": "riot", "product": "league_of_legends", "patchline": "live"},
}

try:
    logging.basicConfig(filename=LOG_FILE, filemode="w", level=logging.INFO,
                        format="%(asctime)s %(message)s", encoding="utf-8")
except OSError:
    pass  # folder not writable: just run without a log file

# pyautogui >= 0.9.41 raises an exception when an image is not found instead of returning None
_NeverRaised = type("_NeverRaised", (Exception,), {})
ImageNotFound = getattr(pyautogui, "ImageNotFoundException", _NeverRaised)


def resource_path(relative_path):
    # Get absolute path to resource, works for dev and PyInstaller
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder when frozen
    except Exception:
        base_path = os.path.abspath(".")  # Normal script execution path
    return os.path.join(base_path, relative_path)


def asset_path(relative_path):
    # Images added by the user next to the app win over the ones bundled inside the exe
    local = os.path.abspath(relative_path)
    return local if os.path.exists(local) else resource_path(relative_path)


# Saved accounts; filled by unlock_accounts() once the master password is entered
accounts = {}

# Load the game definitions, creating the file with defaults on first run
if os.path.exists(GAMES_FILE):
    with open(GAMES_FILE, "r", encoding="utf-8") as f:
        games = json.load(f)
else:
    games = dict(DEFAULT_GAMES)
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=4)


_fernet = None  # encryption key, set after the master password is entered
_salt = None    # random salt stored next to the encrypted data


def derive_fernet(master_password, salt, n, r, p):
    # Turn the master password into an encryption key (scrypt is deliberately slow)
    kdf = Scrypt(salt=salt, length=32, n=n, r=r, p=p)
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))
    return Fernet(key)


def save_accounts():
    # Encrypt the whole accounts dictionary and write it to accounts.enc
    record = {
        "version": 1,
        "kdf": "scrypt",
        **KDF_PARAMS,
        "salt": base64.b64encode(_salt).decode("ascii"),
        "data": _fernet.encrypt(json.dumps(accounts).encode("utf-8")).decode("ascii"),
    }
    # Write to a temp file first so a crash can never leave a half-written accounts file
    temp_file = ENCRYPTED_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=4)
    os.replace(temp_file, ENCRYPTED_FILE)


def encrypted_file_matches(expected):
    # Read accounts.enc back and check it decrypts to exactly what we meant to save
    with open(ENCRYPTED_FILE, "r", encoding="utf-8") as f:
        record = json.load(f)
    data = _fernet.decrypt(record["data"].encode("ascii"))
    return json.loads(data.decode("utf-8")) == expected


def ask_new_master_password():
    # Ask twice; returns the password, or None if the user cancels
    while True:
        first = ask_password(
            f"Create a master password (at least {MIN_PASSWORD_LENGTH} characters). "
            "It encrypts your accounts and CANNOT be recovered if you forget it.",
            "Create master password"
        )
        if first is None:
            return None
        if len(first) < MIN_PASSWORD_LENGTH:
            messagebox.showerror("AutoLogger", f"Use at least {MIN_PASSWORD_LENGTH} characters.", parent=window)
            continue
        second = ask_password("Repeat the master password.", "Create master password")
        if second is None:
            return None
        if first != second:
            messagebox.showerror("AutoLogger", "The passwords do not match.", parent=window)
            continue
        return first


def unlock_accounts():
    # Fill `accounts` from accounts.enc (asking for the master password), or create the
    # encrypted file on first run, migrating the old plain-text accounts.json if it exists.
    global _fernet, _salt

    if os.path.exists(ENCRYPTED_FILE):
        with open(ENCRYPTED_FILE, "r", encoding="utf-8") as f:
            record = json.load(f)
        salt = base64.b64decode(record["salt"])
        for _ in range(3):
            password = ask_password("Enter your master password to unlock your accounts.", "Welcome back")
            if password is None:
                break
            try:
                fernet = derive_fernet(password, salt, record["n"], record["r"], record["p"])
                data = fernet.decrypt(record["data"].encode("ascii"))
            except InvalidToken:
                messagebox.showerror("AutoLogger", "Wrong master password.", parent=window)
                continue
            accounts.update(json.loads(data.decode("utf-8")))
            _fernet, _salt = fernet, salt
            return
        window.destroy()
        sys.exit(0)

    # No encrypted file yet: create the master password
    legacy = None
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            legacy = json.load(f)

    password = ask_new_master_password()
    if password is None:
        window.destroy()
        sys.exit(0)

    _salt = os.urandom(16)
    _fernet = derive_fernet(password, _salt, **KDF_PARAMS)
    if legacy:
        accounts.update(legacy)
    save_accounts()

    if legacy is not None and encrypted_file_matches(accounts):
        # The encrypted copy opens correctly, so the plain-text file is no longer needed
        if messagebox.askyesno(
            "AutoLogger",
            "Your accounts are now encrypted in accounts.enc.\n\n"
            "Delete the old plain-text accounts.json now?",
            parent=window
        ):
            os.remove(ACCOUNTS_FILE)


def set_status(message):
    # Update the status label; safe to call from the worker thread
    try:
        window.after(0, lambda: status_var.set(message))
    except Exception:
        pass


def log(message):
    print(message)
    logging.info(message)
    set_status(message)


# --- Typing text with SendInput (Windows) --------------------------------------------------------
# pyautogui.write() only knows ASCII keys and assumes a US layout, so characters such as the euro
# sign are skipped and @ # ~ can come out wrong on other layouts. SendInput with KEYEVENTF_UNICODE
# sends the character itself, whatever the keyboard layout is.
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32), ("mouseData", ctypes.c_uint32),
                ("dwFlags", ctypes.c_uint32), ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_uint16), ("wScan", ctypes.c_uint16), ("dwFlags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_uint32), ("wParamL", ctypes.c_uint16), ("wParamH", ctypes.c_uint16)]


class _INPUTUNION(ctypes.Union):
    # MOUSEINPUT must be in the union: it is the largest member and sets the size SendInput expects
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("u", _INPUTUNION)]


def utf16_units(text):
    # SendInput takes UTF-16 code units (characters outside the BMP become two units)
    data = text.encode("utf-16-le")
    return [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]


def type_text(text, interval=0.01):
    # Type text exactly as given, including @ # ~ and the euro sign, on any keyboard layout
    if sys.platform != "win32":
        pyautogui.write(text, interval=interval)  # fallback, only for testing outside Windows
        return
    for unit in utf16_units(text):
        events = (_INPUT * 2)()
        for event, flags in zip(events, (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)):
            event.type = INPUT_KEYBOARD
            event.u.ki = _KEYBDINPUT(0, unit, flags, 0, 0)
        if ctypes.windll.user32.SendInput(2, events, ctypes.sizeof(_INPUT)) != 2:
            raise ctypes.WinError()
        time.sleep(interval)


def find_image(path, confidence=0.55, region=None):
    # Return the center of the BEST match of the image on screen, or None if no match reaches
    # the confidence. pyautogui alone returns the FIRST match above the threshold, which can be a
    # false positive over busy background art. "region" = (left, top, width, height) limits the search.
    try:
        import cv2
        import numpy as np
    except ImportError:
        cv2 = None

    if cv2 is not None:
        needle = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if needle is None:
            raise FileNotFoundError(path)
        haystack = cv2.cvtColor(np.array(pyautogui.screenshot(region=region)), cv2.COLOR_RGB2BGR)
        if needle.shape[0] > haystack.shape[0] or needle.shape[1] > haystack.shape[1]:
            return None
        scores = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
        _, best_score, _, best_loc = cv2.minMaxLoc(scores)
        find_image.last_score = best_score
        if best_score < confidence:
            return None
        offset_x, offset_y = (region[0], region[1]) if region else (0, 0)
        return (offset_x + best_loc[0] + needle.shape[1] // 2,
                offset_y + best_loc[1] + needle.shape[0] // 2)

    # Fallback if OpenCV is not installed
    try:
        return pyautogui.locateCenterOnScreen(path, confidence=confidence, region=region)
    except ImageNotFound:
        return None


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int32), ("top", ctypes.c_int32),
                ("right", ctypes.c_int32), ("bottom", ctypes.c_int32)]


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("flags", ctypes.c_uint32), ("showCmd", ctypes.c_uint32),
                ("ptMinPosition", _POINT), ("ptMaxPosition", _POINT), ("rcNormalPosition", _RECT)]


def _win32():
    # Private user32/kernel32 handles with explicit argument types (window handles are pointers)
    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    hwnd = ctypes.c_void_p
    user32.GetForegroundWindow.restype = hwnd
    user32.GetWindowThreadProcessId.argtypes = [hwnd, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
    user32.AttachThreadInput.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int]
    for name in ("BringWindowToTop", "SetForegroundWindow", "IsIconic"):
        getattr(user32, name).argtypes = [hwnd]
    user32.ShowWindow.argtypes = [hwnd, ctypes.c_int]
    user32.GetWindowPlacement.argtypes = [hwnd, ctypes.POINTER(_WINDOWPLACEMENT)]
    kernel32.GetCurrentThreadId.restype = ctypes.c_uint32
    return user32, kernel32


def size_when_restored(candidate):
    # Size the window has when it is not minimized; also works while it sits in the taskbar
    try:
        user32, _ = _win32()
        placement = _WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(_WINDOWPLACEMENT)
        if user32.GetWindowPlacement(candidate._hWnd, ctypes.byref(placement)):
            rect = placement.rcNormalPosition
            return rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        pass
    return candidate.width, candidate.height


def get_riot_window():
    # Several visible windows can have "Riot Client" in their title (helpers, overlays...).
    # The real client is the biggest one, so pick that instead of simply the first match.
    candidates = gw.getWindowsWithTitle("Riot Client")
    best, best_area = None, -1
    for candidate in candidates:
        width, height = size_when_restored(candidate)
        logging.info("Window candidate hwnd=%s title=%r minimized=%s restored_size=%sx%s",
                     candidate._hWnd, candidate.title, candidate.isMinimized, width, height)
        if width * height > best_area:
            best, best_area = candidate, width * height
    return best


def window_rect_if_ready(rc_window):
    # (left, top, width, height) if the window is restored, on screen and a sane size; else None
    try:
        if rc_window.isMinimized:
            return None
        left, top, width, height = rc_window.left, rc_window.top, rc_window.width, rc_window.height
    except Exception:
        return None
    screen_w, screen_h = pyautogui.size()
    if width < MIN_WINDOW_SIZE or height < MIN_WINDOW_SIZE:
        return None
    if left >= screen_w or top >= screen_h or left + width <= 0 or top + height <= 0:
        return None
    return left, top, width, height


def wait_for_window_rect(rc_window, timeout=3):
    # Windows needs a moment to finish restoring a window from the taskbar
    end = time.time() + timeout
    while True:
        rect = window_rect_if_ready(rc_window)
        if rect or time.time() >= end:
            if not rect:
                logging.info("Window not ready: minimized=%s rect=%s", rc_window.isMinimized,
                             (rc_window.left, rc_window.top, rc_window.width, rc_window.height))
            return rect
        time.sleep(0.1)


def login_panel_region(rc_window):
    # The login form lives in the left part of the Riot Client window. Searching only there
    # avoids false matches on the artwork and the profile icon (top right).
    if rc_window is None:
        return None
    screen_w, screen_h = pyautogui.size()
    panel_width = min(max(int(rc_window.width * 0.35), 420), rc_window.width)
    left, top = max(rc_window.left, 0), max(rc_window.top, 0)
    right = min(rc_window.left + panel_width, screen_w)
    bottom = min(rc_window.top + rc_window.height, screen_h)
    if right - left < 1 or bottom - top < 1:
        return None
    return (left, top, right - left, bottom - top)


def wait_for_image(path, timeout=60, confidence=0.8):
    # Poll the screen until the image shows up (or the timeout runs out)
    end = time.time() + timeout
    while time.time() < end:
        position = find_image(path, confidence)
        if position:
            return position
        time.sleep(0.5)
    return None


def force_foreground(rc_window, attempts=3):
    # Bring the window to the front and check that it really got there. Windows only lets the
    # foreground process do this, so we briefly attach our input queue to the current foreground
    # window's thread, which is the standard way around that restriction.
    if sys.platform != "win32":
        rc_window.activate()
        return True

    user32, kernel32 = _win32()
    hwnd = rc_window._hWnd

    for _ in range(attempts):
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE: bring it back from the taskbar
        foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        this_thread = kernel32.GetCurrentThreadId()
        attached = bool(
            foreground_thread and foreground_thread != this_thread
            and user32.AttachThreadInput(this_thread, foreground_thread, True)
        )
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(this_thread, foreground_thread, False)
        time.sleep(0.15)
        if ((user32.GetForegroundWindow() or 0) & 0xFFFFFFFF) == (hwnd & 0xFFFFFFFF):
            return True
    return False


def prepare_riot_window():
    # Find the Riot Client window (also when it is minimized in the taskbar), bring it to the front
    # and wait until it has a usable position. Returns the window, or None (with a message).
    rc_window = get_riot_window()
    if rc_window is None:
        log("Riot Client window not found. Open the Riot Client first.")
        return None
    logging.info("Using window hwnd=%s", rc_window._hWnd)
    try:
        rc_window.minimize()    # Minimize to force window refresh
        time.sleep(0.1)
        rc_window.restore()     # Restore it back
    except Exception:
        logging.exception("minimize/restore failed")
    if not force_foreground(rc_window):
        # Never type credentials if we are not sure the Riot Client is the window in front
        log("Windows would not bring the Riot Client to the front. Click it in the taskbar and try again.")
        return None
    rect = wait_for_window_rect(rc_window)
    if rect is None:
        log("The Riot Client window has no usable position on screen (see autologger.log).")
        return None
    logging.info("Window ready at %s", rect)
    return rc_window


def inject_credentials(username, password, rc_window=None):
    # Automate Riot Client login by injecting username and password using pyautogui
    # Returns True when the login button was clicked, False otherwise
    try:
        log("Starting login...")

        # Normally start_login has already brought the window to the front
        if rc_window is None:
            rc_window = prepare_riot_window()
            if rc_window is None:
                return False

        time.sleep(0.1)

        # Get window position to calculate relative click positions (and make sure it is valid)
        rect = wait_for_window_rect(rc_window, timeout=1)
        if rect is None:
            log("The Riot Client window has no usable position on screen (see autologger.log).")
            return False
        riot_x, riot_y = rect[0], rect[1]
        region = login_panel_region(rc_window)
        logging.info("Window rect=%s search region=%s", rect, region)

        # Click inside the window to ensure focus
        if not pyautogui.onScreen(riot_x + 50, riot_y + 50):
            log("The Riot Client window is not on the screen (see autologger.log).")
            return False
        pyautogui.click(riot_x + 50, riot_y + 50)
        time.sleep(0.1)

        # Locate username input field on screen via image matching
        username_field = find_image(asset_path("assets/username_field.png"), region=region)
        logging.info("username_field: %s score=%s", username_field, getattr(find_image, "last_score", None))
        if username_field:
            pyautogui.click(username_field)
            time.sleep(0.3)
            type_text(username)  # Type username slowly
        else:
            log("Username field not found.")
            return False

        # Locate password input field on screen
        password_field = find_image(asset_path("assets/password_field.png"), region=region)
        logging.info("password_field: %s score=%s", password_field, getattr(find_image, "last_score", None))
        if password_field:
            pyautogui.click(password_field)
            time.sleep(0.3)
            type_text(password)  # Type password slowly
        else:
            log("Password field not found.")
            return False

        # Locate and click the login button
        login_button = find_image(asset_path("assets/login_button.png"), region=region)
        logging.info("login_button: %s score=%s", login_button, getattr(find_image, "last_score", None))
        if login_button:
            time.sleep(0.3)
            pyautogui.click(login_button)
            print("Login sequence complete.")
            return True
        else:
            # The password field still has focus, so Enter submits the form
            log("Login button not found, pressing Enter instead.")
            pyautogui.press("enter")
            return True

    except Exception:
        import traceback
        print("Error during injection:")
        traceback.print_exc()
        logging.exception("Error during login")
        set_status("Error during login (see autologger.log).")
        return False


def wait_login_finished(timeout=30):
    # The login button disappears from the screen once the Riot Client moves past the login form
    time.sleep(1.5)
    end = time.time() + timeout
    while time.time() < end:
        region = login_panel_region(get_riot_window())
        if find_image(asset_path("assets/login_button.png"), region=region) is None:
            return True
        time.sleep(0.5)
    return False


def riot_client_path():
    # Riot writes the path of the installed client here; fall back to the default folder
    installs = os.path.join(
        os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Riot Games", "RiotClientInstalls.json"
    )
    try:
        with open(installs, "r") as f:
            data = json.load(f)
        for key in ("rc_live", "rc_default"):
            path = data.get(key)
            if path and os.path.exists(path):
                return path
    except (OSError, ValueError):
        pass
    fallback = r"C:\Riot Games\Riot Client\RiotClientServices.exe"
    return fallback if os.path.exists(fallback) else None


def launch_game(name, game):
    # Start the game described in games.json
    kind = game.get("type")
    try:
        if kind == "riot":
            client = riot_client_path()
            if not client:
                log("RiotClientServices.exe not found.")
                return
            subprocess.Popen([
                client,
                f"--launch-product={game['product']}",
                f"--launch-patchline={game.get('patchline', 'live')}",
            ])

            # Optional: sometimes the client only selects the game and waits for a click on Play.
            # If "play_image" is set, wait for that button on screen and click it.
            play_image = game.get("play_image")
            if play_image:
                time.sleep(game.get("play_delay", 2))
                position = wait_for_image(
                    asset_path(play_image), game.get("timeout", 30), game.get("confidence", 0.8)
                )
                if not position:
                    log(f"Could not find {play_image} on screen.")
                    return
                pyautogui.click(position)

        elif kind == "image":
            # One image, or a list of images that are clicked in order (e.g. game tab, then Play)
            steps = game.get("images") or [game["image"]]
            for step in steps:
                position = wait_for_image(
                    asset_path(step), game.get("timeout", 60), game.get("confidence", 0.8)
                )
                if not position:
                    log(f"Could not find {step} on screen.")
                    return
                pyautogui.click(position)
                time.sleep(0.5)

        elif kind == "exe":
            subprocess.Popen([game["target"]] + game.get("args", []))

        elif kind == "uri":
            os.startfile(game["target"])  # Windows only

        else:
            log(f"Unknown game type '{kind}' for {name}.")
            return

        log(f"Launched {name}.")

    except Exception as e:
        log(f"Could not launch {name}: {e}")


def run_login_flow(creds, rc_window=None):
    # Full flow: log in, wait for the client to finish, then launch the assigned game
    if not inject_credentials(creds["username"], creds["password"], rc_window):
        return

    game_name = creds.get("game", "")
    if not game_name:
        log("Logged in.")
        return

    game = games.get(game_name)
    if not game:
        log(f"Game '{game_name}' is not defined in {GAMES_FILE}.")
        return

    set_status("Waiting for the login to finish...")
    if not wait_login_finished():
        log("Login did not seem to finish, the game was not launched.")
        return

    time.sleep(game.get("delay", 3))
    launch_game(game_name, game)


login_busy = threading.Event()  # set while a login is running


def login_worker(creds, rc_window):
    try:
        run_login_flow(creds, rc_window)
    finally:
        login_busy.clear()


def start_login(creds):
    if login_busy.is_set():
        set_status("A login is already running, please wait.")
        return
    # Bring the Riot Client to the front HERE, in the thread that just received the user's click:
    # Windows only lets the process that just got input change the foreground window.
    rc_window = prepare_riot_window()
    if rc_window is None:
        return
    # The rest runs in a thread so the window does not freeze while we wait for the client
    login_busy.set()
    threading.Thread(target=login_worker, args=(creds, rc_window), daemon=True).start()


# ======================================================================================
#  User interface (customtkinter)
# ======================================================================================
# Colors
BG = "#0E0A18"            # window background
PANEL = "#181226"         # cards
PANEL_ALT = "#1F1733"     # hover on cards / secondary buttons
INPUT_BG = "#110C1E"      # text boxes
BORDER = "#2C2245"
ACCENT = "#8B5CF6"        # main purple
ACCENT_HOVER = "#7440E8"
ACCENT_SOFT = "#2A1F4A"   # avatar circle
ACCENT_TEXT = "#B79CFF"   # light purple for small labels
DANGER = "#F87171"
DANGER_BORDER = "#5B2530"
DANGER_HOVER = "#2A1218"
TEXT = "#F4F1FF"
MUTED = "#9A90B5"
GOOD = "#34D399"
UI_FONT = "Segoe UI"


def font(size, bold=False):
    return ctk.CTkFont(family=UI_FONT, size=size, weight="bold" if bold else "normal")


def load_logo(height):
    # Header logo: assets/logo.png if it exists, otherwise the window icon image
    for relative in ("assets/logo.png", "assets/youricon.png"):
        path = asset_path(relative)
        if os.path.exists(path):
            try:
                image = Image.open(path)
                width = max(round(height * image.width / image.height), 1)
                return ctk.CTkImage(light_image=image, dark_image=image, size=(width, height))
            except Exception:
                logging.exception("Could not load %s", relative)
    return None


ctk.set_appearance_mode("dark")
window = ctk.CTk(fg_color=BG)
window.title("AutoLogger by Gasson")
window.minsize(780, 620)

# Center the window on the user's screen
WIN_W, WIN_H = 900, 700
try:
    scale = window._get_window_scaling()
except Exception:
    scale = 1.0
x = max((window.winfo_screenwidth() - int(WIN_W * scale)) // 2, 0)
y = max((window.winfo_screenheight() - int(WIN_H * scale)) // 2, 0)
window.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")


def set_window_icon():
    # customtkinter sets its own icon shortly after start-up, so ours is applied after that
    try:
        window._icon_image = tk.PhotoImage(file=asset_path("assets/youricon.png"))
        window.iconphoto(True, window._icon_image)
    except Exception:
        logging.exception("Could not set the window icon")


window.after(300, set_window_icon)

status_var = tk.StringVar(value="Ready")

# ---- Header -------------------------------------------------------------------------------
header = ctk.CTkFrame(window, fg_color="transparent")
header.pack(fill="x", padx=28, pady=(24, 6))
header.grid_columnconfigure(1, weight=1)

logo_image = load_logo(46)
if logo_image is not None:
    ctk.CTkLabel(header, image=logo_image, text="").grid(row=0, column=0, rowspan=2, padx=(0, 14))

ctk.CTkLabel(header, text="AutoLogger", font=font(26, True), text_color=TEXT, anchor="w").grid(
    row=0, column=1, sticky="sw")
ctk.CTkLabel(header, text="Log in to your Riot accounts and start your game in one click",
             font=font(12), text_color=MUTED, anchor="w").grid(row=1, column=1, sticky="nw")
ctk.CTkLabel(header, text="  Encrypted  ", font=font(11, True), text_color=GOOD, fg_color=PANEL,
             corner_radius=12, height=26).grid(row=0, column=2, rowspan=2, sticky="e")

# ---- Accounts list --------------------------------------------------------------------------
list_header = ctk.CTkFrame(window, fg_color="transparent")
list_header.pack(fill="x", padx=30, pady=(16, 4))
ctk.CTkLabel(list_header, text="Your accounts", font=font(15, True), text_color=TEXT).pack(side="left")
count_label = ctk.CTkLabel(list_header, text="", font=font(12), text_color=MUTED)
count_label.pack(side="right")

list_frame = ctk.CTkScrollableFrame(window, fg_color="transparent", scrollbar_button_color=BORDER,
                                    scrollbar_button_hover_color=ACCENT)
list_frame.pack(fill="both", expand=True, padx=(22, 18), pady=(0, 6))

empty_label = ctk.CTkLabel(list_frame, text="No accounts yet.\nAdd your first one below.",
                           font=font(13), text_color=MUTED, justify="center")

account_frames = {}  # name -> card, so cards can be rebuilt


def add_account_card(name, creds):
    # One card per account: avatar, name, game, and the Log in / Edit / Delete buttons
    card = ctk.CTkFrame(list_frame, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
    card.pack(fill="x", padx=6, pady=5)
    card.grid_columnconfigure(1, weight=1)

    avatar = ctk.CTkFrame(card, width=46, height=46, corner_radius=23, fg_color=ACCENT_SOFT)
    avatar.grid(row=0, column=0, rowspan=2, padx=(14, 14), pady=14)
    ctk.CTkLabel(avatar, text=name[:1].upper(), fg_color="transparent", text_color=ACCENT_TEXT,
                 font=font(19, True)).place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(card, text=name, font=font(15, True), text_color=TEXT, anchor="w").grid(
        row=0, column=1, sticky="sw", pady=(14, 0))

    game = creds.get("game", "")
    ctk.CTkLabel(card, text=f"\u25B6  {game}" if game else "Login only", font=font(12),
                 text_color=ACCENT_TEXT if game else MUTED, anchor="w").grid(
        row=1, column=1, sticky="nw", pady=(0, 14))

    actions = ctk.CTkFrame(card, fg_color="transparent")
    actions.grid(row=0, column=2, rowspan=2, padx=(8, 14))

    ctk.CTkButton(actions, text="Log in & play" if game else "Log in", width=124, height=36, corner_radius=10,
                  fg_color=ACCENT, hover_color=ACCENT_HOVER, font=font(13, True),
                  command=lambda c=creds: start_login(c)).pack(side="left", padx=(0, 8))
    ctk.CTkButton(actions, text="Edit", width=62, height=36, corner_radius=10, fg_color="transparent",
                  border_width=1, border_color=BORDER, hover_color=PANEL_ALT, text_color=TEXT,
                  font=font(13), command=lambda n=name: start_edit_account(n)).pack(side="left", padx=(0, 8))
    ctk.CTkButton(actions, text="Delete", width=70, height=36, corner_radius=10, fg_color="transparent",
                  border_width=1, border_color=DANGER_BORDER, hover_color=DANGER_HOVER, text_color=DANGER,
                  font=font(13), command=lambda n=name: delete_account(n)).pack(side="left")

    account_frames[name] = card


def rebuild_cards():
    for card in account_frames.values():
        card.destroy()
    account_frames.clear()
    empty_label.pack_forget()
    for name, creds in accounts.items():
        add_account_card(name, creds)
    if not accounts:
        empty_label.pack(pady=40)
    count_label.configure(text=f"{len(accounts)} account" + ("" if len(accounts) == 1 else "s"))


# ---- Add / edit form --------------------------------------------------------------------------
editing = {"name": None}  # name of the account being edited, or None when adding a new one

form = ctk.CTkFrame(window, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
form.pack(fill="x", padx=28, pady=(6, 4))
for column in range(4):
    form.grid_columnconfigure(column, weight=1, uniform="fields")

form_title = ctk.CTkLabel(form, text="Add account", font=font(15, True), text_color=TEXT, anchor="w")
form_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(16, 8))


def field_label(column, text):
    ctk.CTkLabel(form, text=text, font=font(11, True), text_color=MUTED, anchor="w").grid(
        row=1, column=column, sticky="w", padx=(18 if column == 0 else 6, 6), pady=(0, 4))


def make_entry(column, placeholder, show=None):
    entry = ctk.CTkEntry(form, placeholder_text=placeholder, height=40, corner_radius=10, border_width=1,
                         fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT,
                         placeholder_text_color=MUTED, font=font(13), show=show)
    entry.grid(row=2, column=column, sticky="ew", padx=(18 if column == 0 else 6, 6), pady=(0, 6))
    return entry


field_label(0, "ACCOUNT NAME")
field_label(1, "USERNAME")
field_label(2, "PASSWORD")
field_label(3, "GAME")

label_entry = make_entry(0, "e.g. Main account")
username_entry = make_entry(1, "Riot username")
password_entry = make_entry(2, "Password", show="\u2022")

# Small "Show" toggle on the right of the PASSWORD label (handy to check @ # ~ \u20AC are right)
password_visible = {"on": False}


def toggle_password():
    password_visible["on"] = not password_visible["on"]
    password_entry.configure(show="" if password_visible["on"] else "\u2022")
    show_button.configure(text="Hide" if password_visible["on"] else "Show")


show_button = ctk.CTkButton(form, text="Show", width=44, height=18, corner_radius=6, fg_color="transparent",
                            hover_color=PANEL_ALT, text_color=ACCENT_TEXT, font=font(11, True),
                            command=toggle_password)
show_button.grid(row=1, column=2, sticky="e", padx=(6, 6), pady=(0, 4))

game_var = tk.StringVar(value=NO_GAME)
game_menu = ctk.CTkOptionMenu(form, variable=game_var, values=[NO_GAME] + list(games.keys()), height=40,
                              corner_radius=10, fg_color=INPUT_BG, button_color=BORDER,
                              button_hover_color=ACCENT, dropdown_fg_color=PANEL,
                              dropdown_hover_color=ACCENT_SOFT, dropdown_text_color=TEXT, text_color=TEXT,
                              font=font(13), dropdown_font=font(13), anchor="w")
game_menu.grid(row=2, column=3, sticky="ew", padx=(6, 18), pady=(0, 6))

form_buttons = ctk.CTkFrame(form, fg_color="transparent")
form_buttons.grid(row=3, column=0, columnspan=4, sticky="e", padx=18, pady=(8, 16))

cancel_button = ctk.CTkButton(form_buttons, text="Cancel", width=90, height=38, corner_radius=10,
                              fg_color="transparent", border_width=1, border_color=BORDER,
                              hover_color=PANEL_ALT, text_color=TEXT, font=font(13),
                              command=lambda: reset_form())
submit_button = ctk.CTkButton(form_buttons, text="Add account", width=140, height=38, corner_radius=10,
                              fg_color=ACCENT, hover_color=ACCENT_HOVER, font=font(13, True),
                              command=lambda: submit_form())
submit_button.pack(side="right")


def clear_entry(entry):
    entry.delete(0, "end")
    # A text box only shows its hint text again once it loses focus, so make sure it does
    try:
        if not entry._placeholder_text_active:
            entry._activate_placeholder()
    except AttributeError:
        pass  # other customtkinter version: the hint text just comes back on the next click


def reset_form():
    # Back to "add account" mode with an empty form
    editing["name"] = None
    for entry in (label_entry, username_entry, password_entry):
        clear_entry(entry)
    game_var.set(NO_GAME)
    window.focus_set()
    form_title.configure(text="Add account")
    submit_button.configure(text="Add account")
    cancel_button.pack_forget()


def start_edit_account(name):
    # Fill the form with the account; nothing is removed until "Save changes" is pressed
    creds = accounts[name]
    reset_form()
    editing["name"] = name
    label_entry.insert(0, name)
    username_entry.insert(0, creds["username"])
    password_entry.insert(0, creds["password"])
    game_var.set(creds.get("game") or NO_GAME)
    form_title.configure(text=f"Edit account \u00B7 {name}")
    submit_button.configure(text="Save changes")
    cancel_button.pack(side="right", padx=(0, 10), after=submit_button)


def form_values():
    return label_entry.get().strip(), username_entry.get().strip(), password_entry.get().strip()


def submit_form():
    # Add a new account, or save the one being edited
    name, username, password = form_values()
    selected_game = game_var.get()
    game = "" if selected_game == NO_GAME else selected_game

    if not name or not username or not password:
        set_status("Please fill in the account name, username and password.")
        return

    old_name = editing["name"]
    if name != old_name and name in accounts:
        set_status("An account with that name already exists.")
        return

    entry = {"username": username, "password": password, "game": game}
    if old_name is None:
        accounts[name] = entry
    else:
        # Replace the account keeping its position in the list
        items = [(name, entry) if key == old_name else (key, value) for key, value in accounts.items()]
        accounts.clear()
        accounts.update(items)

    save_accounts()
    reset_form()
    rebuild_cards()
    set_status(f"Account '{name}' saved.")


def delete_account(name):
    if not messagebox.askyesno("Delete account", f"Delete '{name}'? This cannot be undone.", parent=window):
        return
    if name in accounts:
        del accounts[name]
        save_accounts()
    if editing["name"] == name:
        reset_form()
    rebuild_cards()
    set_status(f"Account '{name}' deleted.")


# ---- Status line ------------------------------------------------------------------------------
ctk.CTkLabel(window, textvariable=status_var, font=font(12), text_color=MUTED, anchor="w").pack(
    fill="x", padx=32, pady=(4, 16))


# ---- Master password dialog ---------------------------------------------------------------------
def ask_password(prompt, title="AutoLogger"):
    # Modal dialog with a masked box. Returns the text, or None if the user cancels.
    result = {"value": None}
    dialog = ctk.CTkToplevel(window, fg_color=PANEL)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.transient(window)

    ctk.CTkLabel(dialog, text=title, font=font(17, True), text_color=TEXT, anchor="w").pack(
        fill="x", padx=24, pady=(22, 4))
    ctk.CTkLabel(dialog, text=prompt, font=font(12), text_color=MUTED, wraplength=380, justify="left",
                 anchor="w").pack(fill="x", padx=24, pady=(0, 14))
    entry = ctk.CTkEntry(dialog, show="\u2022", width=380, height=42, corner_radius=10, border_width=1,
                         fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT, font=font(14))
    entry.pack(padx=24)

    def submit(_event=None):
        result["value"] = entry.get()
        dialog.destroy()

    def cancel(_event=None):
        dialog.destroy()

    buttons = ctk.CTkFrame(dialog, fg_color="transparent")
    buttons.pack(fill="x", padx=24, pady=(18, 22))
    ctk.CTkButton(buttons, text="Unlock" if "unlock" in prompt.lower() else "OK", width=110, height=38,
                  corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER, font=font(13, True),
                  command=submit).pack(side="right")
    ctk.CTkButton(buttons, text="Cancel", width=90, height=38, corner_radius=10, fg_color="transparent",
                  border_width=1, border_color=BORDER, hover_color=PANEL_ALT, text_color=TEXT,
                  font=font(13), command=cancel).pack(side="right", padx=(0, 10))

    entry.bind("<Return>", submit)
    dialog.bind("<Escape>", cancel)
    dialog.protocol("WM_DELETE_WINDOW", cancel)

    # Center over the main window
    dialog.update_idletasks()
    dialog_w, dialog_h = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
    pos_x = window.winfo_x() + (window.winfo_width() - dialog_w) // 2
    pos_y = window.winfo_y() + (window.winfo_height() - dialog_h) // 2
    dialog.geometry(f"+{max(pos_x, 0)}+{max(pos_y, 0)}")

    try:
        dialog.wait_visibility()
        dialog.grab_set()
    except tk.TclError:
        pass
    dialog.after(150, lambda: (dialog.lift(), entry.focus_force()))
    window.wait_window(dialog)
    return result["value"]


# ---- Start-up ---------------------------------------------------------------------------------
unlock_accounts()          # ask for the master password and load the accounts
rebuild_cards()

if os.path.exists(ACCOUNTS_FILE):
    status_var.set("Warning: the old plain-text accounts.json still exists. Delete it when you are done.")

# Start Tkinter event loop
window.mainloop()
