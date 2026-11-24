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
import io
import logging
import tempfile
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

APP_VERSION = "2026-11-24.2"
LOG_FILE = "autologger.log"       # diagnostic log (window positions, steps, errors; no credentials)
REPORT_FILE = "autologger_report.txt"  # written by Settings > Diagnostics (no credentials)
SETTINGS_FILE = "settings.json"   # app settings (language, options). Contains no secrets
ACCOUNTS_FILE = "accounts.json"   # OLD plain-text file; only read once to migrate it
ENCRYPTED_FILE = "accounts.enc"   # protected accounts (usernames, passwords, games)
GAMES_FILE = "games.json"         # JSON file that describes how to launch each game
KDF_PARAMS = {"n": 2 ** 15, "r": 8, "p": 1}  # scrypt cost (makes guessing the master password slow)
MIN_PASSWORD_LENGTH = 8
MIN_WINDOW_SIZE = 300             # a real Riot Client window is never smaller than this (pixels)
RIOT_WINDOW_TITLE = "Riot Client"
RIOT_UI_PROCESSES = ("riotclientux.exe",)  # the Riot Client window belongs to this program, in any language
DPAPI_ENTROPY = b"AutoLogger by Gasson"

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
    "League of Legends": {"type": "riot", "product": "league_of_legends", "patchline": "live",
                          "play_image": "assets/play_lol.png"},
}

# Play button that is clicked for each Riot product when a game in games.json has no "play_image" of its
# own (so deleting games.json, or an old games.json, still starts the game). Write "play_image": "" in a
# game to turn this off for it.
DEFAULT_PLAY_IMAGES = {"league_of_legends": "assets/play_lol.png"}

# Copies of the Play button (English and Spanish clients) inside the program, used only when the file is
# not found in assets/ or assets/templates/<language>/. Files you put in those folders always win.
BUILTIN_IMAGES = {
    "assets/play_lol.png": (
    "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"
    ),
    "assets/templates/es/play_lol.png": (
    "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"
    "N9J6yweV5adkIT8xLiorjWsn7D8tyYfw3KnTF9/cfryru0doUltH93PrD2am+LUjQSdPSoJvZEYQbjl+vblE2APsX9tZ/NmH"
    "JTVuF4kFoH+NGB3W2dXb06v1r31a0fhhyWd0Ub3/3EphreKOHe8SRae8IxaI4weKd+SLHI6+Wbq+kbu2/vO+x+TRwX+6f3x2"
    "ekBGT6pNFPz3QPPvYMCbf2v6K28fERv44+6qkmNNq+4YFRvj2bqneu8hpab5t2YMHRKN/akGYyMz4rJSA6fOyCrWf71dum3P"
    "qSk5ya3tXbuKawIxkV9bkrOzmOCm8P1YtDdi+fxRxYDGlFY0rf63wm/97eTpE9I7urrffK9847aylQvG7jhQrZB2oGR6sj82"
    "JvJCSwdj7P2PT77y1sFVC8cHY6Nb2jr/su/UM+v25E/P3ry9DOlp+X7MouZapHYl/NzivwkzFRc09A37w6WnJF8o2qNiHKlD"
    "vN+5J2felGQS7SvZHJj/xthY7GFlfvaf99dW1koDXttw+dk3Siy0GZUR+7UlYx1O026hPUyI8y67feRz/6Pg7pqGlpoGaVfz"
    "p2dmpJgyKgbmSyL+yLslc8aE1I8OnxF365pbn3z5Q3x4SDD6jlnZOw5Uk23Ijr/M1Ni8qcMwfHt5U9HLm4rwsRkT028Zl0pZ"
    "TnqENGsKuAX2r8nuF+KbCc4o37XG53Yc0wn14yt/P+bzKthBjMgI57dWjP7ftXPnTUm+Tvi5yL/jA94XHps7d7JKZy1j2rik"
    "X37vtuQEnxAxaeR4fH7vwjEr5o+0m6ic4fEFS8ZTwAt7pYX1jon2/OSRvBkTh9rfdTjY49+YkZGsQjxi2xwRbtd3C2bOzE23"
    "vxjnj3rk/uk+r4owEMOR3c0ka7P579D173D5Nz+EzEFEFCICFXe/v/9meZOT3t2jsotFM4c+tHLMkKB3QN9/X3X+nRD0PrNm"
    "9qeVZ3/3fuXBow31Z9t6eozkeO/UcclfWTByfHa80G9EPbE2FeF2Pf71qQtmZP5686FDx5sMg8UHopbelv3A8gk+r+do1Tmr"
    "lpMe2Ti/9/nHv7Tnk9pXtxwqPdHIWyTcU8enPnr/tBHpwUaI0cSgFYQ4f+SL31+8u7jq1S2flJ9sauvojo/1Lpk7avWySYnx"
    "MTvMuE8NouUaxoBdwpidh9LvsPl3iC/OTR1gjuLX70TNEOZN+6JADlNgzrd0PrehfM/hxilj4gsWjRiXHQeeQ76ICkbfgklp"
    "Ro7r4PcZ6gp9FzyFmp+uqCHSZH59/yQckhG1zNP0U0u7ruPK6iAQyGuzNZ5rLfj+FuHLUxJ8rz+1XHbFqEOIGJ64RYJbq++/"
    "1X1FpZArCjKRx61UJfvXuCCLZfx9zMvRf4ftP4+L8Tz5YK7Cp7BvkqBdQo4GxX9r2aQdH7zO/ecVNeefeH7nhUsmUJqaGLP2"
    "4by0pADBGMxDFpfV1ZnplvnvtOSAN9LN/x3y9x1Apq+h/5zGcRJT6rf/FnwR+5dfq9z8/tuC/6cl+pMTfMeqzjLG6s+2rnrs"
    "7YI7J9x+a1ZcTBRzsNqGS7/bfqRw5wmMar88e0RMtOz4u8bvv1UO1Xd8rmI90s8axn+jvzN9X/Hrd1nic0v/F2Lj1Fcp/32l"
    "/nPVia1wK2tGgCva8fMw+L+IWWg3ONmn6qgJn4P08X0JWJTahkvf/vG26jqF84QbsyalP71mgd/nucrfb7m6/nPNxvSh31ih"
    "EWe09T047fm3kBSJNGkd0TLqE4Zb2vPBy7+/AN+PKS9pGCwtyf+bJxfdPi0zLKv5KLhz4rP/vNBvwnyD8/331da/VQUPKmTA"
    "O+uXCHLm4je4lgPqJLwRuPs+vy/Rft8IcTqqqTKzNL+eAtEI179G9BtswA333/qpZZdOr2FU110s3HF8R1F1xWfnBJbojXSP"
    "yAiuWDB23tSs+FiO4Ib5vkTij3oN0I5K0a5D0T/Td/9aGPwc8f/Q+i1kwnFw/TLiFWgwCN0jKDsE5UfrRzRA/VuLG2ltQP5+"
    "C9QZSWgr42ds2kTrpCJ4a+wNe7DEm/iCjGzJ/jH3lVP1EZ8LU0bMpyANoUnIHERpDsRrZP8aJZHUEEyru9q7JObX6C8IZqe/"
    "zJsEISG7w5DDvGt2xdz8/ptKMHy6g9kwGL7Qv98y+N9/S15a8XOaf0t+W36RS6vBkG/kpOEGqwm/CGVOYvXfUu4UUCs7h8gF"
    "mhcOav37r+D31war/g34hMLXaCej6qMSVsoQvxVDrKiIhJWMAHQJvEWfjeZHZKKa3MloQEEz6vcdvpi/36LrB+mWhHro9fj9"
    "Nfr7LVhrlx3GSGdJfxljSS7A78DAj0WE0G+uM/CbdGo2/n258jUUrRT+WzoE8y8L/oyebBD717T+c63/7v/n769d9/wbbLBQ"
    "T8xd/w/c34OvUIn6PAAAAABJRU5ErkJggg=="
    ),
}

# Settings saved in settings.json
#   language          "en" or "es" (empty = same as Windows)
#   auto_open_client  open the Riot Client when it is closed and you press Log in
#   input_method      "images" (look for the login boxes on screen) or "keyboard" (any language)
#   template_set      folder of login images that worked last time (set automatically)
#   client_args       extra arguments for RiotClientServices.exe when the app opens the client
#   client_wait_seconds  how long to wait for the Riot Client window after opening it
#   keyboard_field_offset / keyboard_reference_width  where the keyboard method clicks to select the
#                     username box: this many pixels from the window's top-left corner when the window
#                     is 1280 px wide (it scales with the window). Only change it if that click misses.
#   keyboard_wait_seconds  (optional) how long the keyboard method waits for the login form before typing
DEFAULT_SETTINGS = {
    "language": "",
    "auto_open_client": True,
    "input_method": "images",
    "template_set": "",
    "client_args": [],
    "client_wait_seconds": 45,
    "keyboard_field_offset": [165, 216],
    "keyboard_reference_width": 1280,
}  # optional: "keyboard_wait_seconds" = how long the keyboard method waits for the login form

try:
    logging.basicConfig(filename=LOG_FILE, filemode="w", level=logging.INFO,
                        format="%(asctime)s %(message)s", encoding="utf-8")
except OSError:
    pass  # folder not writable: just run without a log file
logging.info("AutoLogger %s starting", APP_VERSION)

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


# ======================================================================================
#  Languages (English / Spanish)
# ======================================================================================
STRINGS = {
    "en": {
        "app_title": "AutoLogger",
        "app_tagline": "Log in to your Riot accounts and start your game in one click",
        "pill_encrypted": "Encrypted",
        "pill_windows": "Windows protection",
        "btn_open_client": "Open Riot Client",
        "btn_settings": "Settings",
        "your_accounts": "Your accounts",
        "count_one": "{n} account",
        "count_many": "{n} accounts",
        "empty_accounts": "No accounts yet.\nAdd your first one below.",
        "login_only": "Login only",
        "btn_login_play": "Log in & play",
        "btn_login": "Log in",
        "btn_edit": "Edit",
        "btn_delete": "Delete",
        "form_add": "Add account",
        "form_edit": "Edit account \u00B7 {name}",
        "lbl_account_name": "Account name",
        "lbl_username": "Username",
        "lbl_password": "Password",
        "lbl_game": "Game",
        "ph_account_name": "e.g. Main account",
        "ph_username": "Riot username",
        "ph_password": "Password",
        "btn_show": "Show",
        "btn_hide": "Hide",
        "btn_cancel": "Cancel",
        "btn_save_changes": "Save changes",
        "btn_ok": "OK",
        "btn_unlock": "Unlock",
        "btn_close": "Close",
        "btn_erase": "Erase",
        "status_ready": "Ready",
        "fill_fields": "Please fill in the account name, username and password.",
        "name_exists": "An account with that name already exists.",
        "account_saved": "Account '{name}' saved.",
        "account_deleted": "Account '{name}' deleted.",
        "delete_title": "Delete account",
        "delete_confirm": "Delete '{name}'? This cannot be undone.",
        "starting_login": "Starting login...",
        "riot_not_found": "Riot Client window not found. Open the Riot Client first (or turn on automatic opening in Settings).",
        "riot_opening": "Opening the Riot Client...",
        "riot_waiting": "Waiting for the Riot Client window...",
        "riot_wait_timeout": "The Riot Client did not open in time.",
        "riot_ready": "The Riot Client is open.",
        "client_in_front": "The Riot Client is already open.",
        "riot_exe_missing": "RiotClientServices.exe not found.",
        "riot_launch_failed": "Could not open the Riot Client: {error}",
        "foreground_failed": "Windows would not bring the Riot Client to the front. Click it in the taskbar and try again.",
        "no_usable_position": "The Riot Client window has no usable position on screen (see autologger.log).",
        "not_on_screen": "The Riot Client window is not on the screen (see autologger.log).",
        "fields_not_found": "Could not recognise the login boxes. If your Riot Client is not in English, choose the Keyboard method in Settings, or run Settings > Diagnostics.",
        "login_button_missing": "Login button not found, pressing Enter instead.",
        "using_keyboard": "Typing the login with the keyboard method...",
        "error_login": "Error during login (see autologger.log).",
        "waiting_login": "Waiting for the login to finish...",
        "login_not_finished": "Login did not seem to finish, the game was not launched.",
        "logged_in": "Logged in.",
        "game_undefined": "Game '{name}' is not defined in games.json.",
        "image_not_found": "Could not find {name} on screen.",
        "play_not_found": "Could not find the Play button on screen. The image {name} has to be captured in your Riot Client's language: save it in assets/templates/<language>/. Settings > Diagnostics shows how close the match was.",
        "unknown_game_type": "Unknown game type '{kind}' for {name}.",
        "launched": "Launched {name}.",
        "launch_failed": "Could not launch {name}: {error}",
        "login_running": "A login is already running, please wait.",
        "choose_title": "Protect your accounts",
        "choose_text": "Choose how AutoLogger keeps your accounts safe. You can change this later in Settings.",
        "choose_password_title": "Master password",
        "choose_password_desc": "You type it every time you open the app. The most secure option. It cannot be recovered if you forget it.",
        "choose_password_btn": "Use a master password",
        "choose_windows_title": "No master password",
        "choose_windows_desc": "The app opens straight away. Your accounts stay encrypted and only your Windows user can read them.",
        "choose_windows_btn": "Continue without a master password",
        "create_master_title": "Create master password",
        "create_master_text": "Create a master password (at least {min} characters). It encrypts your accounts and CANNOT be recovered if you forget it.",
        "repeat_master_text": "Repeat the master password.",
        "change_master_title": "Change master password",
        "pw_too_short": "Use at least {min} characters.",
        "pw_mismatch": "The passwords do not match.",
        "unlock_title": "Welcome back",
        "unlock_text": "Enter your master password to unlock your accounts.",
        "wrong_password": "Wrong master password.",
        "forgot_password": "Forgot your password?",
        "migrated_ask": "Your accounts are now protected in accounts.enc.\n\nDelete the old plain-text accounts.json now?",
        "legacy_warning": "Warning: the old plain-text accounts.json still exists. Delete it when you are done.",
        "windows_open_failed_title": "Cannot open your accounts",
        "windows_open_failed": "These accounts were saved by another Windows user or on another PC, so they cannot be opened here.\n\nYou can erase all data and start from scratch. Do you want to do that?",
        "setup_failed": "Could not set up the protection: {error}",
        "settings_title": "Settings",
        "sec_language": "Language",
        "sec_security": "Security",
        "sec_riot": "Riot Client",
        "sec_recognition": "Login recognition",
        "sec_diagnostics": "Diagnostics",
        "diag_help": "If something does not work, open the Riot Client on the screen where it fails (the login screen, or the League screen with its Play button) and press the button. The app hides for a moment and saves autologger_report.txt and a picture of the Riot Client window. Look at the picture before sharing it.",
        "btn_diagnostics": "Run diagnostics",
        "diag_running": "Running diagnostics... the window hides for a moment.",
        "diag_done": "Diagnostics saved: {report} and {picture}.",
        "diag_failed": "Diagnostics failed: {error}",
        "version_label": "Version {version}",
        "sec_data": "Data",
        "protect_now_password": "Protection: master password",
        "protect_now_windows": "Protection: no master password (Windows account)",
        "btn_change_master": "Change master password",
        "btn_use_windows": "Switch to no master password",
        "btn_use_password": "Switch to a master password",
        "protect_changed": "Protection updated.",
        "protect_failed": "Could not change the protection: {error}",
        "windows_mode_note": "Without a master password, anyone using your Windows account can open the app.",
        "switch_windows_confirm": "Switch to no master password? Your accounts stay encrypted, but the app will open without asking for it.",
        "auto_open_label": "Open the Riot Client automatically when it is closed",
        "client_path": "Detected client: {path}",
        "client_path_none": "Riot Client not found on this PC.",
        "method_images": "Images (default)",
        "method_keyboard": "Keyboard (any language)",
        "method_help": "Images look for the login boxes on screen. Keyboard clicks where the username box is in a standard Riot Client window and types the login, so it works in any language.",
        "templates_help": "More languages: put the 3 login images in assets/templates/<name>/ and they are tried automatically.",
        "btn_reset_settings": "Restore default settings",
        "reset_settings_confirm": "Restore the default settings and game list? Your accounts are not touched.",
        "settings_reset_done": "Settings restored to defaults.",
        "btn_erase_all": "Erase all data...",
        "erase_title": "Erase all data",
        "erase_text": "This deletes your accounts, master password, settings and log. It cannot be undone.\n\nType {word} to confirm.",
        "erase_word": "DELETE",
        "erase_done": "All data was erased. Open the app again to start from scratch.",
        "erase_failed": "Some files could not be deleted: {error}",
    },
    "es": {
        "app_title": "AutoLogger",
        "app_tagline": "Inicia sesi\u00F3n en tus cuentas de Riot y abre tu juego con un clic",
        "pill_encrypted": "Cifrado",
        "pill_windows": "Protecci\u00F3n de Windows",
        "btn_open_client": "Abrir Riot Client",
        "btn_settings": "Ajustes",
        "your_accounts": "Tus cuentas",
        "count_one": "{n} cuenta",
        "count_many": "{n} cuentas",
        "empty_accounts": "A\u00FAn no hay cuentas.\nA\u00F1ade la primera aqu\u00ED abajo.",
        "login_only": "Solo iniciar sesi\u00F3n",
        "btn_login_play": "Entrar y jugar",
        "btn_login": "Entrar",
        "btn_edit": "Editar",
        "btn_delete": "Eliminar",
        "form_add": "A\u00F1adir cuenta",
        "form_edit": "Editar cuenta \u00B7 {name}",
        "lbl_account_name": "Nombre de la cuenta",
        "lbl_username": "Usuario",
        "lbl_password": "Contrase\u00F1a",
        "lbl_game": "Juego",
        "ph_account_name": "p. ej. Cuenta principal",
        "ph_username": "Usuario de Riot",
        "ph_password": "Contrase\u00F1a",
        "btn_show": "Mostrar",
        "btn_hide": "Ocultar",
        "btn_cancel": "Cancelar",
        "btn_save_changes": "Guardar cambios",
        "btn_ok": "Aceptar",
        "btn_unlock": "Desbloquear",
        "btn_close": "Cerrar",
        "btn_erase": "Borrar",
        "status_ready": "Listo",
        "fill_fields": "Rellena el nombre de la cuenta, el usuario y la contrase\u00F1a.",
        "name_exists": "Ya existe una cuenta con ese nombre.",
        "account_saved": "Cuenta '{name}' guardada.",
        "account_deleted": "Cuenta '{name}' eliminada.",
        "delete_title": "Eliminar cuenta",
        "delete_confirm": "\u00BFEliminar '{name}'? No se puede deshacer.",
        "starting_login": "Iniciando sesi\u00F3n...",
        "riot_not_found": "No se encuentra la ventana del Riot Client. \u00C1brelo primero (o activa la apertura autom\u00E1tica en Ajustes).",
        "riot_opening": "Abriendo el Riot Client...",
        "riot_waiting": "Esperando a la ventana del Riot Client...",
        "riot_wait_timeout": "El Riot Client no se abri\u00F3 a tiempo.",
        "riot_ready": "El Riot Client est\u00E1 abierto.",
        "client_in_front": "El Riot Client ya est\u00E1 abierto.",
        "riot_exe_missing": "No se encuentra RiotClientServices.exe.",
        "riot_launch_failed": "No se pudo abrir el Riot Client: {error}",
        "foreground_failed": "Windows no quiso poner el Riot Client delante. Haz clic en \u00E9l en la barra de tareas e int\u00E9ntalo de nuevo.",
        "no_usable_position": "La ventana del Riot Client no tiene una posici\u00F3n v\u00E1lida en pantalla (mira autologger.log).",
        "not_on_screen": "La ventana del Riot Client no est\u00E1 en la pantalla (mira autologger.log).",
        "fields_not_found": "No se reconocen las casillas de inicio de sesi\u00F3n. Si tu Riot Client no est\u00E1 en ingl\u00E9s, elige el m\u00E9todo de Teclado en Ajustes o ejecuta Ajustes > Diagn\u00F3stico.",
        "login_button_missing": "No se encuentra el bot\u00F3n de entrar, se pulsa Enter.",
        "using_keyboard": "Escribiendo el inicio de sesi\u00F3n con el m\u00E9todo de teclado...",
        "error_login": "Error durante el inicio de sesi\u00F3n (mira autologger.log).",
        "waiting_login": "Esperando a que termine el inicio de sesi\u00F3n...",
        "login_not_finished": "El inicio de sesi\u00F3n no parece haber terminado, no se abri\u00F3 el juego.",
        "logged_in": "Sesi\u00F3n iniciada.",
        "game_undefined": "El juego '{name}' no est\u00E1 definido en games.json.",
        "image_not_found": "No se encuentra {name} en pantalla.",
        "play_not_found": "No se encuentra el bot\u00F3n de jugar en pantalla. La imagen {name} hay que capturarla en el idioma de tu Riot Client: gu\u00E1rdala en assets/templates/<idioma>/. Ajustes > Diagn\u00F3stico muestra lo cerca que estuvo.",
        "unknown_game_type": "Tipo de juego desconocido '{kind}' para {name}.",
        "launched": "{name} iniciado.",
        "launch_failed": "No se pudo iniciar {name}: {error}",
        "login_running": "Ya hay un inicio de sesi\u00F3n en curso, espera un momento.",
        "choose_title": "Protege tus cuentas",
        "choose_text": "Elige c\u00F3mo guarda AutoLogger tus cuentas. Podr\u00E1s cambiarlo despu\u00E9s en Ajustes.",
        "choose_password_title": "Contrase\u00F1a maestra",
        "choose_password_desc": "La escribes cada vez que abres la app. Es la opci\u00F3n m\u00E1s segura. No se puede recuperar si la olvidas.",
        "choose_password_btn": "Usar contrase\u00F1a maestra",
        "choose_windows_title": "Sin contrase\u00F1a maestra",
        "choose_windows_desc": "La app se abre directamente. Tus cuentas siguen cifradas y solo tu usuario de Windows puede leerlas.",
        "choose_windows_btn": "Continuar sin contrase\u00F1a maestra",
        "create_master_title": "Crea la contrase\u00F1a maestra",
        "create_master_text": "Crea una contrase\u00F1a maestra (m\u00EDnimo {min} caracteres). Cifra tus cuentas y NO se puede recuperar si la olvidas.",
        "repeat_master_text": "Repite la contrase\u00F1a maestra.",
        "change_master_title": "Cambiar contrase\u00F1a maestra",
        "pw_too_short": "Usa al menos {min} caracteres.",
        "pw_mismatch": "Las contrase\u00F1as no coinciden.",
        "unlock_title": "Bienvenido de nuevo",
        "unlock_text": "Escribe tu contrase\u00F1a maestra para desbloquear tus cuentas.",
        "wrong_password": "Contrase\u00F1a maestra incorrecta.",
        "forgot_password": "\u00BFHas olvidado la contrase\u00F1a?",
        "migrated_ask": "Tus cuentas ya est\u00E1n protegidas en accounts.enc.\n\n\u00BFBorrar ahora el accounts.json antiguo, que est\u00E1 en texto plano?",
        "legacy_warning": "Aviso: todav\u00EDa existe el accounts.json antiguo en texto plano. B\u00F3rralo cuando termines.",
        "windows_open_failed_title": "No se pueden abrir tus cuentas",
        "windows_open_failed": "Estas cuentas se guardaron con otro usuario de Windows o en otro PC, as\u00ED que no se pueden abrir aqu\u00ED.\n\nPuedes borrar todos los datos y empezar de cero. \u00BFQuieres hacerlo?",
        "setup_failed": "No se pudo configurar la protecci\u00F3n: {error}",
        "settings_title": "Ajustes",
        "sec_language": "Idioma",
        "sec_security": "Seguridad",
        "sec_riot": "Riot Client",
        "sec_recognition": "Reconocimiento del inicio de sesi\u00F3n",
        "sec_diagnostics": "Diagn\u00F3stico",
        "diag_help": "Si algo no funciona, abre el Riot Client en la pantalla donde falla (el inicio de sesi\u00F3n, o la pantalla de League con su bot\u00F3n de jugar) y pulsa el bot\u00F3n. La app se oculta un momento y guarda autologger_report.txt y una imagen de la ventana del Riot Client. Mira la imagen antes de compartirla.",
        "btn_diagnostics": "Ejecutar diagn\u00F3stico",
        "diag_running": "Ejecutando el diagn\u00F3stico... la ventana se oculta un momento.",
        "diag_done": "Diagn\u00F3stico guardado: {report} y {picture}.",
        "diag_failed": "El diagn\u00F3stico fall\u00F3: {error}",
        "version_label": "Versi\u00F3n {version}",
        "sec_data": "Datos",
        "protect_now_password": "Protecci\u00F3n: contrase\u00F1a maestra",
        "protect_now_windows": "Protecci\u00F3n: sin contrase\u00F1a maestra (cuenta de Windows)",
        "btn_change_master": "Cambiar contrase\u00F1a maestra",
        "btn_use_windows": "Pasar a sin contrase\u00F1a maestra",
        "btn_use_password": "Pasar a contrase\u00F1a maestra",
        "protect_changed": "Protecci\u00F3n actualizada.",
        "protect_failed": "No se pudo cambiar la protecci\u00F3n: {error}",
        "windows_mode_note": "Sin contrase\u00F1a maestra, cualquiera que use tu cuenta de Windows puede abrir la app.",
        "switch_windows_confirm": "\u00BFPasar a sin contrase\u00F1a maestra? Tus cuentas siguen cifradas, pero la app se abrir\u00E1 sin pedirla.",
        "auto_open_label": "Abrir el Riot Client autom\u00E1ticamente si est\u00E1 cerrado",
        "client_path": "Cliente detectado: {path}",
        "client_path_none": "No se encuentra el Riot Client en este PC.",
        "method_images": "Im\u00E1genes (por defecto)",
        "method_keyboard": "Teclado (cualquier idioma)",
        "method_help": "Im\u00E1genes busca las casillas de inicio de sesi\u00F3n en pantalla. Teclado hace clic donde est\u00E1 la casilla de usuario en una ventana est\u00E1ndar del Riot Client y escribe el inicio de sesi\u00F3n, as\u00ED que funciona en cualquier idioma.",
        "templates_help": "M\u00E1s idiomas: guarda las 3 im\u00E1genes de inicio de sesi\u00F3n en assets/templates/<nombre>/ y se probar\u00E1n autom\u00E1ticamente.",
        "btn_reset_settings": "Restaurar ajustes predeterminados",
        "reset_settings_confirm": "\u00BFRestaurar los ajustes y la lista de juegos? Tus cuentas no se tocan.",
        "settings_reset_done": "Ajustes restaurados.",
        "btn_erase_all": "Borrar todos los datos...",
        "erase_title": "Borrar todos los datos",
        "erase_text": "Esto borra tus cuentas, la contrase\u00F1a maestra, los ajustes y el registro. No se puede deshacer.\n\nEscribe {word} para confirmar.",
        "erase_word": "BORRAR",
        "erase_done": "Se borraron todos los datos. Abre la app de nuevo para empezar de cero.",
        "erase_failed": "No se pudieron borrar algunos archivos: {error}",
    },
}
LANGUAGE_NAMES = {"en": "English", "es": "Espa\u00F1ol"}  # shown in the language menu, never translated


def detect_system_language():
    # Spanish if Windows (or the environment) is in Spanish, otherwise English
    try:
        if sys.platform == "win32":
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "es" if (lang_id & 0x3FF) == 0x0A else "en"  # 0x0A = Spanish
    except Exception:
        pass
    for variable in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(variable, "").lower().startswith("es"):
            return "es"
    return "en"


def load_settings():
    data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            logging.warning("settings.json could not be read, using defaults")
    merged = {**DEFAULT_SETTINGS, **{k: v for k, v in data.items() if k in DEFAULT_SETTINGS}}
    if merged["language"] not in STRINGS:
        merged["language"] = detect_system_language()
    return merged


def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except OSError:
        logging.exception("Could not save settings.json")


_first_run = {"on": not os.path.exists(SETTINGS_FILE)}
settings = load_settings()


def tr(key, **values):
    # Text in the current language (falls back to English)
    text = STRINGS.get(settings["language"], STRINGS["en"]).get(key) or STRINGS["en"][key]
    return text.format(**values) if values else text


def load_games():
    # Read the game definitions, creating the file with defaults on first run
    if os.path.exists(GAMES_FILE):
        try:
            with open(GAMES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            logging.warning("games.json could not be read, using defaults")
            return dict(DEFAULT_GAMES)
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_GAMES, f, indent=4)
    return dict(DEFAULT_GAMES)


games = load_games()

# Saved accounts; filled by unlock_accounts() at start-up
accounts = {}


# ======================================================================================
#  Protecting the saved accounts
#    "password": encrypted with a key made from the master password (scrypt + Fernet)
#    "windows" : encrypted by Windows itself (DPAPI) for the current Windows user, no password needed
# ======================================================================================
class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _make_blob(data):
    buffer = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _dpapi(function_name, data):
    crypt32 = ctypes.WinDLL("crypt32")
    kernel32 = ctypes.WinDLL("kernel32")
    blob_pointer = ctypes.POINTER(_DATA_BLOB)
    function = getattr(crypt32, function_name)
    function.restype = ctypes.c_int
    if function_name == "CryptProtectData":
        function.argtypes = [blob_pointer, ctypes.c_wchar_p, blob_pointer, ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_uint32, blob_pointer]
    else:
        function.argtypes = [blob_pointer, ctypes.c_void_p, blob_pointer, ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_uint32, blob_pointer]
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    blob_in, keep_alive_1 = _make_blob(data)
    entropy, keep_alive_2 = _make_blob(DPAPI_ENTROPY)
    blob_out = _DATA_BLOB()
    description = "AutoLogger" if function_name == "CryptProtectData" else None
    # 1 = CRYPTPROTECT_UI_FORBIDDEN: never show a Windows prompt
    if not function(ctypes.byref(blob_in), description, ctypes.byref(entropy), None, None, 1,
                    ctypes.byref(blob_out)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))


def dpapi_protect(data):
    return _dpapi("CryptProtectData", data)


def dpapi_unprotect(data):
    return _dpapi("CryptUnprotectData", data)


def windows_protection_available():
    return sys.platform == "win32"


_store = {"mode": None, "fernet": None, "salt": None}  # how accounts.enc is protected right now


def derive_fernet(master_password, salt, n, r, p):
    # Turn the master password into an encryption key (scrypt is deliberately slow)
    kdf = Scrypt(salt=salt, length=32, n=n, r=r, p=p)
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))
    return Fernet(key)


def build_record():
    payload = json.dumps(accounts).encode("utf-8")
    if _store["mode"] == "windows":
        return {"version": 2, "mode": "windows",
                "data": base64.b64encode(dpapi_protect(payload)).decode("ascii")}
    return {
        "version": 2, "mode": "password", "kdf": "scrypt", **KDF_PARAMS,
        "salt": base64.b64encode(_store["salt"]).decode("ascii"),
        "data": _store["fernet"].encrypt(payload).decode("ascii"),
    }


def save_accounts():
    # Protect the whole accounts dictionary and write it to accounts.enc
    record = build_record()
    # Write to a temp file first so a crash can never leave a half-written accounts file
    temp_file = ENCRYPTED_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=4)
    os.replace(temp_file, ENCRYPTED_FILE)


def read_record():
    with open(ENCRYPTED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def encrypted_file_matches(expected):
    # Read accounts.enc back and check it opens to exactly what we meant to save
    record = read_record()
    if record.get("mode", "password") == "windows":
        data = dpapi_unprotect(base64.b64decode(record["data"]))
    else:
        data = _store["fernet"].decrypt(record["data"].encode("ascii"))
    return json.loads(data.decode("utf-8")) == expected


def apply_protection(mode, password=None):
    # Switch how accounts.enc is protected. The new file is read back to make sure it really opens;
    # if anything goes wrong the previous protection is put back, so the accounts are never lost.
    previous = dict(_store)
    try:
        if mode == "windows":
            _store.update(mode="windows", salt=None, fernet=None)
        else:
            salt = os.urandom(16)
            _store.update(mode="password", salt=salt, fernet=derive_fernet(password, salt, **KDF_PARAMS))
        save_accounts()
        if not encrypted_file_matches(accounts):
            raise RuntimeError("the saved file does not match the accounts")
    except Exception:
        _store.update(previous)
        if previous["mode"]:
            try:
                save_accounts()
            except Exception:
                logging.exception("Could not restore the previous protection")
        raise


def ask_new_master_password(title_key="create_master_title"):
    # Ask twice; returns the password, or None if the user cancels
    while True:
        first = ask_password(tr("create_master_text", min=MIN_PASSWORD_LENGTH), tr(title_key))
        if first is None:
            return None
        if len(first) < MIN_PASSWORD_LENGTH:
            messagebox.showerror(tr("app_title"), tr("pw_too_short", min=MIN_PASSWORD_LENGTH), parent=window)
            continue
        second = ask_password(tr("repeat_master_text"), tr(title_key))
        if second is None:
            return None
        if first != second:
            messagebox.showerror(tr("app_title"), tr("pw_mismatch"), parent=window)
            continue
        return first


def change_master_password():
    # Password mode: ask for a new master password. Returns False if the user cancelled.
    password = ask_new_master_password("change_master_title")
    if password is None:
        return False
    apply_protection("password", password)
    return True


def switch_to_password_protection():
    password = ask_new_master_password()
    if password is None:
        return False
    apply_protection("password", password)
    return True


def switch_to_windows_protection():
    apply_protection("windows")
    return True


FORGOT_PASSWORD = object()  # returned by the unlock dialog when the user chooses "Forgot your password?"


def exit_app():
    window.destroy()
    sys.exit(0)


def unlock_with_password(record):
    salt = base64.b64decode(record["salt"])
    for _ in range(3):
        password = ask_password(tr("unlock_text"), tr("unlock_title"), forgot=True)
        if password is None:
            break
        if password is FORGOT_PASSWORD:
            if confirm_erase():
                erase_everything_and_exit()
            break
        try:
            fernet = derive_fernet(password, salt, record["n"], record["r"], record["p"])
            data = fernet.decrypt(record["data"].encode("ascii"))
        except InvalidToken:
            messagebox.showerror(tr("app_title"), tr("wrong_password"), parent=window)
            continue
        accounts.update(json.loads(data.decode("utf-8")))
        _store.update(mode="password", salt=salt, fernet=fernet)
        return
    exit_app()


def unlock_with_windows(record):
    try:
        data = dpapi_unprotect(base64.b64decode(record["data"]))
        accounts.update(json.loads(data.decode("utf-8")))
        _store.update(mode="windows", salt=None, fernet=None)
    except Exception:
        logging.exception("Could not open the Windows-protected accounts")
        if messagebox.askyesno(tr("windows_open_failed_title"), tr("windows_open_failed"), parent=window):
            if confirm_erase():
                erase_everything_and_exit()
        exit_app()


def choose_protection_mode():
    # "password", "windows", or None if the user cancelled
    if not windows_protection_available():
        return "password"
    return ask_protection_choice()


def first_run_setup():
    # No accounts.enc yet: the user chooses how to protect the accounts. An old plain-text
    # accounts.json is migrated into the new protected file.
    legacy = None
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            legacy = json.load(f)

    mode = choose_protection_mode()
    if mode is None:
        exit_app()
    password = None
    if mode == "password":
        password = ask_new_master_password()
        if password is None:
            exit_app()

    if legacy:
        accounts.update(legacy)
    try:
        apply_protection(mode, password)
    except Exception as error:
        logging.exception("Could not set up the protection")
        messagebox.showerror(tr("app_title"), tr("setup_failed", error=error), parent=window)
        exit_app()

    if legacy is not None:
        # The new copy opens correctly, so the plain-text file is no longer needed
        if messagebox.askyesno(tr("app_title"), tr("migrated_ask"), parent=window):
            os.remove(ACCOUNTS_FILE)


def unlock_accounts():
    # Fill `accounts` from accounts.enc, or set up the protection on first run
    if not os.path.exists(ENCRYPTED_FILE):
        first_run_setup()
        return
    record = read_record()
    if record.get("mode", "password") == "windows":
        unlock_with_windows(record)
    else:
        unlock_with_password(record)


def confirm_erase():
    # The user has to type a word, so nothing is erased by accident
    word = tr("erase_word")
    answer = ask_text(tr("erase_text", word=word), tr("erase_title"), masked=False, ok_label=tr("btn_erase"))
    return answer is not None and answer.strip().upper() == word.upper()


def erase_all_data():
    # Delete everything the app saved: accounts, master password, settings, games list and log
    logging.shutdown()  # releases autologger.log so Windows lets us delete it
    removed, errors = [], []
    for path in (ENCRYPTED_FILE, ENCRYPTED_FILE + ".tmp", ACCOUNTS_FILE, SETTINGS_FILE, GAMES_FILE, LOG_FILE):
        try:
            if os.path.exists(path):
                os.remove(path)
                removed.append(path)
        except OSError as error:
            errors.append(f"{path}: {error}")
    return removed, errors


def erase_everything_and_exit():
    removed, errors = erase_all_data()
    if errors:
        messagebox.showwarning(tr("erase_title"), tr("erase_failed", error="; ".join(errors)), parent=window)
    else:
        messagebox.showinfo(tr("erase_title"), tr("erase_done"), parent=window)
    app_exiting["on"] = True
    window.destroy()
    if not window_is_running["on"]:
        sys.exit(0)  # before the main loop started (start-up): stop here


app_exiting = {"on": False}
window_is_running = {"on": False}  # True once window.mainloop() is running


def reset_settings():
    # Back to the default settings and game list; the accounts are not touched
    for path in (SETTINGS_FILE, GAMES_FILE):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            logging.exception("Could not delete %s", path)
    settings.clear()
    settings.update(load_settings())
    games.clear()
    games.update(load_games())


def set_status(message):
    # Update the status label; safe to call from the worker thread
    try:
        window.after(0, lambda: status_var.set(message))
    except Exception:
        pass


def notify(key, **values):
    # A message for the user (in the current language). The log file always gets the English text.
    english = STRINGS["en"][key].format(**values) if values else STRINGS["en"][key]
    print(english)
    logging.info(english)
    set_status(tr(key, **values))


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


def windows_by_process(executables):
    # Visible top-level windows that belong to one of the given programs. This finds the Riot Client
    # whatever language its window title is in.
    if sys.platform != "win32":
        return []
    try:
        user32 = ctypes.WinDLL("user32")
        kernel32 = ctypes.WinDLL("kernel32")
        handle, dword = ctypes.c_void_p, ctypes.c_uint32
        user32.IsWindowVisible.argtypes = [handle]
        user32.GetWindowThreadProcessId.argtypes = [handle, ctypes.POINTER(dword)]
        user32.GetWindowThreadProcessId.restype = dword
        kernel32.OpenProcess.argtypes = [dword, ctypes.c_int, dword]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.QueryFullProcessImageNameW.argtypes = [handle, dword, ctypes.c_wchar_p, ctypes.POINTER(dword)]
        kernel32.CloseHandle.argtypes = [handle]
        found = []

        def on_window(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                pid = dword()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process = kernel32.OpenProcess(0x1000, 0, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
                if process:
                    try:
                        buffer = ctypes.create_unicode_buffer(1024)
                        size = dword(1024)
                        if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                            if os.path.basename(buffer.value).lower() in executables:
                                found.append(hwnd)
                    finally:
                        kernel32.CloseHandle(process)
            return True

        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_int, handle, handle)(on_window), 0)
        window_class = getattr(gw, "Win32Window", None) or gw.Window
        return [window_class(hwnd) for hwnd in found]
    except Exception:
        logging.exception("Could not look for the Riot Client by program name")
        return []


def get_riot_window():
    # Several visible windows can have "Riot Client" in their title (helpers, overlays...).
    # The real client is the biggest one, so pick that instead of simply the first match.
    candidates = gw.getWindowsWithTitle(RIOT_WINDOW_TITLE)
    if not candidates:
        # Not found by title (for example a translated title): look for the program that owns it
        candidates = windows_by_process(RIOT_UI_PROCESSES)
        if candidates:
            logging.info("Riot Client found by program name, not by window title")
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


def prepare_riot_window(rc_window=None):
    # Find the Riot Client window (also when it is minimized in the taskbar), bring it to the front
    # and wait until it has a usable position. Returns the window, or None (with a message).
    if rc_window is None:
        rc_window = get_riot_window()
    if rc_window is None:
        notify("riot_not_found")
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
        notify("foreground_failed")
        return None
    rect = wait_for_window_rect(rc_window)
    if rect is None:
        notify("no_usable_position")
        return None
    logging.info("Window ready at %s", rect)
    return rc_window


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


def riot_client_running():
    return get_riot_window() is not None


def launch_riot_client():
    # Start the Riot Client. Returns True if it was started.
    client = riot_client_path()
    if not client:
        notify("riot_exe_missing")
        return False
    try:
        subprocess.Popen([client] + [str(argument) for argument in settings.get("client_args", [])])
    except OSError as error:
        logging.exception("Could not start the Riot Client")
        notify("riot_launch_failed", error=error)
        return False
    logging.info("Started %s", client)
    return True


def wait_for_riot_window(timeout):
    # Wait until the Riot Client window shows up (after launching it)
    end = time.time() + timeout
    while True:
        rc_window = get_riot_window()
        if rc_window is not None or time.time() >= end:
            return rc_window
        time.sleep(0.5)


# ---- Recognising the login screen ----------------------------------------------------------------
def template_sets():
    # Folders with the three login images, one set per Riot Client language: the default set in
    # assets/ and any assets/templates/<name>/ folder. The set that worked last time goes first.
    default_dir = os.path.dirname(asset_path("assets/username_field.png"))
    sets = [("default", default_dir)]
    for base in (os.path.abspath(os.path.join("assets", "templates")),
                 resource_path(os.path.join("assets", "templates"))):
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                folder = os.path.join(base, name)
                known = [existing for existing, _ in sets]
                if name not in known and os.path.isfile(os.path.join(folder, "username_field.png")):
                    sets.append((name, folder))
    preferred = settings.get("template_set")
    sets.sort(key=lambda item: item[0] != preferred)
    return sets


def login_button_path(folder=None):
    # The red arrow has no text, so it looks the same in every language
    folders = ([folder] if folder else []) + [directory for _, directory in template_sets()]
    for directory in folders:
        path = os.path.join(directory, "login_button.png")
        if os.path.isfile(path):
            return path
    return asset_path("assets/login_button.png")


def locate_login_fields(region):
    # Look for the username and password boxes with each set of images. Returns
    # (set name, folder, username position, password position) or None.
    for name, folder in template_sets():
        username_image = os.path.join(folder, "username_field.png")
        password_image = os.path.join(folder, "password_field.png")
        if not (os.path.isfile(username_image) and os.path.isfile(password_image)):
            continue
        username_field = find_image(username_image, region=region)
        logging.info("[%s] username_field: %s score=%s", name, username_field, getattr(find_image, "last_score", None))
        if not username_field:
            continue
        # The password box is below the username box
        below = region
        if region:
            top = username_field[1] + 10
            height = region[1] + region[3] - top
            if height < 1:
                continue
            below = (region[0], top, region[2], height)
        password_field = find_image(password_image, region=below)
        logging.info("[%s] password_field: %s score=%s", name, password_field, getattr(find_image, "last_score", None))
        if password_field and password_field[1] > username_field[1]:
            return name, folder, username_field, password_field
    return None


def wait_for_login_fields(region, patience):
    # A freshly opened client needs a few seconds to draw the login form, so keep looking for a while
    end = time.time() + patience
    while True:
        found = locate_login_fields(region)
        if found or time.time() >= end:
            return found
        time.sleep(0.5)


def keyboard_field_position(rect):
    # Where the username box is, worked out from the window's position and size. The Riot Client
    # login screen has a fixed layout, so the box is always in the same place relative to the window
    # (this does not depend on the language).
    left, top, width, _height = rect
    scale = width / settings.get("keyboard_reference_width", 1280)
    offset_x, offset_y = settings.get("keyboard_field_offset", [165, 216])
    return round(left + offset_x * scale), round(top + offset_y * scale)


def type_with_keyboard(username, password):
    # Language independent: type the username, Tab to the password, type it and press Enter.
    # Ctrl+A first, so anything already in a box is replaced instead of added to.
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    type_text(username)
    time.sleep(0.2)
    pyautogui.press("tab")
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    type_text(password)
    time.sleep(0.2)
    pyautogui.press("enter")


def login_with_keyboard(username, password, rect, region=None, patient=False):
    # Click the username box (so it really has the keyboard focus), then type the login.
    # First wait for the login form to be on screen: a client that was just opened needs several
    # seconds to draw it, and typing before that goes nowhere. The images tell us when it is there;
    # in a language without images nothing matches, so we simply wait the full time.
    patience = settings.get("keyboard_wait_seconds", 12 if patient else 3)
    if region is not None and patience > 0:
        started = time.time()
        found = wait_for_login_fields(region, patience)
        logging.info("Keyboard method: login form %s after %.1f s", "seen" if found else "not recognised (typing anyway)",
                     time.time() - started)
    x, y = keyboard_field_position(rect)
    logging.info("Keyboard method: window rect=%s, clicking the username box at (%s, %s)", rect, x, y)
    if not pyautogui.onScreen(x, y):
        notify("not_on_screen")
        return False
    pyautogui.click(x, y)
    time.sleep(0.4)
    type_with_keyboard(username, password)
    return True


login_state = {"box_image": None}  # username-box image that matched in the last login (None: keyboard method)


def inject_credentials(username, password, rc_window=None, patient=False):
    # Automate Riot Client login. Returns True when the login was sent, False otherwise.
    # patient=True waits longer for the login form (used right after the client was opened).
    try:
        notify("starting_login")

        # Normally start_login has already brought the window to the front
        if rc_window is None:
            rc_window = prepare_riot_window()
            if rc_window is None:
                return False

        time.sleep(0.1)

        # Get window position to calculate relative click positions (and make sure it is valid)
        rect = wait_for_window_rect(rc_window, timeout=1)
        if rect is None:
            notify("no_usable_position")
            return False
        riot_x, riot_y = rect[0], rect[1]
        region = login_panel_region(rc_window)
        logging.info("Window rect=%s search region=%s", rect, region)

        login_state["box_image"] = None
        if settings.get("input_method") == "keyboard":
            notify("using_keyboard")
            return login_with_keyboard(username, password, rect, region, patient)

        # Click inside the window to ensure focus
        if not pyautogui.onScreen(riot_x + 50, riot_y + 50):
            notify("not_on_screen")
            return False
        pyautogui.click(riot_x + 50, riot_y + 50)
        time.sleep(0.1)

        found = wait_for_login_fields(region, 30 if patient else 3)
        if not found:
            notify("fields_not_found")
            return False
        set_name, folder, username_field, password_field = found
        login_state["box_image"] = os.path.join(folder, "username_field.png")
        if settings.get("template_set") != set_name:
            settings["template_set"] = set_name  # remember which language set worked
            save_settings()

        pyautogui.click(username_field)
        time.sleep(0.3)
        type_text(username)  # Type username slowly

        pyautogui.click(password_field)
        time.sleep(0.3)
        type_text(password)  # Type password slowly

        # Locate and click the login button
        login_button = find_image(login_button_path(folder), region=region)
        logging.info("login_button: %s score=%s", login_button, getattr(find_image, "last_score", None))
        if login_button:
            time.sleep(0.3)
            pyautogui.click(login_button)
            print("Login sequence complete.")
        else:
            # The password field still has focus, so Enter submits the form
            notify("login_button_missing")
            pyautogui.press("enter")
        return True

    except Exception:
        import traceback
        print("Error during injection:")
        traceback.print_exc()
        logging.exception("Error during login")
        set_status(tr("error_login"))
        return False


def wait_login_finished(timeout=30):
    # The login button disappears from the screen once the Riot Client moves past the login form.
    # The red arrow can also be matched by mistake on the next screen (another red button), so the
    # username box going away for a moment also counts as "finished" (only when it was seen at login).
    time.sleep(1.5)
    box = login_state.get("box_image")
    box_missing = 0
    end = time.time() + timeout
    while time.time() < end:
        region = login_panel_region(get_riot_window())
        if find_image(login_button_path(), region=region) is None:
            return True
        if box and os.path.isfile(box):
            box_missing = box_missing + 1 if find_image(box, region=region) is None else 0
            if box_missing >= 3:
                logging.info("The username box is gone, so the login finished (the arrow still looked present)")
                return True
        time.sleep(0.5)
    logging.info("Login button still seen after %s s (score %s)", timeout, getattr(find_image, "last_score", None))
    return False


def play_image_for(game):
    # The Play button image of a game: the one in games.json, or the built-in default of its Riot product
    if "play_image" in game:
        return game["play_image"] or ""
    if game.get("type") == "riot":
        return DEFAULT_PLAY_IMAGES.get(game.get("product"), "")
    return ""


BUILTIN_NAMES = {relative.replace("/", "_"): relative for relative in BUILTIN_IMAGES}


def builtin_image_paths(name):
    # The copies kept inside the program for this file name, written (once) to a temporary folder
    paths = []
    for relative, data in BUILTIN_IMAGES.items():
        if os.path.basename(relative) != name:
            continue
        path = os.path.join(tempfile.gettempdir(), "autologger_builtin", relative.replace("/", "_"))
        try:
            content = base64.b64decode("".join(data))
            if not os.path.isfile(path) or os.path.getsize(path) != len(content):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(content)
            paths.append(path)
        except OSError:
            logging.warning("Could not write the built-in image %s", relative)
    return paths


def play_image_candidates(image):
    # Buttons such as Play have text, so they look different in each Riot Client language. Besides
    # the file named in games.json, the same file name is looked for in every language folder
    # (assets/templates/<name>/), starting with the one that worked for the login. The copies built
    # into the program come last, so they only matter when no file of yours exists.
    name = os.path.basename(image)
    candidates = []
    for _, folder in template_sets():
        path = os.path.join(folder, name)
        if os.path.isfile(path) and path not in candidates:
            candidates.append(path)
    given = asset_path(image)
    if os.path.isfile(given) and given not in candidates:
        candidates.append(given)
    for path in builtin_image_paths(name):
        if path not in candidates:
            candidates.append(path)
    return candidates


def wait_for_any_image(paths, timeout, confidence):
    # Poll the screen until one of the images shows up. Returns (position, path) or None.
    end = time.time() + timeout
    while True:
        for path in paths:
            position = find_image(path, confidence)
            if position:
                return position, path
        if time.time() >= end:
            return None
        time.sleep(0.5)


def click_image_step(image, timeout, confidence):
    # Wait for the image (in any of the language sets) and click it. Returns False, after telling
    # the user why, if it never shows up.
    candidates = play_image_candidates(image)
    if not candidates:
        notify("image_not_found", name=image)
        return False
    found = wait_for_any_image(candidates, timeout, confidence)
    if not found:
        logging.info("None of these images matched on screen: %s", candidates)
        notify("play_not_found", name=os.path.basename(image))
        return False
    logging.info("Clicking %s at %s", found[1], found[0])
    pyautogui.click(found[0])
    return True


def run_diagnostics():
    # Writes autologger_report.txt and a picture of the Riot Client window next to the app: where the
    # window is, how well each image matches and where the keyboard method would click.
    # Usernames and passwords are never written.
    import platform
    from PIL import ImageDraw
    lines = []

    def add(text=""):
        lines.append(text)
        logging.info("[diagnostics] %s", text)

    def best_match(path, region=None):
        # (position, score) of the best match, whatever the score is
        find_image.last_score = None
        try:
            position = find_image(path, confidence=0.0, region=region)
        except Exception as error:
            return None, f"error: {error}"
        score = getattr(find_image, "last_score", None)
        best_match.last = float(score) if score is not None else 0.0
        return position, (f"{score:.2f}" if score is not None else "?")

    best_match.last = 0.0

    def shown_path(path):
        # Short name for the report; "built-in copy" = the image kept inside the program
        if os.path.abspath(path).startswith(os.path.join(tempfile.gettempdir(), "autologger_builtin")):
            return "built-in copy of " + BUILTIN_NAMES.get(os.path.basename(path), path)
        try:
            return os.path.relpath(path)
        except ValueError:  # another drive than the app
            return path

    add("=" * 60)
    add(f"AutoLogger {APP_VERSION} diagnostics, {time.strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"System: {platform.platform()} | Python {platform.python_version()} | screen {tuple(pyautogui.size())}")
    add(f"Settings: language={settings['language']} input_method={settings['input_method']} "
        f"template_set={settings['template_set']!r} auto_open_client={settings['auto_open_client']}")

    rc_window = get_riot_window()
    rect = region = None
    marks = []  # things to draw on the picture
    if rc_window is None:
        add("Riot Client window: NOT FOUND (is it open, and not hidden in the system tray?)")
    else:
        rect = window_rect_if_ready(rc_window)
        add(f"Riot Client window: title={rc_window.title!r} minimized={rc_window.isMinimized} "
            f"position/size={(rc_window.left, rc_window.top, rc_window.width, rc_window.height)} usable={rect is not None}")
        region = login_panel_region(rc_window)
        add(f"Login search region: {region}")

    add("Login images (a good match scores 0.55 or more; they only match on the login screen):")
    set_scores = {}
    for name, folder in template_sets():
        set_scores[name] = []
        for image in ("username_field.png", "password_field.png", "login_button.png"):
            path = os.path.join(folder, image)
            if not os.path.isfile(path):
                add(f"  [{name}] {image}: file missing")
                continue
            position, score = best_match(path, region)
            add(f"  [{name}] {image}: best score {score} at {position}")
            if image != "login_button.png":  # the red arrow looks like other red buttons
                set_scores[name].append(best_match.last)
            if position:
                marks.append(("box", position, Image.open(path).size))
    on_login = [name for name, scores in set_scores.items() if scores and min(scores) >= 0.55]
    if on_login:
        add(f"LOGIN SCREEN: yes (recognised with the images of: {', '.join(on_login)})")
    else:
        add("LOGIN SCREEN: NOT recognised. Low scores are normal if the Riot Client is NOT showing the "
            "login form (for example you are already signed in). To test the login, sign out first.")

    add("Game buttons (needed score = \"confidence\" in games.json, default 0.8):")
    for game_name, game in games.items():
        play = play_image_for(game)
        images = ([play] if play else []) + list(
            game.get("images") or ([game["image"]] if game.get("image") else []))
        if not images:
            add(f"  {game_name}: no button to click (the client starts it by itself)")
        for image in images:
            candidates = play_image_candidates(image)
            if not candidates:
                add(f"  {game_name}: {image}: file missing")
            needed = game.get("confidence", 0.8)
            seen = False
            for path in candidates:
                position, score = best_match(path)
                shown = shown_path(path)
                add(f"  {game_name}: {shown}: best score {score} (needs {needed}) at {position}")
                if position:
                    marks.append(("box", position, Image.open(path).size))
                if position and best_match.last >= needed:
                    seen = True
            if candidates:
                add(f"  {game_name}: button {os.path.basename(image)} {'SEEN on screen' if seen else 'not seen on screen (normal if the game list is not showing)'}")

    if rect:
        x, y = keyboard_field_position(rect)
        add(f"Keyboard method would click at ({x}, {y})")
        marks.append(("cross", (x, y), None))

    picture = "autologger_screenshot_" + time.strftime("%H%M%S") + ".png"
    screenshot = pyautogui.screenshot().convert("RGB")
    draw = ImageDraw.Draw(screenshot)
    if region:
        draw.rectangle([region[0], region[1], region[0] + region[2], region[1] + region[3]], outline=(0, 200, 0), width=3)
    for kind, position, size in marks:
        px, py = position
        if kind == "box":
            draw.rectangle([px - size[0] // 2, py - size[1] // 2, px + size[0] // 2, py + size[1] // 2],
                           outline=(0, 120, 255), width=2)
        else:
            draw.line([px - 25, py - 25, px + 25, py + 25], fill=(255, 0, 0), width=4)
            draw.line([px - 25, py + 25, px + 25, py - 25], fill=(255, 0, 0), width=4)
    if rect:  # only the Riot Client window is saved, not the rest of the screen
        screenshot = screenshot.crop((max(rect[0] - 20, 0), max(rect[1] - 20, 0),
                                      min(rect[0] + rect[2] + 20, screenshot.width),
                                      min(rect[1] + rect[3] + 20, screenshot.height)))
    screenshot.save(picture)
    add(f"Picture: {picture} (green frame = where the login boxes are searched, blue frames = best match of "
        "each image, red cross = where the keyboard method clicks)")
    with open(REPORT_FILE, "a", encoding="utf-8") as report:
        report.write("\n".join(lines) + "\n")
    return REPORT_FILE, picture


def diagnostics_worker(dialog):
    try:
        time.sleep(1.2)  # let our own windows disappear
        rc_window = get_riot_window()
        if rc_window is not None:
            prepare_riot_window(rc_window)  # bring it to the front, as a login would
        report, picture = run_diagnostics()
        notify("diag_done", report=report, picture=picture)
    except Exception as error:
        logging.exception("Diagnostics failed")
        notify("diag_failed", error=error)
    finally:
        login_busy.clear()
        window.after(0, lambda: show_after_diagnostics(dialog))


def show_after_diagnostics(dialog):
    window.deiconify()
    try:
        dialog.deiconify()
        dialog.lift()
        dialog.grab_set()
    except tk.TclError:
        pass


def start_diagnostics(dialog):
    if login_busy.is_set():
        notify("login_running")
        return
    login_busy.set()
    notify("diag_running")
    window.withdraw()  # this hides the settings window too, so the Riot Client is fully visible
    threading.Thread(target=diagnostics_worker, args=(dialog,), daemon=True).start()


def launch_game(name, game):
    # Start the game described in games.json
    kind = game.get("type")
    try:
        if kind == "riot":
            client = riot_client_path()
            if not client:
                notify("riot_exe_missing")
                return
            subprocess.Popen([
                client,
                f"--launch-product={game['product']}",
                f"--launch-patchline={game.get('patchline', 'live')}",
            ])

            # The client only selects some games (League of Legends) and waits for a click on Play,
            # so wait for that button on screen and click it. League has a built-in default.
            play_image = play_image_for(game)
            if play_image:
                time.sleep(game.get("play_delay", 2))
                if not click_image_step(play_image, game.get("timeout", 30), game.get("confidence", 0.8)):
                    return

        elif kind == "image":
            # One image, or a list of images that are clicked in order (e.g. game tab, then Play)
            steps = game.get("images") or [game["image"]]
            for step in steps:
                if not click_image_step(step, game.get("timeout", 60), game.get("confidence", 0.8)):
                    return
                time.sleep(0.5)

        elif kind == "exe":
            subprocess.Popen([game["target"]] + game.get("args", []))

        elif kind == "uri":
            os.startfile(game["target"])  # Windows only

        else:
            notify("unknown_game_type", kind=kind, name=name)
            return

        notify("launched", name=name)

    except Exception as e:
        notify("launch_failed", name=name, error=e)


def run_login_flow(creds, rc_window=None, patient=False):
    # Full flow: log in, wait for the client to finish, then launch the assigned game
    if not inject_credentials(creds["username"], creds["password"], rc_window, patient):
        return

    game_name = creds.get("game", "")
    if not game_name:
        notify("logged_in")
        return

    game = games.get(game_name)
    if not game:
        notify("game_undefined", name=game_name)
        return

    set_status(tr("waiting_login"))
    if not wait_login_finished():
        notify("login_not_finished")
        return

    time.sleep(game.get("delay", 3))
    launch_game(game_name, game)


login_busy = threading.Event()  # set while a login (or the opening of the client) is running


def login_worker(creds, rc_window, fresh=False):
    # fresh=True: the Riot Client was just launched, so wait for its window first
    try:
        if fresh:
            notify("riot_waiting")
            rc_window = wait_for_riot_window(settings.get("client_wait_seconds", 45))
            if rc_window is None:
                notify("riot_wait_timeout")
                return
            time.sleep(2)  # let the login screen finish drawing
            rc_window = prepare_riot_window(rc_window)
            if rc_window is None:
                return
        run_login_flow(creds, rc_window, patient=fresh)
    finally:
        login_busy.clear()


def start_login(creds):
    if login_busy.is_set():
        notify("login_running")
        return
    rc_window = get_riot_window()
    if rc_window is None:
        # The Riot Client is closed: open it first, if the user allows that in Settings
        if not settings.get("auto_open_client", True):
            notify("riot_not_found")
            return
        if not launch_riot_client():
            return
        notify("riot_opening")
        login_busy.set()
        threading.Thread(target=login_worker, args=(creds, None, True), daemon=True).start()
        return
    # Bring the Riot Client to the front HERE, in the thread that just received the user's click:
    # Windows only lets the process that just got input change the foreground window.
    rc_window = prepare_riot_window(rc_window)
    if rc_window is None:
        return
    # The rest runs in a thread so the window does not freeze while we wait for the client
    login_busy.set()
    threading.Thread(target=login_worker, args=(creds, rc_window), daemon=True).start()


def open_riot_client_worker():
    try:
        rc_window = wait_for_riot_window(settings.get("client_wait_seconds", 45))
        if rc_window is None:
            notify("riot_wait_timeout")
            return
        time.sleep(1)
        if prepare_riot_window(rc_window) is not None:
            notify("riot_ready")
    finally:
        login_busy.clear()


def open_riot_client():
    # The "Open Riot Client" button: bring it to the front if it is open, start it if it is not
    if login_busy.is_set():
        notify("login_running")
        return
    rc_window = get_riot_window()
    if rc_window is not None:
        if prepare_riot_window(rc_window) is not None:
            notify("client_in_front")
        return
    if not launch_riot_client():
        return
    notify("riot_opening")
    login_busy.set()
    threading.Thread(target=open_riot_client_worker, daemon=True).start()


# ======================================================================================
#  User interface (customtkinter)
# ======================================================================================
# Colors (purple palette)
BG = "#0B0716"            # window background (a touch darker to lift the cards)
PANEL = "#181226"         # cards / panels
PANEL_ALT = "#221739"     # hover on cards / secondary buttons
PANEL_RAISED = "#1E1632"  # second-level surface (form, dialogs)
INPUT_BG = "#120C20"      # text boxes
BORDER = "#2C2245"
BORDER_STRONG = "#3B2E5E" # card hover border
ACCENT = "#8B5CF6"        # main purple
ACCENT_HOVER = "#9A6EFC"
ACCENT_DEEP = "#6D3DE4"   # pressed / deep purple
ACCENT_SOFT = "#2A1F4A"   # avatar circle
ACCENT_TEXT = "#C2AAFF"   # light purple for small labels
ACCENT_LINE = "#5B37B8"   # underlines, accent strips
DANGER = "#F87171"
DANGER_BORDER = "#5B2530"
DANGER_HOVER = "#2A1218"
TEXT = "#F4F1FF"
MUTED = "#9A90B5"
GOOD = "#34D399"
SPLASH_BG = "#07040E"     # splash is slightly darker so the purple lines stand out
SPLASH_GRID = "#15102A"   # faint grid behind the splash
UI_FONT = "Segoe UI"
HEADLINE_CANDIDATES = ("Bahnschrift Condensed", "Bahnschrift SemiBold Condensed",
                       "Bahnschrift", "Oswald", "Impact", "Segoe UI Black", "Segoe UI")
HEADLINE_FAMILY = UI_FONT  # overwritten once Tk is up and tells us which family is really installed


def font(size, bold=False):
    return ctk.CTkFont(family=UI_FONT, size=size, weight="bold" if bold else "normal")


def headline_font(size, weight="bold"):
    return ctk.CTkFont(family=HEADLINE_FAMILY, size=size, weight=weight)


def pick_font_family(parent, candidates):
    # Return the first family that is really installed on this system (so we never silently fall
    # back to a default we did not choose).
    import tkinter.font as tkfont
    try:
        families = set(tkfont.families(parent))
    except Exception:
        return candidates[-1]
    for name in candidates:
        if name in families:
            return name
    return candidates[-1]


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


if sys.platform == "win32":
    try:  # own taskbar identity, so the taskbar shows our icon instead of Python's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Gasson.AutoLogger")
    except Exception:
        pass

ctk.set_appearance_mode("dark")
window = ctk.CTk(fg_color=BG)
window.title("AutoLogger by Gasson")
window.minsize(860, 420)

# Center the window on the user's screen
try:
    scale = window._get_window_scaling()
except Exception:
    scale = 1.0


def fit_height(preferred):
    # Never taller than the screen (leaving room for the taskbar)
    try:
        available = int(window.winfo_screenheight() / scale) - 90
    except Exception:
        return preferred
    return max(min(preferred, available), 420)


WIN_W, WIN_H = 940, fit_height(740)
x = max((window.winfo_screenwidth() - int(WIN_W * scale)) // 2, 0)
y = max((window.winfo_screenheight() - int(WIN_H * scale)) // 2, 0)
window.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")


ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
_icon_file = {"path": None}  # the .ico built from assets/youricon.png (made once)


def icon_square():
    # assets/youricon.png as a square RGBA image. PIL reads the REAL format from the content, so a
    # JPEG that was only renamed to .png works too (Tk's own PhotoImage cannot read JPEG at all).
    path = asset_path("assets/youricon.png")
    image = Image.open(path).convert("RGBA")
    side = max(image.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    logging.info("Window icon image: %s (%dx%d)", path, image.width, image.height)
    return square


def apply_window_icon(target):
    # Give a window the icon from assets/youricon.png.
    # customtkinter puts its own blue icon on a window ~200 ms after it opens, unless the program
    # has already set one. So the icon is set right away, and once more later just in case.
    def photo_icons():
        # Plain PNG images through iconphoto: used on other systems and as a fallback on Windows
        square = icon_square()
        photos = []
        for size in (256, 64, 32, 16):
            buffer = io.BytesIO()
            square.resize((size, size), Image.LANCZOS).save(buffer, format="PNG")
            photos.append(tk.PhotoImage(data=base64.b64encode(buffer.getvalue())))
        target._icon_images = photos  # keep references, or Tk drops the images
        target.iconphoto(True, *photos)

    def apply():
        try:
            if sys.platform == "win32":
                try:
                    if not _icon_file["path"]:
                        # Classic BMP frames: Tk's Windows icon loader does not understand the PNG-compressed
                        # frames that Pillow writes by default, and then silently keeps the default icon.
                        icon_path = os.path.join(tempfile.gettempdir(), "autologger_icon_v2.ico")
                        icon_square().save(icon_path, format="ICO", sizes=ICON_SIZES, bitmap_format="bmp")
                        _icon_file["path"] = icon_path
                    target.iconbitmap(_icon_file["path"])
                    return
                except tk.TclError:
                    logging.exception("iconbitmap failed, using iconphoto instead")
            photo_icons()
        except Exception:
            logging.exception("Could not set the window icon")

    apply()
    target.after(300, apply)


apply_window_icon(window)

# Figure out which headline font is really available on this computer. Bahnschrift Condensed ships
# with Windows 10/11 and gives the splash a tall "title-card" feel; on anything older we fall back
# to Impact and finally to the UI font. Nothing in the main UI depends on this.
HEADLINE_FAMILY = pick_font_family(window, HEADLINE_CANDIDATES)
logging.info("Headline font: %s", HEADLINE_FAMILY)


# ----------------------------------------------------------------------------------------------
# First-run language picker and splash
# ----------------------------------------------------------------------------------------------
def ask_initial_language():
    # Shown the very first time the app opens, in BOTH languages (we don't know yet which one the
    # user speaks). Returns the two-letter code and never a None: closing the picker keeps the
    # language we detected from Windows.
    picked = {"value": settings.get("language") or "en"}

    picker = ctk.CTkToplevel(window, fg_color=BG)
    picker.title("Language / Idioma")
    picker.transient(window)
    picker.resizable(False, False)
    try:
        picker.attributes("-topmost", True)
    except tk.TclError:
        pass
    apply_window_icon(picker)

    wrap = ctk.CTkFrame(picker, fg_color=PANEL_RAISED, corner_radius=20,
                        border_width=1, border_color=BORDER_STRONG)
    wrap.pack(fill="both", expand=True, padx=14, pady=14)

    ctk.CTkLabel(wrap, text="Choose your language", font=font(20, True),
                 text_color=TEXT).pack(pady=(26, 2))
    ctk.CTkLabel(wrap, text="Elige tu idioma", font=font(14),
                 text_color=ACCENT_TEXT).pack(pady=(0, 24))

    ctk.CTkFrame(wrap, fg_color=ACCENT_LINE, height=2, width=180, corner_radius=1).pack(pady=(0, 24))

    buttons = ctk.CTkFrame(wrap, fg_color="transparent")
    buttons.pack(pady=(0, 10))

    def pick(code):
        picked["value"] = code
        picker.destroy()

    for code, label, hint in (("en", "English", "English"),
                              ("es", "Espa\u00F1ol", "Spanish")):
        column = ctk.CTkFrame(buttons, fg_color="transparent")
        column.pack(side="left", padx=14)
        btn = ctk.CTkButton(column, text=label, width=190, height=74, corner_radius=14,
                            fg_color=ACCENT_SOFT, hover_color=ACCENT, text_color=TEXT,
                            border_width=1, border_color=BORDER_STRONG,
                            font=font(20, True), command=lambda c=code: pick(c))
        btn.pack()
        ctk.CTkLabel(column, text=hint, font=font(11), text_color=MUTED).pack(pady=(6, 0))

    ctk.CTkLabel(wrap, text="You can change it later in Settings  \u00B7  "
                            "Puedes cambiarlo despu\u00e9s en Ajustes",
                 font=font(11), text_color=MUTED).pack(pady=(22, 20))

    # Center on the screen (the main window is still withdrawn)
    picker.update_idletasks()
    dw, dh = 560, 320
    sx = max((picker.winfo_screenwidth() - dw) // 2, 0)
    sy = max((picker.winfo_screenheight() - dh) // 2, 0)
    picker.geometry(f"{dw}x{dh}+{sx}+{sy}")

    picker.protocol("WM_DELETE_WINDOW", picker.destroy)
    try:
        picker.wait_visibility()
        picker.grab_set()
    except tk.TclError:
        pass
    # If the picker was somehow destroyed before wait_window starts, skip the wait to avoid the
    # "bad window path name" error Tkinter raises on an already-gone window.
    try:
        if picker.winfo_exists():
            window.wait_window(picker)
    except tk.TclError:
        pass
    return picked["value"]


def show_splash_screen(on_done):
    # Frameless startup card: "BUSSY SCRIPTS" revealed letter by letter, a thin purple progress bar
    # underneath, then a fade out. All animation is driven by window.after() so Tkinter stays happy.
    try:
        splash = tk.Toplevel(window)
    except tk.TclError:
        on_done()
        return
    splash.overrideredirect(True)
    splash.configure(bg=SPLASH_BG)
    sw, sh = 900, 460
    try:
        splash.attributes("-topmost", True)
        splash.attributes("-alpha", 0.0)
    except tk.TclError:
        pass
    sx = max((splash.winfo_screenwidth() - sw) // 2, 0)
    sy = max((splash.winfo_screenheight() - sh) // 2, 0)
    splash.geometry(f"{sw}x{sh}+{sx}+{sy}")
    try:
        apply_window_icon(splash)
    except Exception:
        pass

    canvas = tk.Canvas(splash, width=sw, height=sh, bg=SPLASH_BG, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    # Faint grid (very subtle, keeps the background from looking flat)
    for gx in range(0, sw, 36):
        canvas.create_line(gx, 0, gx, sh, fill=SPLASH_GRID, width=1)
    for gy in range(0, sh, 36):
        canvas.create_line(0, gy, sw, gy, fill=SPLASH_GRID, width=1)

    # Panel border (a 1 px purple line that outlines the whole splash)
    canvas.create_rectangle(1, 1, sw - 1, sh - 1, outline=ACCENT_LINE, width=1)

    # Evangelion-style corner brackets in all four corners
    bl, bw, m = 28, 3, 22
    for (x0, y0, dx, dy) in ((m, m, 1, 1), (sw - m, m, -1, 1),
                             (m, sh - m, 1, -1), (sw - m, sh - m, -1, -1)):
        canvas.create_line(x0, y0, x0 + dx * bl, y0, fill=ACCENT, width=bw)
        canvas.create_line(x0, y0, x0, y0 + dy * bl, fill=ACCENT, width=bw)

    cx, cy = sw // 2, sh // 2 - 10
    title_font = (HEADLINE_FAMILY, 56, "bold")
    title_text = "BUSSY SCRIPTS"
    extra_space = 4   # tiny gap between letters, Evangelion-style
    space_width = 26  # how wide the literal " " is

    # Dry run: measure every letter at its real font size, add them up with the Evangelion-style
    # spacing. This is what the actual phrase will span, so the accent lines on the sides never
    # clip the last letter.
    letter_widths = []
    probes = []
    title_h = 60
    for ch in title_text:
        if ch == " ":
            letter_widths.append(("space", space_width))
            continue
        item = canvas.create_text(-1000, -1000, text=ch, font=title_font, anchor="w")
        probes.append(item)
        lb = canvas.bbox(item) or (0, 0, 40, 0)
        lw = lb[2] - lb[0]
        title_h = max(title_h, lb[3] - lb[1])
        letter_widths.append(("letter", lw, ch, item))
    total_w = 0
    for entry in letter_widths:
        if entry[0] == "space":
            total_w += entry[1]
        else:
            total_w += entry[1] + extra_space
    total_w -= extra_space  # no trailing gap

    gap = 34
    canvas.create_line(60, cy, cx - total_w // 2 - gap, cy, fill=ACCENT_LINE, width=2)
    canvas.create_line(cx + total_w // 2 + gap, cy, sw - 60, cy, fill=ACCENT_LINE, width=2)

    # Draw every letter at its own x so we can reveal them one by one. Hidden at first (painted
    # the same color as the splash background), then switched to white on the reveal step.
    letter_items = []
    x = cx - total_w // 2
    for entry in letter_widths:
        if entry[0] == "space":
            x += entry[1]
            letter_items.append(None)
            continue
        _, lw, ch, probe_item = entry
        canvas.delete(probe_item)
        item = canvas.create_text(x, cy, text=ch, font=title_font, fill=SPLASH_BG, anchor="w")
        letter_items.append(item)
        x += lw + extra_space

    # Subtitle (hidden at first)
    sub_font = (UI_FONT, 15, "bold")
    sub_item = canvas.create_text(cx, cy + title_h // 2 + 30,
                                  text="A   U   T   O   L   O   G   G   E   R",
                                  font=sub_font, fill=SPLASH_BG, anchor="n")

    tag_item = canvas.create_text(cx, cy + title_h // 2 + 64,
                                  text="BY GASSON",
                                  font=(UI_FONT, 11, "bold"), fill=SPLASH_BG, anchor="n")

    # Thin progress bar (fills up while the letters finish revealing)
    pb_w, pb_h = 240, 3
    pb_x = cx - pb_w // 2
    pb_y = cy + title_h // 2 + 100
    canvas.create_rectangle(pb_x, pb_y, pb_x + pb_w, pb_y + pb_h, outline="", fill=SPLASH_GRID)
    pb_fill = canvas.create_rectangle(pb_x, pb_y, pb_x, pb_y + pb_h, outline="", fill=ACCENT)

    state = {"i": 0, "closed": False}

    def finish():
        if state["closed"]:
            return
        state["closed"] = True
        try:
            splash.destroy()
        except tk.TclError:
            pass
        on_done()

    def animate_progress(step):
        total = 28
        if state["closed"]:
            return
        if step >= total:
            splash.after(420, lambda: fade_out(1.0))
            return
        fw = int(pb_w * (step + 1) / total)
        canvas.coords(pb_fill, pb_x, pb_y, pb_x + fw, pb_y + pb_h)
        splash.after(22, lambda: animate_progress(step + 1))

    def reveal_letter():
        if state["closed"]:
            return
        i = state["i"]
        if i < len(letter_items):
            item = letter_items[i]
            if item is not None:
                canvas.itemconfigure(item, fill=TEXT)
            state["i"] = i + 1
            splash.after(60, reveal_letter)
        else:
            canvas.itemconfigure(sub_item, fill=ACCENT_TEXT)
            canvas.itemconfigure(tag_item, fill=MUTED)
            animate_progress(0)

    def fade_out(alpha):
        if state["closed"]:
            return
        alpha -= 0.07
        if alpha <= 0.02:
            finish()
            return
        try:
            splash.attributes("-alpha", alpha)
        except tk.TclError:
            finish()
            return
        splash.after(16, lambda: fade_out(alpha))

    def fade_in(alpha):
        if state["closed"]:
            return
        alpha += 0.07
        try:
            splash.attributes("-alpha", min(alpha, 1.0))
        except tk.TclError:
            pass
        if alpha >= 1.0:
            splash.after(140, reveal_letter)
            return
        splash.after(16, lambda: fade_in(alpha))

    # Safety net: if anything above fails (no alpha support, clock problem\u2026) the splash is
    # closed after 4.5 s so the user never gets stuck looking at it.
    splash.after(4500, finish)

    # Any click or key press skips the splash
    for event in ("<Button-1>", "<Key>"):
        splash.bind(event, lambda e: finish())

    splash.after(0, lambda: fade_in(0.0))


status_var = tk.StringVar(value=tr("status_ready"))
game_var = tk.StringVar(value="")

account_frames = {}                 # name -> card, so cards can be rebuilt
editing = {"name": None}            # account being edited, or None when adding a new one
password_visible = {"on": False}

# Widgets that build_ui() creates (and re-creates when the language changes)
logo_image = count_label = list_frame = empty_label = form_title = None
label_entry = username_entry = password_entry = show_button = None
game_menu = cancel_button = submit_button = header_pill = None


def with_glyph(glyph, text):
    # Returns "glyph  text". Keeps the text exactly as the user chose their language, we only
    # prepend an arrow / cog / etc. so the buttons read as a pro app and not as default labels.
    return f"{glyph}  {text}"


def no_game_label():
    return tr("login_only")


def mode_pill_text():
    return tr("pill_windows") if _store["mode"] == "windows" else tr("pill_encrypted")


def build_ui():
    # Everything inside the main window. Called at start-up and again when the language changes.
    global logo_image, count_label, list_frame, empty_label, form_title, label_entry, username_entry
    global password_entry, show_button, game_menu, cancel_button, submit_button, header_pill
    global status_row, status_dot
    account_frames.clear()
    editing["name"] = None
    password_visible["on"] = False
    game_var.set(no_game_label())

    # ---- Header ---------------------------------------------------------------------------
    header = ctk.CTkFrame(window, fg_color="transparent")
    header.pack(fill="x", padx=28, pady=(24, 6))
    header.grid_columnconfigure(1, weight=1)

    logo_image = load_logo(46)
    if logo_image is not None:
        ctk.CTkLabel(header, image=logo_image, text="").grid(row=0, column=0, padx=(0, 14))

    text_block = ctk.CTkFrame(header, fg_color="transparent")
    text_block.grid(row=0, column=1, sticky="w")
    title_row = ctk.CTkFrame(text_block, fg_color="transparent")
    title_row.pack(anchor="w")
    ctk.CTkLabel(title_row, text=tr("app_title"), font=font(26, True), text_color=TEXT).pack(side="left")
    header_pill = ctk.CTkLabel(title_row, text=f"  {mode_pill_text()}  ", font=font(11, True), text_color=GOOD,
                               fg_color=PANEL, corner_radius=12, height=26)
    header_pill.pack(side="left", padx=(12, 0), pady=(8, 0))
    ctk.CTkLabel(text_block, text=tr("app_tagline"), font=font(12), text_color=MUTED, anchor="w",
                 justify="left", wraplength=430).pack(anchor="w")

    header_buttons = ctk.CTkFrame(header, fg_color="transparent")
    header_buttons.grid(row=0, column=2, sticky="e")
    ctk.CTkButton(header_buttons, text=with_glyph("\u26A1", tr("btn_open_client")),
                  height=36, corner_radius=10, fg_color="transparent", border_width=1,
                  border_color=ACCENT, hover_color=PANEL_ALT, text_color=ACCENT_TEXT,
                  font=font(13, True), command=lambda: open_riot_client()).pack(side="left", padx=(0, 8))
    ctk.CTkButton(header_buttons, text=with_glyph("\u2699", tr("btn_settings")),
                  height=36, corner_radius=10, fg_color="transparent", border_width=1,
                  border_color=BORDER, hover_color=PANEL_ALT, text_color=TEXT,
                  font=font(13), command=lambda: open_settings()).pack(side="left")

    # Thin purple accent strip between the header and the accounts list (gradient-like: two
    # segments, the darker one on the right).
    accent_row = ctk.CTkFrame(window, fg_color="transparent")
    accent_row.pack(fill="x", padx=28, pady=(10, 0))
    ctk.CTkFrame(accent_row, fg_color=ACCENT, height=2, corner_radius=1).pack(side="left", fill="x", expand=True)
    ctk.CTkFrame(accent_row, fg_color=ACCENT_LINE, height=2, corner_radius=1, width=120).pack(side="left")

    # ---- Accounts list --------------------------------------------------------------------
    list_header = ctk.CTkFrame(window, fg_color="transparent")
    list_header.pack(fill="x", padx=30, pady=(14, 4))
    ctk.CTkLabel(list_header, text=tr("your_accounts"), font=font(15, True), text_color=TEXT).pack(side="left")
    count_label = ctk.CTkLabel(list_header, text="", font=font(12), text_color=MUTED)
    count_label.pack(side="right")

    list_frame = ctk.CTkScrollableFrame(window, fg_color="transparent", scrollbar_button_color=BORDER,
                                        scrollbar_button_hover_color=ACCENT)
    list_frame.pack(fill="both", expand=True, padx=(22, 18), pady=(0, 6))
    empty_label = ctk.CTkLabel(list_frame, text=tr("empty_accounts"), font=font(13), text_color=MUTED,
                               justify="center")

    # ---- Add / edit form ------------------------------------------------------------------
    form = ctk.CTkFrame(window, fg_color=PANEL_RAISED, corner_radius=16, border_width=1, border_color=BORDER_STRONG)
    form.pack(fill="x", padx=28, pady=(6, 4))
    for column in range(4):
        form.grid_columnconfigure(column, weight=1, uniform="fields")

    form_title = ctk.CTkLabel(form, text=tr("form_add"), font=font(15, True), text_color=TEXT, anchor="w")
    form_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(16, 8))

    def field_label(column, text):
        ctk.CTkLabel(form, text=text.upper(), font=font(11, True), text_color=MUTED, anchor="w").grid(
            row=1, column=column, sticky="w", padx=(18 if column == 0 else 6, 6), pady=(0, 4))

    def make_entry(column, placeholder, show=None):
        entry = ctk.CTkEntry(form, placeholder_text=placeholder, height=40, corner_radius=10, border_width=1,
                             fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT,
                             placeholder_text_color=MUTED, font=font(13), show=show)
        entry.grid(row=2, column=column, sticky="ew", padx=(18 if column == 0 else 6, 6), pady=(0, 6))
        return entry

    field_label(0, tr("lbl_account_name"))
    field_label(1, tr("lbl_username"))
    field_label(2, tr("lbl_password"))
    field_label(3, tr("lbl_game"))

    label_entry = make_entry(0, tr("ph_account_name"))
    username_entry = make_entry(1, tr("ph_username"))
    password_entry = make_entry(2, tr("ph_password"), show="\u2022")

    # Small "Show" toggle on the right of the PASSWORD label (handy to check @ # ~ \u20AC are right)
    show_button = ctk.CTkButton(form, text=tr("btn_show"), width=54, height=18, corner_radius=6,
                                fg_color="transparent", hover_color=PANEL_ALT, text_color=ACCENT_TEXT,
                                font=font(11, True), command=lambda: toggle_password())
    show_button.grid(row=1, column=2, sticky="e", padx=(6, 6), pady=(0, 4))

    game_menu = ctk.CTkOptionMenu(form, variable=game_var, values=[no_game_label()] + list(games.keys()),
                                  height=40, corner_radius=10, fg_color=INPUT_BG, button_color=BORDER,
                                  button_hover_color=ACCENT, dropdown_fg_color=PANEL,
                                  dropdown_hover_color=ACCENT_SOFT, dropdown_text_color=TEXT, text_color=TEXT,
                                  font=font(13), dropdown_font=font(13), anchor="w")
    game_menu.grid(row=2, column=3, sticky="ew", padx=(6, 18), pady=(0, 6))

    form_buttons = ctk.CTkFrame(form, fg_color="transparent")
    form_buttons.grid(row=3, column=0, columnspan=4, sticky="e", padx=18, pady=(8, 16))
    cancel_button = ctk.CTkButton(form_buttons, text=tr("btn_cancel"), width=100, height=38, corner_radius=10,
                                  fg_color="transparent", border_width=1, border_color=BORDER,
                                  hover_color=PANEL_ALT, text_color=TEXT, font=font(13),
                                  command=lambda: reset_form())
    submit_button = ctk.CTkButton(form_buttons, text=with_glyph("\u002B", tr("form_add")),
                                  width=170, height=38, corner_radius=10,
                                  fg_color=ACCENT, hover_color=ACCENT_HOVER, font=font(13, True),
                                  command=lambda: submit_form())
    submit_button.pack(side="right")

    # ---- Status line ----------------------------------------------------------------------
    global status_row, status_dot
    status_row = ctk.CTkFrame(window, fg_color="transparent")
    status_row.pack(fill="x", padx=32, pady=(4, 16))
    status_dot = ctk.CTkLabel(status_row, text="\u2022", font=font(18, True), text_color=GOOD, width=14)
    status_dot.pack(side="left", padx=(0, 6))
    ctk.CTkLabel(status_row, textvariable=status_var, font=font(12), text_color=MUTED, anchor="w",
                 justify="left", wraplength=820).pack(side="left", fill="x", expand=True)
    version_badge = ctk.CTkLabel(status_row, text=f"v{APP_VERSION}", font=font(10),
                                 text_color=MUTED, fg_color=PANEL, corner_radius=8)
    version_badge.pack(side="right")


def refresh_header():
    # The little badge next to the title shows how the accounts are protected
    header_pill.configure(text=f"  {mode_pill_text()}  ")


def rebuild_ui(ready=False):
    # Recreate the whole window content (used when the language changes)
    for child in window.winfo_children():
        child.destroy()
    build_ui()
    rebuild_cards()
    if ready:
        status_var.set(tr("status_ready"))  # the old status text was in the previous language


def add_account_card(name, creds):
    # One card per account: avatar, name, game, and the Log in / Edit / Delete buttons
    card = ctk.CTkFrame(list_frame, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
    card.pack(fill="x", padx=6, pady=5)
    card.grid_columnconfigure(1, weight=1)

    def hover_on(event=None, c=card): c.configure(border_color=ACCENT_LINE, fg_color=PANEL_ALT)
    def hover_off(event=None, c=card): c.configure(border_color=BORDER, fg_color=PANEL)
    for w in (card,):
        w.bind("<Enter>", hover_on)
        w.bind("<Leave>", hover_off)

    avatar = ctk.CTkFrame(card, width=46, height=46, corner_radius=23, fg_color=ACCENT_SOFT)
    avatar.grid(row=0, column=0, rowspan=2, padx=(14, 14), pady=14)
    ctk.CTkLabel(avatar, text=name[:1].upper(), fg_color="transparent", text_color=ACCENT_TEXT,
                 font=font(19, True)).place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(card, text=name, font=font(15, True), text_color=TEXT, anchor="w").grid(
        row=0, column=1, sticky="sw", pady=(14, 0))

    game = creds.get("game", "")
    ctk.CTkLabel(card, text=f"\u25B6  {game}" if game else no_game_label(), font=font(12),
                 text_color=ACCENT_TEXT if game else MUTED, anchor="w").grid(
        row=1, column=1, sticky="nw", pady=(0, 14))

    actions = ctk.CTkFrame(card, fg_color="transparent")
    actions.grid(row=0, column=2, rowspan=2, padx=(8, 14))

    ctk.CTkButton(actions, text=with_glyph("\u25B6", tr("btn_login_play") if game else tr("btn_login")),
                  width=150, height=36, corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                  font=font(13, True), command=lambda c=creds: start_login(c)).pack(side="left", padx=(0, 8))
    ctk.CTkButton(actions, text=with_glyph("\u270E", tr("btn_edit")), width=84, height=36, corner_radius=10,
                  fg_color="transparent", border_width=1, border_color=BORDER, hover_color=PANEL_ALT,
                  text_color=TEXT, font=font(13),
                  command=lambda n=name: start_edit_account(n)).pack(side="left", padx=(0, 8))
    ctk.CTkButton(actions, text=with_glyph("\u2715", tr("btn_delete")), width=90, height=36, corner_radius=10,
                  fg_color="transparent", border_width=1, border_color=DANGER_BORDER, hover_color=DANGER_HOVER,
                  text_color=DANGER, font=font(13),
                  command=lambda n=name: delete_account(n)).pack(side="left")

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
    count_label.configure(text=tr("count_one" if len(accounts) == 1 else "count_many", n=len(accounts)))


def toggle_password():
    password_visible["on"] = not password_visible["on"]
    password_entry.configure(show="" if password_visible["on"] else "\u2022")
    show_button.configure(text=tr("btn_hide") if password_visible["on"] else tr("btn_show"))


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
    game_var.set(no_game_label())
    window.focus_set()
    form_title.configure(text=tr("form_add"))
    submit_button.configure(text=tr("form_add"))
    cancel_button.pack_forget()


def start_edit_account(name):
    # Fill the form with the account; nothing is removed until "Save changes" is pressed
    creds = accounts[name]
    reset_form()
    editing["name"] = name
    label_entry.insert(0, name)
    username_entry.insert(0, creds["username"])
    password_entry.insert(0, creds["password"])
    game_var.set(creds.get("game") or no_game_label())
    form_title.configure(text=tr("form_edit", name=name))
    submit_button.configure(text=tr("btn_save_changes"))
    cancel_button.pack(side="right", padx=(0, 10), after=submit_button)


def form_values():
    return label_entry.get().strip(), username_entry.get().strip(), password_entry.get().strip()


def submit_form():
    # Add a new account, or save the one being edited
    name, username, password = form_values()
    selected_game = game_var.get()
    game = "" if selected_game == no_game_label() else selected_game

    if not name or not username or not password:
        set_status(tr("fill_fields"))
        return

    old_name = editing["name"]
    if name != old_name and name in accounts:
        set_status(tr("name_exists"))
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
    set_status(tr("account_saved", name=name))


def delete_account(name):
    if not messagebox.askyesno(tr("delete_title"), tr("delete_confirm", name=name), parent=window):
        return
    if name in accounts:
        del accounts[name]
        save_accounts()
    if editing["name"] == name:
        reset_form()
    rebuild_cards()
    set_status(tr("account_deleted", name=name))


# ---- Dialogs ----------------------------------------------------------------------------------
def make_dialog(title):
    dialog = ctk.CTkToplevel(window, fg_color=PANEL)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.transient(window)
    apply_window_icon(dialog)
    return dialog


def show_modal(dialog, focus_widget=None, size=None):
    # Center the dialog over the main window, make it modal and wait until it is closed
    dialog.update_idletasks()
    dialog_w, dialog_h = size or (dialog.winfo_reqwidth(), dialog.winfo_reqheight())
    pos_x = max(window.winfo_x() + (window.winfo_width() - dialog_w) // 2, 0)
    pos_y = max(window.winfo_y() + (window.winfo_height() - dialog_h) // 2, 0)
    dialog.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}" if size else f"+{pos_x}+{pos_y}")
    try:
        dialog.wait_visibility()
        dialog.grab_set()
    except tk.TclError:
        pass
    dialog.after(150, lambda: (dialog.lift(), (focus_widget or dialog).focus_force()))
    window.wait_window(dialog)


def regrab(dialog):
    # A closed nested dialog releases the modal grab; take it back for the dialog that is still open
    try:
        dialog.grab_set()
    except tk.TclError:
        pass


def ask_text(prompt, title, masked=True, ok_label=None, forgot=False):
    # Modal box with one text field. Returns the text, None if cancelled, or FORGOT_PASSWORD.
    result = {"value": None}
    dialog = make_dialog(title)

    ctk.CTkLabel(dialog, text=title, font=font(17, True), text_color=TEXT, anchor="w").pack(
        fill="x", padx=24, pady=(22, 4))
    ctk.CTkLabel(dialog, text=prompt, font=font(12), text_color=MUTED, wraplength=380, justify="left",
                 anchor="w").pack(fill="x", padx=24, pady=(0, 14))
    entry = ctk.CTkEntry(dialog, show="\u2022" if masked else "", width=380, height=42, corner_radius=10,
                         border_width=1, fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT, font=font(14))
    entry.pack(padx=24)

    def submit(_event=None):
        result["value"] = entry.get()
        dialog.destroy()

    def cancel(_event=None):
        dialog.destroy()

    def forgot_clicked():
        result["value"] = FORGOT_PASSWORD
        dialog.destroy()

    buttons = ctk.CTkFrame(dialog, fg_color="transparent")
    buttons.pack(fill="x", padx=24, pady=(18, 22))
    ctk.CTkButton(buttons, text=ok_label or tr("btn_ok"), width=120, height=38, corner_radius=10,
                  fg_color=ACCENT, hover_color=ACCENT_HOVER, font=font(13, True), command=submit).pack(side="right")
    ctk.CTkButton(buttons, text=tr("btn_cancel"), width=100, height=38, corner_radius=10, fg_color="transparent",
                  border_width=1, border_color=BORDER, hover_color=PANEL_ALT, text_color=TEXT,
                  font=font(13), command=cancel).pack(side="right", padx=(0, 10))
    if forgot:
        ctk.CTkButton(buttons, text=tr("forgot_password"), height=38, corner_radius=10, fg_color="transparent",
                      hover_color=PANEL_ALT, text_color=ACCENT_TEXT, font=font(12),
                      command=forgot_clicked).pack(side="left")

    entry.bind("<Return>", submit)
    dialog.bind("<Escape>", cancel)
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    show_modal(dialog, entry)
    return result["value"]


def ask_password(prompt, title=None, forgot=False):
    # Masked text box. With forgot=True it is the unlock box and offers "Forgot your password?"
    return ask_text(prompt, title or tr("app_title"), masked=True,
                    ok_label=tr("btn_unlock") if forgot else None, forgot=forgot)


def ask_protection_choice():
    # First run: master password or no master password. Returns "password", "windows" or None.
    result = {"value": None}
    dialog = make_dialog(tr("choose_title"))
    ctk.CTkLabel(dialog, text=tr("choose_title"), font=font(18, True), text_color=TEXT, anchor="w").pack(
        fill="x", padx=24, pady=(22, 4))
    ctk.CTkLabel(dialog, text=tr("choose_text"), font=font(12), text_color=MUTED, wraplength=440,
                 justify="left", anchor="w").pack(fill="x", padx=24, pady=(0, 10))

    def option(title_key, description_key, button_key, value, primary):
        card = ctk.CTkFrame(dialog, fg_color=PANEL_ALT, corner_radius=14)
        card.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(card, text=tr(title_key), font=font(14, True), text_color=TEXT, anchor="w").pack(
            fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(card, text=tr(description_key), font=font(12), text_color=MUTED, wraplength=410,
                     justify="left", anchor="w").pack(fill="x", padx=16)

        def choose():
            result["value"] = value
            dialog.destroy()

        ctk.CTkButton(card, text=tr(button_key), height=36, corner_radius=10,
                      fg_color=ACCENT if primary else "transparent", hover_color=ACCENT_HOVER if primary else PANEL,
                      border_width=0 if primary else 1, border_color=BORDER,
                      text_color=TEXT, font=font(13, True), command=choose).pack(anchor="e", padx=16, pady=(10, 14))

    option("choose_password_title", "choose_password_desc", "choose_password_btn", "password", True)
    option("choose_windows_title", "choose_windows_desc", "choose_windows_btn", "windows", False)
    ctk.CTkButton(dialog, text=tr("btn_cancel"), height=34, corner_radius=10, fg_color="transparent",
                  hover_color=PANEL_ALT, text_color=MUTED, font=font(12), command=dialog.destroy).pack(
        pady=(4, 18))
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    show_modal(dialog)
    return result["value"]


# ---- Settings -----------------------------------------------------------------------------------
def open_settings():
    state = {"rebuild": False, "ready": False}
    dialog = make_dialog(tr("settings_title"))
    body = ctk.CTkScrollableFrame(dialog, fg_color="transparent", scrollbar_button_color=BORDER,
                                  scrollbar_button_hover_color=ACCENT)
    body.pack(fill="both", expand=True, padx=14, pady=(14, 0))

    def section(key):
        ctk.CTkLabel(body, text=tr(key), font=font(15, True), text_color=TEXT, anchor="w").pack(
            fill="x", padx=8, pady=(18, 4))

    def note(text):
        ctk.CTkLabel(body, text=text, font=font(12), text_color=MUTED, wraplength=520, justify="left",
                     anchor="w").pack(fill="x", padx=8, pady=(0, 6))

    def action_button(text, command, danger=False):
        ctk.CTkButton(body, text=text, height=36, corner_radius=10, fg_color="transparent", border_width=1,
                      border_color=DANGER_BORDER if danger else BORDER,
                      hover_color=DANGER_HOVER if danger else PANEL_ALT,
                      text_color=DANGER if danger else TEXT, font=font(13), anchor="w",
                      command=command).pack(fill="x", padx=8, pady=4)

    def menu(values, variable, command):
        ctk.CTkOptionMenu(body, values=values, variable=variable, command=command, height=38, corner_radius=10,
                          fg_color=INPUT_BG, button_color=BORDER, button_hover_color=ACCENT,
                          dropdown_fg_color=PANEL, dropdown_hover_color=ACCENT_SOFT, dropdown_text_color=TEXT,
                          text_color=TEXT, font=font(13), dropdown_font=font(13), anchor="w").pack(
            fill="x", padx=8, pady=(0, 4))

    # ---- Language ----
    section("sec_language")
    language_var = tk.StringVar(value=LANGUAGE_NAMES[settings["language"]])

    def choose_language(choice):
        code = next(code for code, name in LANGUAGE_NAMES.items() if name == choice)
        if code != settings["language"]:
            settings["language"] = code
            save_settings()
            state["rebuild"] = True
            state["ready"] = True
            dialog.destroy()

    menu(list(LANGUAGE_NAMES.values()), language_var, choose_language)

    # ---- Security ----
    section("sec_security")
    mode = _store["mode"]
    note(tr("protect_now_windows") if mode == "windows" else tr("protect_now_password"))

    def attempt(action, confirm_key=None):
        if confirm_key and not messagebox.askyesno(tr("settings_title"), tr(confirm_key), parent=dialog):
            return
        try:
            done = action()
        except Exception as error:
            logging.exception("Protection change failed")
            notify("protect_failed", error=error)
            messagebox.showerror(tr("settings_title"), tr("protect_failed", error=error), parent=dialog)
            regrab(dialog)
            return
        if done:
            notify("protect_changed")
            state["rebuild"] = True
            dialog.destroy()
        else:
            regrab(dialog)

    if mode == "windows":
        action_button(tr("btn_use_password"), lambda: attempt(switch_to_password_protection))
        note(tr("windows_mode_note"))
    else:
        action_button(tr("btn_change_master"), lambda: attempt(change_master_password))
        if windows_protection_available():
            action_button(tr("btn_use_windows"), lambda: attempt(switch_to_windows_protection,
                                                                 "switch_windows_confirm"))

    # ---- Riot Client ----
    section("sec_riot")
    auto_open_var = tk.BooleanVar(value=bool(settings["auto_open_client"]))

    def toggle_auto_open():
        settings["auto_open_client"] = bool(auto_open_var.get())
        save_settings()

    ctk.CTkSwitch(body, text=tr("auto_open_label"), variable=auto_open_var, command=toggle_auto_open,
                  progress_color=ACCENT, font=font(13), text_color=TEXT).pack(anchor="w", padx=8, pady=(2, 6))
    client = riot_client_path()
    note(tr("client_path", path=client) if client else tr("client_path_none"))

    # ---- Login recognition ----
    section("sec_recognition")
    method_names = {"images": tr("method_images"), "keyboard": tr("method_keyboard")}
    method_var = tk.StringVar(value=method_names.get(settings["input_method"], method_names["images"]))

    def choose_method(choice):
        settings["input_method"] = next(code for code, name in method_names.items() if name == choice)
        save_settings()

    menu(list(method_names.values()), method_var, choose_method)
    note(tr("method_help"))
    note(tr("templates_help"))

    # ---- Diagnostics ----
    section("sec_diagnostics")
    note(tr("diag_help"))
    action_button(tr("btn_diagnostics"), lambda: start_diagnostics(dialog))

    # ---- Data ----
    section("sec_data")

    def do_reset_settings():
        if not messagebox.askyesno(tr("settings_title"), tr("reset_settings_confirm"), parent=dialog):
            return
        reset_settings()
        notify("settings_reset_done")
        state["rebuild"] = True
        dialog.destroy()

    def do_erase_all():
        if confirm_erase():
            erase_everything_and_exit()
        else:
            regrab(dialog)

    action_button(tr("btn_reset_settings"), do_reset_settings)
    action_button(tr("btn_erase_all"), do_erase_all, danger=True)

    ctk.CTkLabel(dialog, text=tr("version_label", version=APP_VERSION), font=font(11), text_color=MUTED).pack(pady=(10, 0))
    ctk.CTkButton(dialog, text=tr("btn_close"), width=120, height=38, corner_radius=10, fg_color=ACCENT,
                  hover_color=ACCENT_HOVER, font=font(13, True), command=dialog.destroy).pack(pady=(6, 14))

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    show_modal(dialog, size=(620, fit_height(740)))
    if state["rebuild"] and not app_exiting["on"]:
        rebuild_ui(ready=state["ready"])
        refresh_header()


# ---- Start-up ---------------------------------------------------------------------------------
# On first run, ask for the language BEFORE the main UI is built, so every label is in the chosen
# language from the first frame. Then play the splash animation, and only then ask for the master
# password and load the accounts.
window.withdraw()


def after_splash():
    window.deiconify()
    window.lift()
    window.focus_force()
    unlock_accounts()
    refresh_header()
    rebuild_cards()
    if os.path.exists(ACCOUNTS_FILE):
        status_var.set(tr("legacy_warning"))


def startup_sequence():
    if _first_run["on"]:
        chosen = ask_initial_language()
        settings["language"] = chosen
        save_settings()
    build_ui()
    show_splash_screen(after_splash)


window.after(60, startup_sequence)
window_is_running["on"] = True
window.mainloop()
