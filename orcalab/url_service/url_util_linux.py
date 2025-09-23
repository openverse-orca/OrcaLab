import os
import sys
import pathlib


def _application_folder():
    home = pathlib.Path.home()
    return home / ".local/share/applications"


def _desktop_entry_file_path():
    return _application_folder() / "orca-url-handler.desktop"


def _mime_file_path():
    return pathlib.Path.home() / ".config/mimeapps.list"


# https://specifications.freedesktop.org/desktop-entry-spec/latest/
def _write_desktop_entry():
    if not _application_folder().exists():
        os.makedirs(_application_folder())

    executable = sys.executable

    script_file = pathlib.Path(__file__).parent / "url_handler.py"

    text = f"""[Desktop Entry]
Name=Orca URL Handler
Exec=code
Type=Application
NoDisplay=true
MimeType=x-scheme-handler/orca;
Exec={executable} {script_file} --url %u
        """

    with open(_desktop_entry_file_path(), "w", encoding="utf-8") as f:
        f.write(text)


def _update_desktop_database():
    os.system("update-desktop-database ~/.local/share/applications")


def _set_mime_association():
    os.system("xdg-mime default orca-url-handler.desktop x-scheme-handler/orca")


def is_protocol_registered():
    if not os.path.exists(_desktop_entry_file_path()):
        return False

    return True


def register_protocol():
    try:
        _write_desktop_entry()
        _update_desktop_database()
        _set_mime_association()
    except Exception as e:
        print(f"Error registering URI scheme: {e}")


def unregister_protocol():
    file = _desktop_entry_file_path()

    if not os.path.exists(file):
        return

    try:
        os.remove(file)
    except Exception as e:
        print(f"Error unregistering URI scheme: {e}")
