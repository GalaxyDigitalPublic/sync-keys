# Adapted from GalaxyBlockchainEngineering/staking_agent .github/scripts/check_lock.py at commit
# db88c9cb267a2f8e796237d774ca91ebbdc58ad7: sync-keys has one git dependency (ethstaker-deposit), pinned in the
# Dockerfile as ETHSTAKER_DEPOSIT_REF (the commit its tag in requirements.txt points to).
"""Fail if requirements.lock / the Dockerfile drifted from requirements.txt.

The image installs only requirements.lock (hashed) plus ethstaker-deposit, built from the Dockerfile's pinned commit,
so a pin changed in requirements.txt without regenerating the lock would otherwise ship silently.
"""

import re
import sys
from pathlib import Path

# ethstaker-deposit-cli tag -> the commit it points to (git ls-remote ... 'refs/tags/<tag>^{}'). Add the new tag here
# when bumping it in requirements.txt, together with ETHSTAKER_DEPOSIT_REF in the Dockerfile.
ETHSTAKER_TAGS = {"v1.3.0": "d8016bc8ca25d7f85e143828b6d99160f55a640f"}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pins(text: str) -> dict:
    return {
        norm(n): v
        for n, v in re.findall(
            r"^([A-Za-z0-9][A-Za-z0-9_.\-]*)(?:\[[^\]]*\])?==([^\s\;#\\]+)",
            text,
            re.MULTILINE,
        )
    }


def check(root: Path) -> list:
    errors = []
    requirements = (root / "requirements.txt").read_text()
    lock = pins((root / "requirements.lock").read_text())
    for name, version in pins(requirements).items():
        if lock.get(name) != version:
            errors.append(
                f"requirements.txt pins {name}=={version}, requirements.lock has {lock.get(name)}"
            )
    tag = re.search(r"ethstaker-deposit-cli@(\S+)", requirements)
    arg = re.search(
        r"^ARG ETHSTAKER_DEPOSIT_REF=(\S+)",
        (root / "Dockerfile").read_text(),
        re.MULTILINE,
    )
    tag_name = tag.group(1) if tag else None
    want = ETHSTAKER_TAGS.get(tag_name or "")
    if not want:
        errors.append(f"ethstaker-deposit tag {tag_name} is not in ETHSTAKER_TAGS")
    elif not arg or arg.group(1) != want:
        errors.append(
            f"Dockerfile ETHSTAKER_DEPOSIT_REF {arg and arg.group(1)} != {tag_name} ({want})"
        )
    return errors


if __name__ == "__main__":
    problems = check(Path(__file__).resolve().parents[2])
    for problem in problems:
        print(problem, file=sys.stderr)
    sys.exit(1 if problems else 0)
