import unicodedata

MAX_TEXT_LENGTH = 60
MAX_NUMBER = 9999
DIGITS = "0123456789"
NAME_SYMBOLS = "'’-.:&!,#♀♂"
LIST_SYMBOLS = NAME_SYMBOLS + "()[]–—"


def clean_spaces(text):
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.split())


def shorten(text, limit=20):
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def find_bad_characters(text, allowed_symbols):
    found = []
    for character in text:
        if character == " " or character in DIGITS or character in allowed_symbols or character.isalpha():
            continue
        if character not in found:
            found.append(character)
    return found


def describe_characters(characters):
    visible = []
    for character in characters:
        if character.isprintable():
            visible.append(character)
    text = " ".join(visible[:6])
    if len(visible) > 6:
        text = text + " ..."
    if len(visible) < len(characters):
        if text != "":
            text = text + " and "
        text = text + "invisible characters"
    return text


def is_digits(text):
    if text == "":
        return False
    for character in text:
        if character not in DIGITS:
            return False
    return True


def is_decimal_like(text):
    if text == "" or not ("." in text or "," in text):
        return False
    has_digit = False
    for character in text:
        if character in DIGITS:
            has_digit = True
        elif character not in ".,":
            return False
    return has_digit


def check_words(text, subject, allowed_symbols, empty_hint, spaces_hint, empty_allowed=False):
    if text == "":
        if empty_allowed:
            return "", ""
        return "", subject + " is empty. " + empty_hint

    cleaned = clean_spaces(text)
    if cleaned == "":
        return "", subject + " only contains spaces. " + spaces_hint
    if len(cleaned) > MAX_TEXT_LENGTH:
        return "", (subject + " is too long (" + str(len(cleaned)) + " characters). Use "
                    + str(MAX_TEXT_LENGTH) + " or fewer.")

    bad = find_bad_characters(cleaned, allowed_symbols)
    if len(bad) > 0:
        return "", (subject + " cannot contain: " + describe_characters(bad)
                    + ". Use only letters, numbers, spaces and these symbols: " + " ".join(allowed_symbols))
    return cleaned, ""


def check_card_name(text):
    cleaned, error = check_words(
        text, "The card name", NAME_SYMBOLS,
        empty_hint="Type a card name, for example: Pikachu.",
        spaces_hint="Type at least one letter.")
    if error != "":
        return "", error
    for character in cleaned:
        if character.isalpha():
            return cleaned, ""
    return "", ('The card name "' + shorten(cleaned) + '" has no letters. '
                "A card name needs at least one letter, for example: Pikachu.")


def check_name_filter(text):
    return check_words(
        text, 'The "Name contains" box', NAME_SYMBOLS,
        empty_hint="",
        spaces_hint="Type part of a card name, or clear the box.",
        empty_allowed=True)


def check_tag_kind(kind):
    if kind == "":
        return "Pick a kind of tag first (Set, Type, Rarity ...)."
    return ""


def check_tag_value(text, kind, typeable):
    if not typeable:
        cleaned = clean_spaces(text)
        if cleaned == "":
            return "", 'Pick a value for the "' + kind + '" tag from the dropdown list.'
        return cleaned, ""
    return check_words(
        text, "The value box", LIST_SYMBOLS,
        empty_hint="Type or pick a value for the " + kind + " tag.",
        spaces_hint="Type part of a " + kind.lower() + " name, or pick one from the list.")


def check_whole_number(text, label, example):
    if text == "":
        return None, ""
    name = '"' + label + '"'
    stripped = text.strip()
    if stripped == "":
        return None, name + " only contains spaces. Type a whole number such as " + str(example) + ", or clear the box."

    shown = '"' + shorten(stripped) + '"'
    negative = stripped.startswith("-")
    body = stripped[1:] if negative else stripped

    if is_digits(body) or is_decimal_like(body):
        if negative:
            return None, name + ": " + shown + " cannot be negative. Use 0 or more."
        if is_decimal_like(body):
            return None, (name + ": " + shown + " must be a whole number, with no decimal point or comma. "
                          "For example: " + str(example))
        digits = body.lstrip("0")
        if len(digits) > len(str(MAX_NUMBER)) or (digits != "" and int(digits) > MAX_NUMBER):
            return None, name + ": " + shown + " is too big. The highest number allowed is " + str(MAX_NUMBER) + "."
        if digits == "":
            return 0, ""
        return int(digits), ""

    without_spaces = "".join(stripped.split())
    if len(stripped.split()) > 1 and is_digits(without_spaces):
        return None, (name + ": " + shown + " has spaces between the digits. "
                      "Type it without spaces, for example: " + str(example))
    return None, name + ": " + shown + " is not a number. Use digits only, for example: " + str(example)


def check_number_range(low, high, low_label, high_label):
    if low is not None and high is not None and low > high:
        return ('"' + low_label + '" (' + str(low) + ') is bigger than "' + high_label + '" (' + str(high)
                + "), so no card can match. Change one of them.")
    return ""


def check_number_pair(low_text, high_text, low_label, high_label, example):
    errors = []
    low, error = check_whole_number(low_text, low_label, example)
    if error != "":
        errors.append(error)
    high, error = check_whole_number(high_text, high_label, example)
    if error != "":
        errors.append(error)
    error = check_number_range(low, high, low_label, high_label)
    if error != "":
        errors.append(error)
        low = None
        high = None
    return low, high, errors
