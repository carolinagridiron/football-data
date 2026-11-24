"""Resolve editorial school names to verified NCAA slug inventory entries."""
import csv
import re

def key(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower().replace("&", " and ")).strip()

def load_lookup(directory, names):
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
    return mapping

def resolve_name(value, mapping):
    """Return a canonical NCAA slug, or a nonmatching sentinel for unknown names.

    Unknown names never silently turn into guessed NCAA identifiers.
    """
    k=key(value)
    return mapping.get(k, "unresolved:" + k)
