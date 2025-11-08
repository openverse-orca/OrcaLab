import os
import sys

url = "http://localhost:8000/box_pc.pak"
safe_string = "orca://download-asset/?url=" + url

if sys.platform == "win32":
    os.system(f"start {safe_string}")
else:
    os.system(f"xdg-open {safe_string}")
