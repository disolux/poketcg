import json
import os
import time
from datetime import date

import api

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
LISTS_FILE = os.path.join(BASE_FOLDER, "lists.json")
MAX_AGE_SECONDS = 14 * 24 * 60 * 60

KINDS = ("Set", "Series", "Type", "Supertype", "Subtype", "Rarity",
         "Release year", "Released from year", "Released until year")
MODES = ("ALL", "ANY")
TYPEABLE_KINDS = ("Set", "Series", "Rarity", "Subtype")

TYPES = ("Colorless", "Darkness", "Dragon", "Fairy", "Fighting", "Fire",
         "Grass", "Lightning", "Metal", "Psychic", "Water")
SUPERTYPES = ("Energy", "Pokémon", "Trainer")

FALLBACK_RARITIES = ("Common", "Uncommon", "Rare", "Rare Holo", "Rare Holo EX", "Rare Holo GX",
                     "Rare Holo V", "Rare Holo VMAX", "Rare Ultra", "Rare Secret", "Rare Rainbow",
                     "Amazing Rare", "Double Rare", "Illustration Rare",
                     "Special Illustration Rare", "Ultra Rare", "Hyper Rare", "Promo")
FALLBACK_SUBTYPES = ("Basic", "Stage 1", "Stage 2", "BREAK", "EX", "ex", "GX", "V", "VMAX",
                     "VSTAR", "Item", "Supporter", "Stadium", "Pokémon Tool", "Special")


def tag_query(kind, value):
    value = value.replace('"', "")
    if kind == "Set":
        return 'set.id:"' + value + '"'
    if kind == "Series":
        return 'set.series:"' + value + '"'
    if kind == "Type":
        return 'types:"' + value + '"'
    if kind == "Supertype":
        return 'supertype:"' + value + '"'
    if kind == "Subtype":
        return '!subtypes:"' + value + '"'
    if kind == "Rarity":
        return '!rarity:"' + value + '"'
    if kind == "Release year":
        return "set.releaseDate:[" + value + "/01/01 TO " + value + "/12/31]"
    if kind == "Released from year":
        return "set.releaseDate:[" + value + "/01/01 TO *]"
    if kind == "Released until year":
        return "set.releaseDate:[* TO " + value + "/12/31]"
    return ""


def build_tag_query(tags, mode):
    pieces = []
    for kind, value, shown in tags:
        pieces.append(tag_query(kind, value))
    if mode == "ANY":
        return " OR ".join(pieces)
    return " ".join(pieces)


def tag_label(tag):
    kind, value, shown = tag
    return kind + ": " + shown


def tag_phrase(tag):
    kind, value, shown = tag
    if kind == "Release year":
        return "released in " + shown
    if kind == "Released from year":
        return "released in " + shown + " or later"
    if kind == "Released until year":
        return "released in " + shown + " or earlier"
    return kind.lower() + " is " + shown


def describe(tags, mode):
    if len(tags) == 0:
        return "No tags yet. Pick a kind and a value, then click Add tag."
    joiner = " AND " if mode == "ALL" else " OR "
    phrases = []
    for tag in tags:
        phrases.append(tag_phrase(tag))
    return "Shows cards where: " + joiner.join(phrases)


def set_choices(sets):
    choices = []
    used = []
    for item in sets:
        text = item["name"]
        if item["release_date"] != "":
            text = text + " (" + item["release_date"][:4] + ")"
        if text in used:
            text = text + " [" + item["id"] + "]"
        used.append(text)
        choices.append((text, item["id"]))
    return choices


def series_choices(sets):
    result = []
    for item in sets:
        if item["series"] != "" and item["series"] not in result:
            result.append(item["series"])
    return tuple(result)


def year_choices(sets):
    years = set()
    for item in sets:
        year = item["release_date"][:4]
        if year.isdigit():
            years.add(year)
    if len(years) == 0:
        for year in range(1996, date.today().year + 1):
            years.add(str(year))
    return tuple(sorted(years, reverse=True))


def narrow(choices, typed):
    typed = typed.strip().lower()
    if typed == "":
        return tuple(choices)
    found = []
    for choice in choices:
        if typed in choice.lower():
            found.append(choice)
    return tuple(found)


def name_part(choice):
    if choice.endswith("]") and " [" in choice:
        choice = choice.rsplit(" [", 1)[0]
    if choice.endswith(")") and " (" in choice:
        return choice.rsplit(" (", 1)[0]
    return choice


def find_choice(typed, choices):
    typed = typed.strip().lower()
    if typed == "":
        return "", []

    exact = []
    same_name = []
    for choice in choices:
        if choice.lower() == typed:
            exact.append(choice)
        if name_part(choice).lower() == typed:
            same_name.append(choice)
    if len(exact) == 1:
        return exact[0], exact
    if len(same_name) == 1:
        return same_name[0], same_name

    matches = narrow(choices, typed)
    if len(matches) == 1:
        return matches[0], list(matches)
    return "", list(matches)


def read_lists_file():
    try:
        with open(LISTS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("sets"), list) or not isinstance(data.get("rarities"), list) \
            or not isinstance(data.get("subtypes"), list) or not isinstance(data.get("saved"), (int, float)):
        return None
    good_sets = []
    for item in data["sets"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("name"), str):
            good_sets.append({
                "id": item["id"], "name": item["name"],
                "series": item.get("series") if isinstance(item.get("series"), str) else "",
                "total": item.get("total") if isinstance(item.get("total"), int) else 0,
                "release_date": item.get("release_date") if isinstance(item.get("release_date"), str) else "",
            })
    data["sets"] = good_sets
    if len(good_sets) == 0 or len(data["rarities"]) == 0 or len(data["subtypes"]) == 0:
        return None
    return data


def save_lists_file(lists):
    data = dict(lists)
    data["saved"] = time.time()
    try:
        with open(LISTS_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
    except OSError:
        pass


def get_lists(show_status=None, force=False):
    saved = read_lists_file()
    if saved is not None and not force and time.time() - saved["saved"] < MAX_AGE_SECONDS:
        return saved, ""

    lists = {"sets": [], "rarities": list(FALLBACK_RARITIES), "subtypes": list(FALLBACK_SUBTYPES)}
    if saved is not None:
        for key in ("sets", "rarities", "subtypes"):
            if len(saved[key]) > 0:
                lists[key] = saved[key]

    problem = ""
    sets, error = api.fetch_sets(show_status)
    if error is None and len(sets) == 0:
        error = "The card server sent an empty list of sets."
    if error is None:
        lists["sets"] = sets
    else:
        problem = error
    rarities, error = api.fetch_name_list(api.RARITIES_URL, show_status)
    if error is None and len(rarities) == 0:
        error = "The card server sent an empty list of rarities."
    if error is None:
        lists["rarities"] = rarities
    elif problem == "":
        problem = error
    subtypes, error = api.fetch_name_list(api.SUBTYPES_URL, show_status)
    if error is None and len(subtypes) == 0:
        error = "The card server sent an empty list of subtypes."
    if error is None:
        lists["subtypes"] = subtypes
    elif problem == "":
        problem = error

    if problem == "":
        save_lists_file(lists)
        return lists, ""
    note = 'Could not download the newest lists (' + problem + ') Click "Reload lists" to try again.'
    if len(lists["sets"]) == 0:
        note = "The list of sets could not be loaded, so Set, Series and Release tags are limited. " + note
    return lists, note
