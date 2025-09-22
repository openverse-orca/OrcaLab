import os
import urllib.parse


url = "?url=http://localhost:8000/hello.txt"
safe_string = "orca://download-asset" + urllib.parse.quote_plus(url, safe="/")
os.system(f"start {safe_string}")
