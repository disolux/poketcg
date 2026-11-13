import os
import time
import requests

API_URL = "https://api.pokemontcg.io/v2/cards"
SETS_URL = "https://api.pokemontcg.io/v2/sets"
RARITIES_URL = "https://api.pokemontcg.io/v2/rarities"
SUBTYPES_URL = "https://api.pokemontcg.io/v2/subtypes"
NAMES_URL = "https://pokeapi.co/api/v2/pokemon-species"
API_KEY = ""
TIMEOUT = 30
PAGE_SIZE = 50
TRIES = 3
WAIT_SECONDS = 2
BUSY_CODES = (502, 503, 504)
SEARCH_ORDER = "-set.releaseDate"
BROWSE_ORDER = "-set.releaseDate,name"
CARD_FIELDS = "id,name,supertype,subtypes,types,hp,rarity,number,set,artist,images"
BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
IMAGE_FOLDER = os.path.join(BASE_FOLDER, "images")


def make_card(item):
    set_info = item.get("set") or {}
    images = item.get("images") or {}
    hp = str(item.get("hp", ""))
    return {
        "id": item.get("id") or "",
        "name": item.get("name") or "",
        "supertype": item.get("supertype") or "",
        "subtypes": item.get("subtypes") or [],
        "types": item.get("types") or [],
        "hp": int(hp) if hp.isdigit() else 0,
        "rarity": item.get("rarity") or "",
        "number": item.get("number") or "",
        "set": set_info.get("name") or "",
        "series": set_info.get("series") or "",
        "release_date": (set_info.get("releaseDate") or "").replace("/", "-"),
        "artist": item.get("artist") or "",
        "image_url": images.get("small") or "",
        "image_large_url": images.get("large") or "",
    }


def build_name_query(name):
    pieces = []
    for word in name.replace('"', " ").split():
        if word.isalnum():
            pieces.append("name:" + word + "*")
        else:
            pieces.append('name:"' + word + '"')
    return " ".join(pieces)


def http_error_text(code):
    if code == 0:
        return "The card server returned an error. Please try again later."
    if code == 429:
        return "Too many searches in a short time. Please wait a minute and try again."
    if code == 400:
        return "The card server did not accept that search. Try a simpler search."
    if code >= 500:
        return ("The card server is having problems right now (error " + str(code) +
                "). Please try again in a moment.")
    return "The card server returned an error (code " + str(code) + "). Please try again later."


def ask_once(url, params, headers, timeout):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json(), None, False
    except requests.exceptions.Timeout:
        return None, "The card server took too long to answer. Please try again in a moment.", True
    except requests.exceptions.ConnectionError:
        return None, "Could not reach the card server. Check your internet connection.", False
    except requests.exceptions.HTTPError as error:
        code = 0
        if error.response is not None:
            code = error.response.status_code
        return None, http_error_text(code), code in BUSY_CODES
    except ValueError:
        return None, "The card server sent a reply that could not be read.", False
    except requests.exceptions.RequestException:
        return None, "Something went wrong while searching. Please try again.", False


def get_json(url, params, show_status=None, tries=None, timeout=None):
    if tries is None:
        tries = TRIES
    if timeout is None:
        timeout = TIMEOUT
    headers = {}
    if API_KEY and url.startswith("https://api.pokemontcg.io"):
        headers["X-Api-Key"] = API_KEY

    for attempt in range(1, tries + 1):
        data, error, worth_retrying = ask_once(url, params, headers, timeout)
        if error is None or not worth_retrying or attempt == tries:
            break
        if show_status:
            show_status("The server is busy, trying again (" + str(attempt + 1) + " of " + str(tries) + ")...")
        time.sleep(WAIT_SECONDS)

    if error is not None:
        if attempt > 1:
            error = error + " (The program tried " + str(attempt) + " times.)"
        return None, error
    if not isinstance(data, dict):
        return None, "The card server sent a reply that could not be read."
    return data, None


def fetch_cards(query, page=1, show_status=None, order=SEARCH_ORDER):
    params = {
        "q": query,
        "page": page,
        "pageSize": PAGE_SIZE,
        "orderBy": order,
        "select": CARD_FIELDS,
    }
    data, error = get_json(API_URL, params, show_status)
    if error is not None:
        return [], 0, error

    items = data.get("data")
    if not isinstance(items, list):
        items = []
    cards = []
    for item in items:
        if isinstance(item, dict):
            cards.append(make_card(item))
    total = data.get("totalCount")
    if not isinstance(total, int):
        total = len(cards)
    return cards, total, None


def search_cards(name, show_status=None):
    cards, total, error = fetch_cards(build_name_query(name), 1, show_status)
    return cards, error


def fetch_sets(show_status=None):
    sets = []
    page = 1
    while page <= 5:
        params = {"page": page, "pageSize": 250, "orderBy": "-releaseDate",
                  "select": "id,name,series,total,releaseDate"}
        data, error = get_json(SETS_URL, params, show_status)
        if error is not None:
            return [], error
        items = data.get("data")
        if not isinstance(items, list):
            items = []
        for item in items:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                total = item.get("total")
                sets.append({
                    "id": item["id"],
                    "name": item["name"],
                    "series": item.get("series") or "",
                    "total": total if isinstance(total, int) else 0,
                    "release_date": (item.get("releaseDate") or "").replace("/", "-"),
                })
        count = data.get("totalCount")
        if len(items) == 0 or not isinstance(count, int) or len(sets) >= count:
            break
        page += 1
    return sets, None


def fetch_name_list(url, show_status=None):
    data, error = get_json(url, {}, show_status)
    if error is not None:
        return [], error
    items = data.get("data")
    if not isinstance(items, list):
        return [], "The card server sent a reply that could not be read."
    names = []
    for item in items:
        if isinstance(item, str) and item != "":
            names.append(item)
    return names, None


def fetch_pokemon_names():
    data, error = get_json(NAMES_URL, {"limit": 2000}, None, tries=1, timeout=8)
    if error is not None:
        return [], error
    items = data.get("results")
    if not isinstance(items, list):
        return [], "The list of names could not be read."
    names = []
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]).replace("-", " ").title())
    return names, None


def download(url, path):
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        with open(path, "wb") as file:
            file.write(response.content)
    except (requests.exceptions.RequestException, OSError):
        return False
    return True


def get_image(card):
    if not card.get("image_url") or not card.get("id"):
        return None

    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    path = os.path.join(IMAGE_FOLDER, card["id"] + ".png")
    if os.path.exists(path):
        return path
    if download(card["image_url"], path):
        return path
    return None


def get_large_image(card):
    url = card.get("image_large_url") or ""
    small = card.get("image_url") or ""
    if url == "" and small.endswith(".png"):
        url = small[:-4] + "_hires.png"
    if url == "" or not card.get("id"):
        return None

    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    path = os.path.join(IMAGE_FOLDER, card["id"] + "_large.png")
    if os.path.exists(path):
        return path
    if download(url, path):
        return path
    return None
