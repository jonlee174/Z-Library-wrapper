"""Locate, load and validate the user's config.ini.

No login UI: credentials live in a plain .ini the user edits once. We look in a
per-user location that survives app reinstalls and is always writable.
"""

from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import APP_NAME


class ConfigError(Exception):
    """Raised when the config file is missing or incomplete. The message is
    user-facing and names the exact path + required fields."""


@dataclass
class AppConfig:
    email: str
    password: str
    download_dir: str = ""
    default_count: int = 25
    default_format: str = ""
    path: Optional[Path] = None


def user_config_dir() -> Path:
    """Per-user config directory, per OS."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    # Linux / dev fallback
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def config_path() -> Path:
    """The single config path we read from and tell the user to edit."""
    override = os.environ.get("Z_LIBRARY_CONFIG")
    if override:
        return Path(override)
    return user_config_dir() / "config.ini"


TEMPLATE = """\
[credentials]
email = you@example.com
password = your_password

[settings]
; download_dir: leave blank to use your OS Downloads folder
download_dir =
; default number of results to fetch per search
default_count = 25
; default file format filter: blank, PDF, EPUB, MOBI, ...
default_format =
"""


def ensure_template() -> Path:
    """Create the config directory and a template file if none exists.
    Returns the path. Locks perms to the user where the OS supports it."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(TEMPLATE, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # Windows relies on the per-user APPDATA ACL
    return path


def load_config() -> AppConfig:
    """Load and validate the config, raising ConfigError with a helpful,
    user-facing message when it's missing or the credentials are unfilled."""
    path = config_path()

    if not path.exists():
        created = ensure_template()
        raise ConfigError(
            "No config file was found, so a template was created for you at:\n\n"
            f"    {created}\n\n"
            "Open it, fill in your Z-Library email and password under "
            "[credentials], then start the app again."
        )

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    email = parser.get("credentials", "email", fallback="").strip()
    password = parser.get("credentials", "password", fallback="").strip()

    if not email or not password or email == "you@example.com":
        raise ConfigError(
            "Your config file is missing a valid email and/or password.\n\n"
            f"Edit this file:\n\n    {path}\n\n"
            "and set your real Z-Library credentials under [credentials]."
        )

    try:
        default_count = parser.getint("settings", "default_count", fallback=25)
    except ValueError:
        default_count = 25

    return AppConfig(
        email=email,
        password=password,
        download_dir=parser.get("settings", "download_dir", fallback="").strip(),
        default_count=max(1, min(default_count, 100)),
        default_format=parser.get("settings", "default_format", fallback="").strip(),
        path=path,
    )
