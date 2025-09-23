import pathlib
import sys


scheme_name = "orca"


def is_protocol_registered():
    import winreg

    try:
        key_path = rf"SOFTWARE\Classes\{scheme_name}"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False


def register_protocol():
    import winreg

    executable = sys.executable

    # We do not need a console window for handling the protocol
    if executable.endswith("python.exe"):
        executable = executable.replace("python.exe", "pythonw.exe")

    script_file = pathlib.Path(__file__).parent / "url_handler.py"

    try:
        # Create the main key for the custom scheme
        key_path = rf"SOFTWARE\Classes\{scheme_name}"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"URL:{scheme_name} Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)

        # Create the 'shell\open\command' subkeys
        command_key_path = rf"{key_path}\shell\open\command"
        command_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, command_key_path)
        winreg.SetValueEx(
            command_key,
            "",
            0,
            winreg.REG_SZ,
            f'"{executable}" "{script_file}" --url "%1"',
        )
        winreg.CloseKey(command_key)

        print(f"URI scheme '{scheme_name}' registered successfully.")
    except Exception as e:
        print(f"Error registering URI scheme: {e}")


def unregister_protocol():
    import winreg

    try:
        key_path = rf"SOFTWARE\Classes\{scheme_name}"
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell\open\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell\open")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        print(f"URI scheme '{scheme_name}' unregistered successfully.")
    except Exception as e:
        print(f"Error unregistering URI scheme: {e}")
