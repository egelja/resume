import mimetypes
import shutil
import typing as t
from datetime import datetime
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


def _use_default_avatar() -> None:
    console.print("Using default avatar")
    shutil.copy(default_picture_file, picture_file.with_suffix(".png"))


def _download_avatar() -> bool:
    if "basics" not in RESUME or "image" not in RESUME["basics"]:
        # no avatar
        return False

    # Have picture, download
    console.print(f"Downloading avatar from {RESUME['basics']['image']}")

    res = httpx.get(RESUME["basics"]["image"], timeout=TIMEOUT)

    # Check if ok
    if res.status_code != 200:
        # Download failed
        console.print("Could not download resume image", style="bold red")
        return False

    # Save image
    content_type = res.headers["Content-Type"]
    ext = mimetypes.guess_extension(content_type)

    if ext is None:
        # Unknown extension
        console.print(f"Unknown file type {content_type}", style="bold red")
        return False

    # Open the picture file and save the image
    with picture_file.with_suffix(ext).open("wb") as f:
        f.write(res.content)

    # Success
    return True


# Perform download
if not _download_avatar():
    _use_default_avatar()


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
    block_start_string="<&",
    block_end_string="&>",
    variable_start_string="<<",
    variable_end_string=">>",
    comment_start_string="<#",
    comment_end_string="#>",
)

# Date format filter
def format_date(date_str: str) -> str:
    if not date_str:
        return "Present"

    try:
        date = datetime.fromisoformat(date_str)
    except Exception as e:
        console.print(e)
        return "???"

    return date.strftime("%b %Y")


env.filters["format_date"] = format_date

# Url escape filter
def latex_escape(s: str) -> str:
    return s.replace("#", "\#").replace("%", "\%").replace("&", "\&")


env.filters["latex_escape"] = latex_escape

# Render the templates
console.print()


def _should_render(key: str):
    # TODO(nino): Improve this for sub-keys of key
    if key not in RESUME or not RESUME[key]:
        return False
    return True


def _render_template(name: str, args: dict[str, t.Any] = dict()) -> None:
    console.print(f"Rendering template {name}... ", end="")

    out_file = OUTPUT_DIR / name
    render = env.get_template(name).render(**args)

    with out_file.open("w") as f:
        f.write(render)

    console.print("Rendered", style="bold green")


# Prelude
if _should_render("basics"):
    _render_template("0_prelude.tex", RESUME["basics"])

# Profile
if _should_render("basics"):
    _render_template("1_profile.tex", RESUME["basics"])

# Work
if _should_render("work"):
    _render_template("2_work.tex", RESUME)

# Education
if _should_render("education"):
    _render_template("3_education.tex", RESUME)

# Education
if _should_render("volunteer"):
    _render_template("4_volunteer.tex", RESUME)
