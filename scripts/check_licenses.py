# SPDX-License-Identifier: Apache-2.0
"""Verify every runtime dependency is licensed compatibly with Apache-2.0.

De-Scramble is Apache-2.0 and intends to stay usable by anyone, including
commercially, without legal homework. That promise is only as good as the
licences underneath it: a single copyleft dependency arriving through a
transitive upgrade would quietly impose obligations this project does not
advertise, on people who never agreed to them.

So this is checked on every dependency change rather than audited once. It
reads licences from the metadata of what is *actually installed*, not from a
hand-maintained list that drifts from reality the first time a dependency
updates.

Usage:
    python scripts/check_licenses.py            # verify, non-zero exit on failure
    python scripts/check_licenses.py --notice   # emit the dependency block for NOTICE

Run it in an environment containing the runtime dependencies only (``pip
install .``), so that development and build tooling is not mistaken for
something that ships.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import sys

#: Licences that impose no restriction preventing Apache-2.0 redistribution.
PERMISSIVE = {
    "Apache-2.0",
    "MIT",
    "MIT-0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "0BSD",
    "ISC",
    "Python-2.0",
    "PSF-2.0",
    "Unlicense",
    "CC0-1.0",
    "Zlib",
}

#: File-level copyleft, accepted deliberately and recorded rather than waved
#: through. MPL-2.0 attaches its obligations to the MPL-licensed files
#: themselves, not to software that merely depends on them, so an Apache-2.0
#: project can depend on and redistribute it provided those files are not
#: modified. De-Scramble does not modify or vendor any of them. Anything
#: reaching this list is listed explicitly in NOTICE so the decision is visible
#: rather than buried in a tool.
WEAK_COPYLEFT_ACCEPTED = {"MPL-2.0"}

#: Licences that would make redistribution under Apache-2.0 misleading or
#: impose obligations on users that this project does not declare. Any of these
#: is a hard failure rather than a warning: the point of the gate is to stop
#: the release, not to annotate it.
INCOMPATIBLE_MARKERS = (
    "GPL", "AGPL", "LGPL", "SSPL", "BUSL", "Business Source",
    "CC-BY-NC", "NonCommercial", "Proprietary", "Commons Clause",
)

#: Packaging and tooling present in any environment; not shipped as part of the
#: runtime and therefore out of scope for this gate.
NOT_SHIPPED = {"pip", "setuptools", "wheel", "descramble", "pkg-resources"}

CLASSIFIER_TO_SPDX = {
    "Apache Software License": "Apache-2.0",
    "MIT License": "MIT",
    "MIT No Attribution License (MIT-0)": "MIT",
    "BSD License": "BSD-3-Clause",
    "ISC License (ISCL)": "ISC",
    "Python Software Foundation License": "PSF-2.0",
    "The Unlicense (Unlicense)": "Unlicense",
    "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": "CC0-1.0",
    "zlib/libpng License": "Zlib",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "GNU General Public License (GPL)": "GPL",
    "GNU General Public License v2 (GPLv2)": "GPL-2.0",
    "GNU General Public License v3 (GPLv3)": "GPL-3.0",
    "GNU Lesser General Public License v2 (LGPLv2)": "LGPL-2.0",
    "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0",
    "GNU Affero General Public License v3": "AGPL-3.0",
}

_NORMALISE = {
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "asl 2": "Apache-2.0",
    "mit": "MIT",
    "mit license": "MIT",
    "bsd": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "3-clause bsd license": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "isc": "ISC",
    "psf-2.0": "PSF-2.0",
    "python software foundation license": "PSF-2.0",
    "mpl-2.0": "MPL-2.0",
    "the unlicense": "Unlicense",
}


def _normalise(raw: str) -> str:
    return _NORMALISE.get(raw.strip().lower(), raw.strip())


def licence_of(dist: metadata.Distribution) -> tuple[str, str]:
    """Return the licence and where it was found, for one installed distribution.

    Three sources are consulted, most authoritative first. Modern packages
    declare a machine-readable SPDX expression; older ones only have
    classifiers; a few put the entire licence text in a free-text field, which
    is why long values are reduced to their first line rather than reported
    verbatim.
    """
    meta = dist.metadata

    expression = meta.get("License-Expression")
    if expression:
        return _normalise(expression), "License-Expression"

    classifiers = [
        value.split("::")[-1].strip()
        for value in meta.get_all("Classifier") or []
        if value.startswith("License ::")
    ]
    for classifier in classifiers:
        if classifier in CLASSIFIER_TO_SPDX:
            return CLASSIFIER_TO_SPDX[classifier], "Classifier"
    if classifiers:
        return _normalise(classifiers[0]), "Classifier"

    free_text = (meta.get("License") or "").strip()
    if free_text:
        first_line = free_text.splitlines()[0].strip()
        if len(first_line) > 60:
            match = re.search(
                r"(Apache[^\n,]*2\.0|MIT|BSD[^\n,]*|ISC|MPL[^\n,]*|[AL]?GPL[^\n,]*)",
                free_text,
            )
            first_line = match.group(1) if match else first_line[:60] + "..."
        return _normalise(first_line), "License"

    return "UNKNOWN", "none"


def _terms(expression: str) -> list[list[str]]:
    """Split an SPDX expression into OR-alternatives, each a list of AND-terms.

    Modern packaging declares compound expressions — ``Apache-2.0 OR
    BSD-2-Clause``, ``MIT AND PSF-2.0`` — and treating those as opaque strings
    produces findings that are pure noise. Noise is not harmless here: a gate
    that cries wolf four times gets skimmed, and the fifth finding is the real
    one.
    """
    cleaned = expression.replace("(", " ").replace(")", " ")
    return [
        [term.strip() for term in alternative.split(" AND ") if term.strip()]
        for alternative in cleaned.split(" OR ")
    ]


def verdict(licence: str) -> tuple[str, str]:
    """Classify a licence as OK, NOTE, REVIEW, or FAIL, with the reason.

    Compound expressions are evaluated properly: under OR the licensee may
    choose, so one acceptable alternative is enough; under AND every term
    binds, so all of them must be acceptable.
    """
    if licence == "UNKNOWN":
        return "FAIL", "no licence declared in package metadata; cannot be verified"

    if any(marker.lower() in licence.lower() for marker in INCOMPATIBLE_MARKERS):
        return "FAIL", "copyleft or restricted; incompatible with Apache-2.0 redistribution"

    alternatives = _terms(licence)
    acceptable = PERMISSIVE | WEAK_COPYLEFT_ACCEPTED

    for alternative in alternatives:
        if all(term in PERMISSIVE for term in alternative):
            return "OK", "permissive"

    for alternative in alternatives:
        if all(term in acceptable for term in alternative):
            noted = sorted(set(alternative) & WEAK_COPYLEFT_ACCEPTED)
            return "NOTE", f"accepted file-level copyleft ({', '.join(noted)}); recorded in NOTICE"

    return "REVIEW", "not on the accepted list; requires a human decision"


def installed_runtime_distributions() -> list[metadata.Distribution]:
    seen: dict[str, metadata.Distribution] = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name")
        if not name or name.lower() in NOT_SHIPPED:
            continue
        seen.setdefault(name.lower(), dist)
    return [seen[key] for key in sorted(seen)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--notice",
        action="store_true",
        help="emit the dependency block for NOTICE instead of the check report",
    )
    args = parser.parse_args(argv)

    distributions = installed_runtime_distributions()
    if not distributions:
        print("error: no runtime distributions found in this environment", file=sys.stderr)
        return 2

    rows = []
    for dist in distributions:
        name = dist.metadata["Name"]
        licence, source = licence_of(dist)
        status, reason = verdict(licence)
        rows.append((name, dist.version, licence, source, status, reason))

    if args.notice:
        width = max(len(f"{name} {version}") for name, version, *_ in rows)
        for name, version, licence, _, _, _ in rows:
            print(f"  {f'{name} {version}'.ljust(width)}   {licence}")
        return 0

    name_width = max(len(row[0]) for row in rows)
    print(f"Runtime dependency licences ({len(rows)} packages)")
    print("=" * 78)
    for name, version, licence, source, status, _ in rows:
        flag = {"OK": "  ok  ", "NOTE": " note ", "REVIEW": "REVIEW", "FAIL": " FAIL "}[status]
        print(f"[{flag}] {name.ljust(name_width)}  {version:<12} {licence:<34.34} ({source})")

    failures = [row for row in rows if row[4] == "FAIL"]
    reviews = [row for row in rows if row[4] == "REVIEW"]
    notes = [row for row in rows if row[4] == "NOTE"]

    print("=" * 78)
    print(
        f"permissive: {len(rows) - len(failures) - len(reviews) - len(notes)}   "
        f"accepted with note: {len(notes)}   "
        f"needs review: {len(reviews)}   "
        f"incompatible or unknown: {len(failures)}"
    )

    for name, _, licence, _, _, reason in notes:
        print(f"  note    {name}: {licence} - {reason}")
    for name, _, licence, _, _, reason in reviews:
        print(f"  REVIEW  {name}: {licence} - {reason}")
    for name, _, licence, _, _, reason in failures:
        print(f"  FAIL    {name}: {licence} - {reason}")

    if failures or reviews:
        print("\nGATE-LIC FAILED - resolve every item above before release.")
        return 1

    print("\nGATE-LIC PASSED - every runtime dependency is compatible with Apache-2.0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
