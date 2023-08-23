import glob
import mimetypes
import shutil
from os import getenv
from pathlib import Path
from sys import exit

import httpx
import jinja2
from rich.console import Console

JSON_RESUME_URL = "https://www.nikola.cx/assets/json/resume.json"
TIMEOUT = 20

ROOT_DIR = Path(__file__).resolve().parent

TEMPLATE_DIR = ROOT_DIR / "templates"
RESOURCES_DIR = ROOT_DIR / "resources"
OUTPUT_DIR = ROOT_DIR / "sections"

console = Console()


###############################################################################
# Get our resume
###############################################################################
res = httpx.get(JSON_RESUME_URL, timeout=TIMEOUT)

if res.status_code != 200:
    console.print("Could not get Resume JSON", style="bold red")
    exit(1)

RESUME = res.json()

if getenv("RESUME_DEBUG", default=False):
    console.print_json(res.text)


###############################################################################
# Download resume picture
###############################################################################
picture_file = RESOURCES_DIR / "avatar"
default_picture_file = RESOURCES_DIR / "_avatar.png"

# Delete old files
for file in RESOURCES_DIR.glob("avatar*"):
    console.print(f"Deleting old avatar {file}")
    file.unlink()


def _use_default_picture():
    console.print("Using default avatar")
    shutil.copy(default_picture_file, picture_file.with_suffix(".png"))


if "basics" in RESUME and "image" in RESUME["basics"]:
    # Have picture, download
    console.print(f"Downloading avatar from {RESUME['basics']['image']}")

    res = httpx.get(RESUME["basics"]["image"], timeout=TIMEOUT)

    # Check if ok
    if res.status_code != 200:
        # Download failed
        console.print("Could not download resume image", style="bold red")
        _use_default_picture()
    else:
        # Save image
        content_type = res.headers["Content-Type"]
        ext = mimetypes.guess_extension(content_type)

        if ext is None:
            # Unknown extension
            console.print(f"Unknown file type {content_type}", style="bold red")
            _use_default_picture()
        else:
            # Open the picture file and save the image
            with picture_file.with_suffix(ext).open("wb") as f:
                f.write(res.content)
else:
    # No picture provided
    _use_default_picture()


###############################################################################
# Render templates
###############################################################################
# Clear old renders
shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
OUTPUT_DIR.mkdir(parents=True)

# Set up jinja2
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader([TEMPLATE_DIR]),
    autoescape=False,  # Assume all data is trusted
)

# Render templates
