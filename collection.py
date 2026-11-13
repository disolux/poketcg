import json
import os
from datetime import date, datetime

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
COLLECTION_FILE = os.path.join(BASE_FOLDER, "collection.json")
UNREADABLE_FILE = os.path.join(BASE_FOLDER, "collection_unreadable.json")
HISTORY_FILE = os.path.join(BASE_FOLDER, "history.txt")

CONDITIONS = ("Mint", "Near Mint", "Played")
SORT_OPTIONS = ("Name", "Set", "Card number", "Release date", "Rarity",
                "HP", "Type", "Quantity", "Condition", "Date added")
ORDERS = ("Ascending", "Descending")

BOX_FIELDS = (
    ("supertype", "supertype"),
    ("type", "types"),
    ("subtype", "subtypes"),
    ("rarity", "rarity"),
    ("set", "set"),
    ("series", "series"),
    ("artist", "artist"),
    ("condition", "condition"),
)
NUMBER_FILTERS = ("hp_min", "hp_max", "qty_min", "qty_max")


def empty_card():
    return {
        "id": "", "name": "", "supertype": "", "subtypes": [], "types": [],
        "hp": 0, "rarity": "", "number": "", "set": "", "series": "",
        "release_date": "", "artist": "", "image_url": "", "image_large_url": "",
        "condition": "Near Mint", "quantity": 1, "date_added": "",
    }


def fix_entry(item):
    if not isinstance(item, dict):
        return None
    card = empty_card()
    for key in card:
        if key in item and isinstance(item[key], type(card[key])):
            card[key] = item[key]
    if card["id"] == "" or card["name"] == "":
        return None
    card["quantity"] = max(1, card["quantity"])
    return card


def keep_unreadable_file():
    try:
        os.replace(COLLECTION_FILE, UNREADABLE_FILE)
        return ("The saved collection could not be read, so you are starting with an empty "
                "one. The old file was kept as collection_unreadable.json.")
    except OSError:
        return "The saved collection could not be read, so you are starting with an empty one."


def load_collection():
    if not os.path.exists(COLLECTION_FILE):
        return [], None
    try:
        with open(COLLECTION_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return [], keep_unreadable_file()
    if not isinstance(data, list):
        return [], keep_unreadable_file()

    cards = []
    for item in data:
        card = fix_entry(item)
        if card is not None:
            cards.append(card)
    warning = None
    if len(cards) < len(data):
        warning = str(len(data) - len(cards)) + " damaged entries in the saved file were skipped."
    return cards, warning


def save_collection(cards):
    temp_file = COLLECTION_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(cards, file, indent=2, ensure_ascii=False)
        os.replace(temp_file, COLLECTION_FILE)
    except OSError as error:
        return "Could not save the collection: " + str(error)
    return None


def write_history(action, card):
    line = "{} | {} | {} ({}) | {}\n".format(
        datetime.now().strftime("%Y-%m-%d %H:%M"), action,
        card["name"], card["id"], card["condition"])
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as file:
            file.write(line)
    except OSError:
        pass


def find_entry(cards, card_id, condition):
    for entry in cards:
        if entry["id"] == card_id and entry["condition"] == condition:
            return entry
    return None


def add_card(cards, card, condition):
    if condition not in CONDITIONS:
        return "Please choose a condition first."

    entry = find_entry(cards, card["id"], condition)
    if entry is not None:
        entry["quantity"] += 1
        message = "{} ({}) was already in your collection. Quantity is now {}.".format(
            entry["name"], condition, entry["quantity"])
    else:
        entry = dict(card)
        entry["condition"] = condition
        entry["quantity"] = 1
        entry["date_added"] = date.today().isoformat()
        cards.append(entry)
        message = "Added {} ({}) to your collection.".format(entry["name"], condition)

    write_history("ADDED", entry)
    problem = save_collection(cards)
    if problem:
        message = message + " " + problem
    return message


def remove_card(cards, entry):
    entry["quantity"] -= 1
    if entry["quantity"] <= 0:
        cards.remove(entry)
        message = "Removed {} ({}) from your collection.".format(entry["name"], entry["condition"])
    else:
        message = "Removed one copy of {} ({}). {} left.".format(
            entry["name"], entry["condition"], entry["quantity"])

    write_history("REMOVED", entry)
    problem = save_collection(cards)
    if problem:
        message = message + " " + problem
    return message


def number_key(number):
    digits = ""
    for character in number:
        if character.isdigit():
            digits = digits + character
    if digits == "":
        return (0, number)
    return (int(digits), number)


def sort_key(card, option):
    if option == "Name":
        return card["name"].lower()
    if option == "Set":
        return card["set"].lower()
    if option == "Card number":
        return number_key(card["number"])
    if option == "Release date":
        return card["release_date"]
    if option == "Rarity":
        return card["rarity"].lower()
    if option == "HP":
        return card["hp"]
    if option == "Type":
        return ", ".join(card["types"]).lower()
    if option == "Quantity":
        return card["quantity"]
    if option == "Condition":
        return card["condition"]
    if option == "Date added":
        return card["date_added"]
    return card["name"].lower()


def sort_cards(cards, option, order):
    result = sorted(cards, key=lambda card: card["name"].lower())
    result.sort(key=lambda card: sort_key(card, option), reverse=(order == "Descending"))
    return result


def empty_filters():
    filters = {"name": "", "year": ""}
    for key, field in BOX_FIELDS:
        filters[key] = ""
    for key in NUMBER_FILTERS:
        filters[key] = None
    return filters


def in_range(number, lowest, highest):
    if lowest is not None and number < lowest:
        return False
    if highest is not None and number > highest:
        return False
    return True


def check_results(card, filters):
    results = []
    if filters["name"] != "":
        results.append(filters["name"].lower() in card["name"].lower())

    for key, field in BOX_FIELDS:
        wanted = filters[key]
        if wanted == "":
            continue
        value = card[field]
        if isinstance(value, list):
            results.append(wanted in value)
        else:
            results.append(value == wanted)

    if filters["year"] != "":
        results.append(card["release_date"][:4] == filters["year"])
    if filters["hp_min"] is not None or filters["hp_max"] is not None:
        results.append(in_range(card["hp"], filters["hp_min"], filters["hp_max"]))
    if filters["qty_min"] is not None or filters["qty_max"] is not None:
        results.append(in_range(card["quantity"], filters["qty_min"], filters["qty_max"]))
    return results


def card_matches(card, filters, mode="ALL"):
    results = check_results(card, filters)
    if len(results) == 0:
        return True
    if mode == "ANY":
        return any(results)
    return all(results)


def filter_cards(cards, filters, mode="ALL"):
    result = []
    for card in cards:
        if card_matches(card, filters, mode):
            result.append(card)
    return result


def get_choices(cards, key):
    if key == "condition":
        return CONDITIONS
    field = dict(BOX_FIELDS).get(key)
    values = set()
    for card in cards:
        if key == "year":
            value = card["release_date"][:4]
        else:
            value = card[field]
        if isinstance(value, list):
            values.update(value)
        elif value != "":
            values.add(value)
    return tuple(sorted(values, key=str.lower))


def total_copies(cards):
    total = 0
    for card in cards:
        total = total + card["quantity"]
    return total


def count_text(shown, everything):
    return "Showing {} of {} cards ({} of {} copies)".format(
        len(shown), len(everything), total_copies(shown), total_copies(everything))
