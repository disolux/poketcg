import json
import os

import api

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
RECENT_FILE = os.path.join(BASE_FOLDER, "recent_searches.txt")
NAMES_FILE = os.path.join(BASE_FOLDER, "names.json")
MAX_SUGGESTIONS = 8
MAX_RECENT = 5


def add_recent(text):
    text = " ".join(text.split())
    if text == "":
        return
    try:
        with open(RECENT_FILE, "a", encoding="utf-8") as file:
            file.write(text + "\n")
    except OSError:
        pass


def load_recent():
    try:
        with open(RECENT_FILE, "r", encoding="utf-8") as file:
            lines = file.read().splitlines()
    except (OSError, ValueError):
        return []
    result = []
    seen = set()
    for line in reversed(lines):
        line = line.strip()
        if line != "" and line.lower() not in seen:
            seen.add(line.lower())
            result.append(line)
        if len(result) >= 20:
            break
    return result


def read_names_file():
    try:
        with open(NAMES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    names = []
    for item in data:
        if isinstance(item, str) and item != "":
            names.append(item)
    return names


def load_names():
    names = read_names_file()
    if len(names) > 0:
        return names, None
    names, error = api.fetch_pokemon_names()
    if error is not None:
        return [], error
    try:
        with open(NAMES_FILE, "w", encoding="utf-8") as file:
            json.dump(names, file, ensure_ascii=False)
    except OSError:
        pass
    return names, None


def get_suggestions(text, recent, names):
    typed = text.strip().lower()
    if typed == "":
        return recent[:MAX_RECENT]

    found = []
    found_lower = []

    for item in recent:
        if len(found) >= MAX_RECENT:
            break
        if typed in item.lower() and item.lower() != typed and item.lower() not in found_lower:
            found.append(item)
            found_lower.append(item.lower())

    for name in names:
        if len(found) >= MAX_SUGGESTIONS:
            break
        if name.lower().startswith(typed) and name.lower() != typed and name.lower() not in found_lower:
            found.append(name)
            found_lower.append(name.lower())
    for name in names:
        if len(found) >= MAX_SUGGESTIONS:
            break
        for word in name.lower().split()[1:]:
            if word.startswith(typed) and name.lower() not in found_lower:
                found.append(name)
                found_lower.append(name.lower())
                break
    return found
