import urllib.request
import os

os.makedirs('assets/fonts', exist_ok=True)
url = 'https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Black.ttf'
out_path = 'assets/fonts/Poppins-Black.ttf'
print(f"Downloading {url} to {out_path}...")
try:
    urllib.request.urlretrieve(url, out_path)
    print("Done!")
except Exception as e:
    print(f"Error: {e}")
