"""Fails unless RELEASE_TAG is a stable vX.Y.Z tag equal to nexiom_connect.__version__."""

import os
import re
import sys
from pathlib import Path

source = Path("src/nexiom_connect/_version.py").read_text(encoding="utf-8")
match = re.fullmatch(r'__version__ = "([^"]+)"\n', source)

if match is None:
    sys.exit("src/nexiom_connect/_version.py must contain only __version__")

version = match.group(1)
tag = os.environ.get("RELEASE_TAG", "")

if re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag) is None:
    sys.exit(f"Release tag must be a stable version such as v0.1.0, not {tag!r}")

if tag != f"v{version}":
    sys.exit(f"Version mismatch: __version__={version}, tag={tag}")

print(f"Release {tag} matches __version__")  # noqa: T201
