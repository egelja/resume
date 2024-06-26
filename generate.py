import mimetypes
import shutil
import typing as t
from datetime import datetime
from os import getenv
from pathlib import Path
from sys import exit
import orjson
import httpx
import jinja2
from rich.console import Console

JSON_RESUME_URL = "https://raw.githubusercontent.com/egelja/egelja.github.io/master/assets/json/resume.json"
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
    console.print(
        f"Could not get Resume JSON (Status code {res.status_code})", style="bold red"
    )
    exit(1)

#RESUME = res.json()
with open("resume.json", 'rb') as f:
    RESUME = orjson.loads(f.read())

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
# Prepare data
###############################################################################
# Escape our data
@t.overload
def latex_escape(data: str) -> str:
    ...


@t.overload
def latex_escape(data: dict) -> dict:
    ...


@t.overload
def latex_escape(data: list) -> list:
    ...


def latex_escape(data: str | list | dict | t.Any) -> str | list | dict | t.Any:
    if isinstance(data, dict):
        return {key: latex_escape(val) for key, val in data.items()}
    elif isinstance(data, list):
        return [latex_escape(val) for val in data]
    elif isinstance(data, str):
        return (
            data.replace("#", "\\#")
            .replace("%", "\\%")
            .replace("&", "\\&")
            .replace("\260", "\\degree{}")
            .replace(" - ", " -- ")  # em dash
        )
    else:
        return data


RESUME = latex_escape(RESUME)

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
def format_date(date_str: str, full_month: bool = False) -> str:
    if not date_str:
        return "Present"

    try:
        date = datetime.fromisoformat(date_str)
    except Exception as e:
        console.print(e)
        return "???"

    if full_month:
        return date.strftime("%B %Y")
    return date.strftime("%b %Y")


env.filters["format_date"] = format_date

# Full date format filter
def format_date_full(date_str: str) -> str:
    try:
        date = datetime.fromisoformat(date_str)
    except Exception as e:
        console.print(e)
        return "???"

    return date.strftime("%Y.%m.%d")


env.filters["format_date_full"] = format_date_full

# Study type fix for NU
def fix_study_type_and_area(study_type: str, area: str) -> str:
    if '/' not in study_type or '/' not in area:
        return f"{study_type}, {area}"

    # Get areas
    area1, area2 = area.split('/')

    # Get degrees
    deg1, rest = study_type.split('/')
    deg2, rest = rest.split(' ', 1)

    # Put back together
    return f"{deg1} {rest}, {area1}; {deg2} {rest}, {area2}"

env.filters["fix_study_type_and_area"] = fix_study_type_and_area

# Fluency to percentage
def fluency_to_percentage(s: str) -> str:
    s = s.lower()

    if "native" in s:
        return "1.0"
    elif "full professional" in s:
        return "0.8"
    elif "professional" in s:
        return "0.6"
    elif "limited" in s:
        return "0.4"
    elif "elementary" in s:
        return "0.2"

    return "0.0"


env.filters["fluency_to_percentage"] = fluency_to_percentage

# Short fluency
def short_fluency(s: str) -> str:
    s = s.lower()

    if "native" in s:
        return "Native Speaker"
    elif "full professional" in s:
        return "Fluent"
    elif "professional" in s:
        return "Conversational"
    elif "limited" in s:
        return "Limited"
    elif "elementary" in s:
        return "Elementary"

    return "0.0"


env.filters["short_fluency"] = short_fluency

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


# Profile
if _should_render("basics"):
    _render_template("1_profile.tex", RESUME["basics"])

# Education
if _should_render("education"):
    _render_template("2_education.tex", RESUME)

# Work
if _should_render("work"):
    _render_template("3_work.tex", RESUME)

# Projects
if _should_render("projects"):
    _render_template("4_projects.tex", RESUME)

# Awards
if _should_render("awards"):
    _render_template("5_awards.tex", RESUME)

# Skills
if _should_render("skills"):
    _render_template("6_skills.tex", RESUME)
