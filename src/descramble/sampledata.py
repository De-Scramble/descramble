# SPDX-License-Identifier: Apache-2.0
"""Synthetic record generation.

A demonstration of record linkage is worthless without data that actually
contains duplicates, and using real personal data to show off a deduplication
tool would be indefensible. So the sample dataset is invented from scratch:
every person here is fictional, and every email address uses a domain reserved
by RFC 2606 for documentation, which cannot resolve to a real service.

The point of the generator is the *duplicates*. Records describing the same
person are emitted more than once with the kinds of damage real data actually
suffers — inconsistent capitalisation, transposed letters, dropped characters,
familiar forms of a given name, a changed postcode after a move, a missing
city. Exact-match deduplication misses all of it, which is the argument for
probabilistic linkage in a single, visible example.

Generation is fully seeded: the same seed yields byte-identical output.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from pathlib import Path

from descramble.config import RECORD_COLUMNS

FIRST_NAMES = (
    "Alice", "Benjamin", "Catherine", "Daniel", "Eleanor", "Francis", "Grace",
    "Harold", "Isabel", "Jonathan", "Katherine", "Laurence", "Margaret",
    "Nathaniel", "Olivia", "Patrick", "Quentin", "Rosalind", "Samuel",
    "Theodora", "Ulysses", "Victoria", "William", "Ximena", "Yolanda",
    "Zachary", "Amelia", "Bartholomew", "Clara", "Dominic", "Evelyn",
    "Frederick", "Gwendolyn", "Hugo", "Imogen", "Julius", "Kirsten",
    "Leonard", "Miriam", "Nicholas", "Ophelia", "Percival", "Rebecca",
    "Sebastian", "Tabitha", "Vincent", "Winifred", "Adelaide", "Alistair",
    "Anneliese", "Archibald", "Augustine", "Beatrix", "Cordelia", "Cornelius",
    "Delphine", "Desmond", "Edmund", "Emmeline", "Esther", "Ezekiel",
    "Felicity", "Fergus", "Genevieve", "Gideon", "Griselda", "Hattie",
    "Horatio", "Ignatius", "Ingrid", "Jasper", "Josephine", "Juniper",
    "Lachlan", "Lavinia", "Lysander", "Mabel", "Magnus", "Marguerite",
    "Matilda", "Maximilian", "Meredith", "Montgomery", "Mortimer", "Nadia",
    "Octavia", "Orlando", "Oswald", "Penelope", "Peregrine", "Phoebe",
    "Reginald", "Rowena", "Rupert", "Seraphina", "Sylvester", "Tamsin",
    "Thaddeus", "Ursula", "Valentina", "Verity", "Wilhelmina", "Wyatt",
    "Xanthe", "Yseult", "Zebedee", "Zora", "Barnaby", "Clementine",
    "Dorothea", "Elspeth", "Giles", "Honoria", "Isadora", "Jerome",
    "Lucasta", "Marcus", "Niamh", "Perpetua",
)

LAST_NAMES = (
    "Ashworth", "Blackwood", "Carmichael", "Donnelly", "Ellsworth",
    "Fairbanks", "Grimshaw", "Hollingsworth", "Ingram", "Jennings",
    "Kingsley", "Lockhart", "Mortimer", "Nightingale", "Ollerenshaw",
    "Pemberton", "Quarrington", "Ravenscroft", "Sinclair", "Thackeray",
    "Underhill", "Vanbrugh", "Wetherby", "Yarborough", "Ziegler",
    "Abernathy", "Bramwell", "Chadwick", "Dunmore", "Everleigh",
    "Fotheringay", "Galbraith", "Harcourt", "Inchbald", "Jardine",
    "Kettering", "Lamperton", "Marchbanks", "Netherfield", "Oakhurst",
    "Padgett", "Quillon", "Rutherglen", "Stanhope", "Trelawney",
    "Ufford", "Vexley", "Wolstenholme", "Yeardley", "Zephyrus",
    "Ainsworth", "Balfour", "Cavendish", "Drummond", "Eastleigh",
    "Fenchurch", "Greenhalgh", "Haverford", "Illingworth", "Jessop",
    "Kirkbride", "Loxley", "Merriweather", "Norrington", "Ormsby",
    "Prescott", "Quimby", "Rosewarne", "Sedgwick", "Tremaine",
    "Ullathorne", "Verity", "Wainwright", "Yelverton", "Zouche",
    "Applegarth", "Braithwaite", "Cholmondeley", "Deverell", "Elphinstone",
    "Farquharson", "Gillingham", "Hawksmoor", "Ivory", "Jerningham",
    "Kenworthy", "Langridge", "Mainwaring", "Norbury", "Ottaway",
    "Pargeter", "Quenington", "Rackham", "Somerville", "Tattersall",
    "Uppingham", "Voysey", "Wilberforce", "Yardley", "Zennor",
    "Alderton", "Beaumont", "Culpepper", "Danvers", "Emberly",
    "Fitzwilliam", "Goldsworthy", "Hepplewhite", "Ilchester", "Jocelyn",
    "Kingscote", "Lyttleton", "Mowbray", "Nunnerley", "Osgood",
    "Ponsonby", "Radcliffe", "Standish", "Thorncroft", "Umberton",
)

CITIES = (
    "Ashford", "Brightwater", "Cedarhill", "Draysbourne", "Eastmarch",
    "Fenwick", "Glassmere", "Harrowgate", "Inverleith", "Kestrelby",
    "Langmoor", "Mordenhall", "Northwold", "Oakhaven", "Pinecross",
)

#: Familiar forms of a given name. A human reads "Katherine" and "Kate" as the
#: same person instantly; exact matching does not, and neither does a naive
#: edit-distance threshold, since the two strings are far apart. This is one of
#: the clearest illustrations of why the comparison model needs to be
#: probabilistic rather than a single rule.
FAMILIAR_FORMS = {
    "Benjamin": "Ben",
    "Catherine": "Cathy",
    "Daniel": "Dan",
    "Eleanor": "Ellie",
    "Jonathan": "Jon",
    "Katherine": "Kate",
    "Margaret": "Maggie",
    "Nathaniel": "Nate",
    "Patrick": "Pat",
    "Rosalind": "Roz",
    "Samuel": "Sam",
    "Theodora": "Thea",
    "Victoria": "Vicky",
    "William": "Will",
    "Rebecca": "Becky",
    "Sebastian": "Seb",
    "Nicholas": "Nick",
    "Frederick": "Fred",
}

# RFC 2606 reserves these for documentation and examples. They are guaranteed
# never to belong to anyone.
EMAIL_DOMAINS = ("example.com", "example.net", "example.org")


@dataclass
class GenerationSummary:
    """What the generator actually produced, for reporting and for tests."""

    total_rows: int = 0
    distinct_people: int = 0
    people_with_duplicates: int = 0
    duplicate_rows: int = 0
    variations_applied: dict[str, int] = field(default_factory=dict)

    #: Ground truth: record identifier to the identifier of the *first* record
    #: describing that person. Records sharing a value here describe the same
    #: person and should end up in the same cluster.
    #:
    #: This is deliberately not written into the sample CSV. Handing the answer
    #: to the pipeline as an input column would make the demonstration
    #: circular; keeping it beside the data lets tests measure how well the
    #: linkage actually did.
    truth: dict[str, str] = field(default_factory=dict)

    @property
    def expected_golden_records(self) -> int:
        """Golden-record count a perfect resolver would produce."""
        return self.distinct_people


def _transpose(rng: random.Random, text: str) -> str:
    """Swap two adjacent characters — the classic typing slip."""
    if len(text) < 3:
        return text
    i = rng.randrange(1, len(text) - 1)
    return text[:i] + text[i + 1] + text[i] + text[i + 1 + 1 :]


def _drop_character(rng: random.Random, text: str) -> str:
    if len(text) < 3:
        return text
    i = rng.randrange(1, len(text))
    return text[:i] + text[i + 1 :]


def _double_character(rng: random.Random, text: str) -> str:
    if len(text) < 2:
        return text
    i = rng.randrange(1, len(text))
    return text[:i] + text[i] + text[i:]


def _make_postcode(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXY") for _ in range(2))
    return f"{letters}{rng.randrange(10, 99)} {rng.randrange(1, 9)}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}"


def _typo_postcode(rng: random.Random, postcode: str) -> str:
    """Alter one character — a *mistyped* postcode, not a different address.

    Distinct from a genuine move: this stays one edit away from the original,
    which is exactly the near-miss the comparison model grades between "same"
    and "different".
    """
    characters = list(postcode)
    positions = [i for i, c in enumerate(characters) if c != " "]
    if not positions:
        return postcode
    i = rng.choice(positions)
    if characters[i].isdigit():
        characters[i] = rng.choice([d for d in "0123456789" if d != characters[i]])
    else:
        characters[i] = rng.choice([c for c in "ABCDEFGHJKLMNPRSTUVWXY" if c != characters[i]])
    return "".join(characters)


def _typo_email_local_part(rng: random.Random, email: str) -> str:
    """Damage the local part, leaving the domain intact.

    The two halves of an address carry very different amounts of identifying
    information — thousands of people share a domain, almost nobody shares a
    local part — so damaging only the left side is both realistic and the case
    the comparison model treats separately.
    """
    local, at, domain = email.partition("@")
    if not at or len(local) < 3:
        return email
    damaged = rng.choice((_transpose, _drop_character, _double_character))(rng, local)
    return f"{damaged}@{domain}"


def _make_email(rng: random.Random, first: str, last: str) -> str:
    style = rng.randrange(4)
    first_l, last_l = first.lower(), last.lower()
    if style == 0:
        local = f"{first_l}.{last_l}"
    elif style == 1:
        local = f"{first_l[0]}{last_l}"
    elif style == 2:
        local = f"{first_l}{rng.randrange(1, 99)}"
    else:
        local = f"{first_l}_{last_l}"
    return f"{local}@{rng.choice(EMAIL_DOMAINS)}"


def _vary(rng: random.Random, person: dict[str, str], tally: dict[str, int]) -> dict[str, str]:
    """Produce one damaged copy of a person's record.

    At least one variation is always applied — a duplicate identical to its
    original would prove nothing about the matching.
    """
    copy = dict(person)
    applied = 0

    def mark(name: str) -> None:
        nonlocal applied
        tally[name] = tally.get(name, 0) + 1
        applied += 1

    if rng.random() < 0.55:
        copy["email"] = copy["email"].upper() if rng.random() < 0.5 else copy["email"].title()
        mark("email_case")

    if rng.random() < 0.18:
        copy["email"] = _typo_email_local_part(rng, copy["email"])
        mark("email_typo")

    if rng.random() < 0.40:
        familiar = FAMILIAR_FORMS.get(copy["first_name"])
        if familiar:
            copy["first_name"] = familiar
            mark("familiar_given_name")

    if rng.random() < 0.45:
        damage = rng.choice((_transpose, _drop_character, _double_character))
        copy["last_name"] = damage(rng, copy["last_name"])
        mark("surname_typo")

    if rng.random() < 0.30:
        copy["first_name"] = _transpose(rng, copy["first_name"])
        mark("given_name_typo")

    # A mistyped postcode and a genuine change of address look different in the
    # data and should be scored differently, so the generator produces both.
    if rng.random() < 0.20:
        copy["postcode"] = _typo_postcode(rng, copy["postcode"])
        mark("postcode_typo")
    elif rng.random() < 0.18:
        copy["postcode"] = _make_postcode(rng)
        copy["city"] = rng.choice([c for c in CITIES if c != copy["city"]])
        mark("moved_address")

    if rng.random() < 0.15:
        copy["city"] = ""
        mark("missing_city")

    if applied == 0:
        copy["email"] = copy["email"].upper()
        mark("email_case")

    return copy


def generate_records(
    people: int = 2000,
    duplicate_rate: float = 0.30,
    seed: int = 1729,
    max_duplicates_per_person: int = 3,
) -> tuple[list[dict[str, str]], GenerationSummary]:
    """Generate synthetic records containing known duplicates.

    Args:
        people: number of distinct fictional people to invent.
        duplicate_rate: fraction of them that appear more than once.
        seed: fixes the output; the same seed always produces the same rows.
        max_duplicates_per_person: upper bound on extra copies of one person.

    Returns:
        The rows, and a summary describing what was generated. The summary's
        ``expected_golden_records`` is ground truth: a perfect resolver would
        collapse the rows to exactly that many.
    """
    if people < 1:
        raise ValueError("people must be at least 1")
    if not 0.0 <= duplicate_rate <= 1.0:
        raise ValueError("duplicate_rate must be between 0 and 1")

    name_space = len(FIRST_NAMES) * len(LAST_NAMES)
    if people > name_space:
        raise ValueError(
            f"cannot invent {people} distinctly-named people from {name_space} "
            f"available name combinations"
        )

    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    summary = GenerationSummary(distinct_people=people)
    tally: dict[str, int] = {}
    counter = 0
    used_names: set[tuple[str, str]] = set()

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"r{counter:07d}"

    for _ in range(people):
        # Distinct people are given distinct full names. Two unrelated people
        # who genuinely share a name are a real phenomenon, but in a dataset
        # with published ground truth they are a different problem wearing the
        # same clothes: the ground truth says "different" while the record
        # offers nothing but the other fields to tell them apart. Keeping names
        # unique here means a merge of two people is unambiguously a matching
        # error and the reported accuracy means what it says.
        while True:
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break

        person = {
            "record_id": next_id(),
            "first_name": first,
            "last_name": last,
            "email": _make_email(rng, first, last),
            "postcode": _make_postcode(rng),
            "city": rng.choice(CITIES),
        }
        rows.append(person)
        summary.truth[person["record_id"]] = person["record_id"]

        if rng.random() < duplicate_rate:
            summary.people_with_duplicates += 1
            for _ in range(rng.randint(1, max_duplicates_per_person)):
                duplicate = _vary(rng, person, tally)
                duplicate["record_id"] = next_id()
                rows.append(duplicate)
                summary.truth[duplicate["record_id"]] = person["record_id"]
                summary.duplicate_rows += 1

    summary.total_rows = len(rows)
    summary.variations_applied = dict(sorted(tally.items()))
    return rows, summary


def write_csv(rows: list[dict[str, str]], destination: Path) -> Path:
    """Write rows to CSV with a stable column order and Unix line endings."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(RECORD_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return destination
