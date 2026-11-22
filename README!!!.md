# Autologger V2

**A Python-based Riot Games account login automation tool.**

Autologger V2 is a personal project developed in Python, based on the original Autologger application created by **Gassonexe (Luka Galonjic)**. This version introduces improvements to the original implementation, providing a more polished graphical interface, enhanced account management and an updated login automation system.

The application allows users to store, manage and automatically log into multiple Riot Games accounts through a simple graphical interface.

---

## Table of Contents

- [About the Application](#about-the-application)
- [Features](#features)
- [How It Works](#how-it-works)
- [Security and Privacy](#security-and-privacy)
- [Installation](#installation)
  - [Method 1: Using the Executable](#method-1-using-the-executable)
  - [Method 2: Running the Python Source Code](#method-2-running-the-python-source-code)
- [Compatibility and Limitations](#compatibility-and-limitations)
- [Disclaimer](#disclaimer)
- [Credits](#credits)
- [License](#license)

---

## About the Application

Autologger V2 is designed to simplify the process of logging into multiple Riot Games accounts.

Users can create, edit and delete as many account profiles as they need. Each profile contains a customizable name, username and password.

Additionally, users can select which game should launch after successfully logging in:

- **League of Legends**
- **VALORANT**
- **Login Only:** Log into the Riot Client without automatically launching a game.

When a game is selected, the application waits for an intentional 3-second delay before attempting to launch it.

The application features a graphical user interface (GUI) built with Tkinter and CustomTkinter, providing a cleaner and more intuitive experience than the original version.

## Features

- **Multiple Account Management:** Create, edit and delete an unlimited number of account profiles.
- **Custom Profile Names:** Give each account a personalized name for easier identification.
- **Encrypted Credentials:** Protect stored usernames and passwords using a master password.
- **Local Storage:** Account information is stored in a local JSON file.
- **Automated Login:** Automatically enter credentials into the Riot Client.
- **Image Recognition:** Locate interface elements through image recognition.
- **Automatic Game Launching:** Launch VALORANT or League of Legends after logging in.
- **Simple GUI:** Manage everything through an intuitive graphical interface.
- **Open Source:** The source code is available for inspection and personal use under the terms of the project's license.

---

## How It Works

### 1. Initial Setup and Master Password

When launching Autologger V2 for the first time, users will be prompted to configure a master password.

This password is used as part of the encryption process to protect the credentials associated with the account profiles stored by the application.

**IMPORTANT:** Your master password is essential. If you lose or forget it, you will not be able to access your previously protected credentials. You will need to reinstall or reset the application and configure your account profiles again.

Make sure to choose a password you can remember and keep it somewhere safe.

### 2. Creating an Account Profile

Once the initial setup is complete, you will have access to the main interface.

From there, you can:

- Create new account profiles.
- Change existing profile names.
- Update usernames and passwords.
- Delete profiles you no longer need.

Your account information is saved locally in a JSON file located in the same directory as the executable.

### 3. Automated Login Process

To start the login process:

1. Open the Riot Games Client.
2. Launch Autologger V2.
3. Select the account profile you want to use.
4. The application will locate the Riot Client window, even if it is minimized or running in windowed mode.
5. The application will bring the Riot Client to the foreground.
6. Using image recognition and automated mouse and keyboard inputs, it will locate the appropriate interface elements and enter your stored username and password.
7. Once the credentials have been entered, the application will automatically move the cursor to the login button and click it.

The login process is performed locally through automated interactions with the Riot Client interface.

### 4. Automatic Game Launching

When configuring or selecting an account profile, users can choose between three options:

- VALORANT
- League of Legends
- Login Only

If a game is selected, Autologger V2 will attempt to launch the corresponding game after a deliberate 3-second delay following the login process.

If no game is selected, the application will simply perform the login without attempting to launch anything else.

---

## Security and Privacy

Autologger V2 is designed to operate locally on your computer.

**No external server connection is required for its intended functionality.**

The application does not require an external account database or cloud-based credential storage. All account information is stored locally in a JSON file located in the application's directory.

For additional security:

- Usernames and passwords are encrypted before being stored.
- A master password is configured during the initial setup.
- Account information remains on the local machine.
- Users can inspect the complete Python source code to understand how the application works.

The project is open source, allowing anyone to review its implementation rather than having to blindly trust a precompiled executable.

**Transparency is important:** Users who do not trust the executable are encouraged to inspect the source code and run the Python script directly.

---

## Installation

There are two ways to run Autologger V2.

### Method 1: Using the Executable

This is the easiest installation method.

1. Download or clone the repository.
2. Extract the project files if necessary.
3. Locate `AutologgerV2.exe`.
4. Double-click the executable to launch the application.
5. Complete the initial master password setup.

No separate Python installation or manual dependency installation is required when using the provided executable.

**Note:** Keep the `assets` folder in the same directory as the executable. Do not rename, move or delete its contents, as the application relies on these resources for image recognition.

### Method 2: Running the Python Source Code

If you prefer not to execute a precompiled executable, you can run the original Python source code directly.

This method is recommended for users who want to inspect the code or prefer running the application through their own Python environment.

**Requirements:**

- Python 3.x installed on your computer.
- Pip package manager.
- All project dependencies installed.

**Step 1. Install Python**

Download and install Python 3.x from the official website:

https://www.python.org/downloads/

Make sure Python and Pip are available from your Windows Command Prompt.

**Step 2. Install the required dependencies**

Open a CMD or terminal window inside the project directory.

Install all required packages using the following command:

```bash
pip install pyautogui pygetwindow opencv-python pillow cryptography customtkinter pyinstaller
```

**Step 3. Run the application**

Once all dependencies have been installed, execute the following command from the same directory:

```bash
py "Autologger by Gasson.py"
```

Make sure to preserve the exact filename, including capitalization and spaces.

The application should now launch directly from your Python environment.

---

## Compatibility and Limitations

Please keep the following limitations in mind before using Autologger V2:

- **Language:** The current version is designed exclusively for the Riot Games Client in English.
- **Display Scaling:** Custom Windows display scaling settings may interfere with image recognition.
- **Resolution:** Different screen resolutions may cause image recognition to fail.
- **Assets:** Do not modify or remove files inside the `assets` directory. These images are required for the automation system to identify interface elements.
- **Riot Client:** The Riot Games Client must be running before selecting an account profile.
- **Interface Changes:** Updates to the Riot Client interface may affect the application's image recognition and automated interactions.

For the best experience, use the default Windows display scaling settings and the English version of the Riot Games Client.

---

## Disclaimer

**PLEASE READ THIS SECTION CAREFULLY BEFORE USING AUTOLOGGER V2.**

Autologger V2 is an independent, unofficial and community-developed project. It is not affiliated with, endorsed by, sponsored by or associated with Riot Games, Inc. in any way.

This application uses automated mouse and keyboard interactions to perform login actions within the Riot Games Client. Such automation may conflict with Riot Games' Terms of Service, policies or community guidelines.

**Using third-party automation software may expose your Riot Games accounts to potential disciplinary action**, including temporary suspensions, permanent bans or other account restrictions.

The developers make no guarantees regarding the safety of using this application with Riot Games services.

By downloading, installing or using Autologger V2, you acknowledge and accept that:

1. You are solely responsible for how you use the application.
2. You understand that using third-party automation software may result in account penalties.
3. The developers are not responsible for temporary suspensions, permanent bans, account restrictions or any other consequences resulting from the use of this software.
4. The developers assume no responsibility for disputes, conflicts or issues arising between users and Riot Games.
5. You use this application entirely at your own risk.

This project is provided strictly for **educational and personal purposes**.

If you are uncomfortable with the potential risks associated with third-party automation, do not use this application.

**USE AT YOUR OWN RISK.**

---

## Credits

The original Autologger project was conceived and developed by:

**Gassonexe (Luka Galonjic)**

Autologger V2 is based on his original concept and implementation, with modifications and improvements introduced to provide an enhanced version of the application.

Full credit and recognition are given to the original creator for developing the initial project.

Thank you, Gassonexe, for the original idea and foundation that made this project possible.

---

## License

This project is distributed under an existing license.

The original project and its associated rights belong to their respective creator, as established by the project's licensing terms.

For complete information regarding permissions, restrictions, redistribution and usage rights, please refer to the **`LICENSE`** file included in the root directory of this repository.

By downloading, modifying or redistributing this project, you agree to respect the terms and conditions established in that license.
