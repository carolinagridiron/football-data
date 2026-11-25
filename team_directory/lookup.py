"""Resolve editorial school names to verified NCAA slug inventory entries."""
import csv
import re

def key(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower().replace("&", " and ")).strip()

def load_lookup(directory, names, external=None):
    with open(directory, encoding="utf-8-sig", newline="") as f:
        slugs={r["ncaa_slug"] for r in csv.DictReader(f)}
    mapping={}
    for slug in slugs:
        mapping[key(slug)]=slug
    with open(names, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["ncaa_slug"] not in slugs:
                raise ValueError("Unknown NCAA slug: " + row["ncaa_slug"])
            k=key(row["editorial_name"])
            if k in mapping and mapping[k]!=row["ncaa_slug"]:
                raise ValueError("Conflicting mapping: " + k)
            mapping[k]=row["ncaa_slug"]
    # NCAA scoreboard responses can retain older abbreviations. Normalize both
    # the old and current identifiers to the user-confirmed canonical slug.
    for old, current in {"west-va-st": "west-virginia-st", "lindenwood": "lindenwood-mo"}.items():
        mapping[key(old)] = current
    if external is not None:
        with open(external, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                k = key(row["editorial_name"])
                identity = row["identity"]
                if not identity.startswith("external:"):
                    raise ValueError("External identity must be namespaced: " + identity)
                if k in mapping and mapping[k] != identity:
                    raise ValueError("External name conflicts with NCAA name: " + k)
                mapping[k] = identity
    # Exact NCAA-side spellings for external opponents; these are identities,
    # not NCAA membership slugs. Keep this map explicit and conflict-checked.
    if external is not None:
        for alias, identity in {
            'Bluefield Univ.': 'external:bluefield-university',
            'Bluefield University': 'external:bluefield-university',
            'Monroe': 'external:monroe-university',
            'Monroe University': 'external:monroe-university',
            'VU-Lynchburg': 'external:virginia-lynchburg',
            'Virginia-Lynchburg': 'external:virginia-lynchburg',
        }.items():
            k=key(alias)
            if k in mapping and mapping[k] != identity:
                raise ValueError('External alias conflicts with existing mapping: ' + alias)
            mapping[k]=identity
    return mapping

def resolve_name(value, mapping):
    """Return a canonical NCAA slug, or a nonmatching sentinel for unknown names.

    Unknown names never silently turn into guessed NCAA identifiers.
    """
    k=key(value)
    return mapping.get(k, "unresolved:" + k)
