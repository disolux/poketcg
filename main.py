import os
import tkinter as tk
from tkinter import ttk, messagebox

import api
import browse
import collection
import suggestions
import validation

ERROR_COLOR = "#b00020"

PICTURE_PANEL_WIDTH = 270
PICTURE_INFO_WRAP = 250
WIDE_TEXT_WRAP = 1100
DESCRIPTION_WRAP = 1000
SCREEN_MARGIN = 120
WINDOW_RAISE = 30

SEARCH_BOX_WIDTH = 40
KIND_BOX_WIDTH = 20
VALUE_BOX_WIDTH = 34
CONDITION_BOX_WIDTH = 12
FILTER_BOX_WIDTH = 12
SORT_BOX_WIDTH = 14
ORDER_BOX_WIDTH = 12

LOAD_WARNING_DELAY_MS = 300
LOAD_NAMES_DELAY_MS = 500

NAVIGATION_KEYS = ("Up", "Down", "Return", "Escape", "Tab", "Left", "Right", "Home", "End",
                   "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R")

SEARCH_COLUMNS = (
    ("Name", 170), ("Set", 170), ("No.", 50), ("Rarity", 110),
    ("Type", 90), ("HP", 50), ("Released", 90),
)
COLLECTION_COLUMNS = (
    ("Name", 135), ("Set", 125), ("No.", 50), ("Released", 90), ("Rarity", 95),
    ("Type", 75), ("HP", 45), ("Condition", 85), ("Qty", 40), ("Added", 85),
)
FILTER_DROPDOWNS = (
    ("Supertype", "supertype"), ("Type", "type"), ("Subtype", "subtype"),
    ("Rarity", "rarity"), ("Set", "set"), ("Series", "series"),
    ("Artist", "artist"), ("Condition", "condition"), ("Release year", "year"),
)
SCALES = ((1, 1), (3, 4), (2, 3), (1, 2), (1, 3), (1, 4))
PICTURE_HINT = "Click a card in the table\nto see its picture."

my_cards = []
search_results = []
shown_cards = []

browse_tags = []
browse_results = []
browse_query = ""
browse_page = 1
browse_total = 0
browse_lists = None
set_id_by_text = {}
value_choices = ()

recent_searches = []
pokemon_names = []
large_window = None


def show_status(label, text, error=False):
    label.config(text=text, foreground=ERROR_COLOR if error else "")


def report_input_error(title, message, status_label, box):
    show_status(status_label, message, error=True)
    messagebox.showwarning(title, message)
    box.focus_set()
    box.select_range(0, "end")


def make_table(parent, columns):
    frame = ttk.Frame(parent)
    names = []
    for heading, width in columns:
        names.append(heading)
    table = ttk.Treeview(frame, columns=names, show="headings", selectmode="browse")
    for heading, width in columns:
        table.heading(heading, text=heading)
        table.column(heading, width=width, anchor="w")
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    table.pack(side="left", fill="both", expand=True)
    return frame, table


def make_picture_panel(parent):
    frame = ttk.Frame(parent, width=PICTURE_PANEL_WIDTH)
    frame.pack_propagate(False)
    picture = ttk.Label(frame, text=PICTURE_HINT, anchor="center", justify="center")
    picture.card = None
    picture.bind("<Button-1>", enlarge_picture)
    picture.pack(pady=(0, 8))
    info = ttk.Label(frame, text="", justify="center", wraplength=PICTURE_INFO_WRAP)
    info.pack()
    return frame, picture, info


def clear_card(picture, info):
    picture.config(image="", text=PICTURE_HINT, cursor="")
    picture.image = None
    picture.card = None
    info.config(text="")


def load_photo(path):
    try:
        return tk.PhotoImage(file=path)
    except tk.TclError:
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def show_card(card, picture, info):
    info.config(text="{}\n{} ({}) #{}\nArtist: {}\n(click the picture to enlarge it)".format(
        card["name"], card["set"], card["series"], card["number"], card["artist"] or "unknown"))
    picture.card = card
    picture.config(image="", text="Loading picture...", cursor="hand2")
    picture.image = None
    root.update_idletasks()

    path = api.get_image(card)
    if path is None:
        picture.config(text="No picture available.")
        return
    photo = load_photo(path)
    if photo is None:
        picture.config(text="The picture could not be shown.")
        return
    picture.config(image=photo, text="")
    picture.image = photo


def show_selected(table, cards, picture, info):
    index = selected_index(table)
    if index is None or index >= len(cards):
        clear_card(picture, info)
    else:
        show_card(cards[index], picture, info)


def selected_index(table):
    selected = table.selection()
    if len(selected) == 0:
        return None
    return int(selected[0])


def show_hp(card):
    if card["hp"] == 0:
        return "-"
    return card["hp"]


def show_types(card):
    return ", ".join(card["types"])


def fill_results_table(table, cards):
    for row in table.get_children():
        table.delete(row)
    for index, card in enumerate(cards):
        table.insert("", "end", iid=str(index), values=(
            card["name"], card["set"], card["number"], card["rarity"],
            show_types(card), show_hp(card), card["release_date"]))


def add_selected(table, cards, status_label):
    index = selected_index(table)
    if index is None or index >= len(cards):
        messagebox.showinfo("Add card", "Click a card in the table first.")
        return
    message = collection.add_card(my_cards, cards[index], condition_var.get())
    show_status(status_label, message)
    collection_changed()


def shrink_to_fit_screen(photo, window):
    room = window.winfo_screenheight() - SCREEN_MARGIN
    for multiply, divide in SCALES:
        if photo.height() * multiply // divide <= room:
            break
    if (multiply, divide) != (1, 1):
        photo = photo.zoom(multiply).subsample(divide)
    return photo


def center_on_screen(window):
    window.update_idletasks()
    window_left = (window.winfo_screenwidth() - window.winfo_reqwidth()) // 2
    window_top = max(0, (window.winfo_screenheight() - window.winfo_reqheight()) // 2 - WINDOW_RAISE)
    window.geometry("+" + str(window_left) + "+" + str(window_top))


def close_large_picture(event=None):
    global large_window
    if large_window is not None:
        large_window.destroy()
        large_window = None


def enlarge_picture(event):
    global large_window
    card = getattr(event.widget, "card", None)
    if card is None:
        return
    close_large_picture()

    window = tk.Toplevel(root)
    large_window = window
    window.title(card["name"] + "  (click or press Esc to close)")
    window.protocol("WM_DELETE_WINDOW", close_large_picture)
    window.bind("<Button-1>", close_large_picture)
    window.bind("<Escape>", close_large_picture)
    label = ttk.Label(window, text="Loading the large picture ...", padding=30)
    label.pack()
    window.update()
    if large_window is not window:
        return
    window.focus_force()

    path = api.get_large_image(card)
    photo = None
    if path is not None:
        photo = load_photo(path)
    if photo is None:
        label.config(text="The large picture could not be loaded.")
        return

    photo = shrink_to_fit_screen(photo, window)
    label.config(image=photo, text="", padding=0)
    label.image = photo
    center_on_screen(window)


def show_search_status(text):
    show_status(search_status, text)
    root.update()


def do_search(event=None):
    global search_results, recent_searches
    if str(search_button["state"]) == "disabled":
        return
    hide_suggestions()

    name, error = validation.check_card_name(search_var.get())
    if error:
        report_input_error("Card name", error, search_status, search_entry)
        return
    search_var.set(name)

    search_button.config(state="disabled")
    show_status(search_status, 'Searching for "' + name + '" ... this can take a few seconds.')
    root.update()
    cards, error = api.search_cards(name, show_search_status)
    search_button.config(state="normal")

    if error:
        show_status(search_status, "The search did not work.")
        messagebox.showerror("Search failed", error)
        return

    search_results = cards
    fill_results_table(results_table, search_results)

    if len(search_results) == 0:
        show_status(search_status, 'No cards found for "' + name + '". Check the spelling.')
    else:
        suggestions.add_recent(name)
        recent_searches = suggestions.load_recent()
        text = "Found " + str(len(search_results)) + " cards. Click one, pick a condition, then click Add."
        if len(search_results) >= api.PAGE_SIZE:
            text = text + " (Only the first " + str(api.PAGE_SIZE) + " are shown - type more of the name to narrow it down.)"
        show_status(search_status, text)


def on_result_selected(event=None):
    show_selected(results_table, search_results, search_picture, search_info)


def do_add():
    add_selected(results_table, search_results, search_status)


def show_suggestions(event=None):
    items = suggestions.get_suggestions(search_var.get(), recent_searches, pokemon_names)
    suggestion_box.delete(0, "end")
    if len(items) == 0:
        suggestion_box.place_forget()
        return
    for item in items:
        suggestion_box.insert("end", item)
    suggestion_box.config(height=len(items))
    suggestion_box.place(in_=search_entry, relx=0, rely=1.0, relwidth=1.0)
    suggestion_box.lift()


def hide_suggestions(event=None):
    suggestion_box.place_forget()


def suggestions_visible():
    return suggestion_box.winfo_ismapped()


def move_suggestion(step):
    if not suggestions_visible():
        show_suggestions()
        if not suggestions_visible():
            return "break"
    size = suggestion_box.size()
    current = suggestion_box.curselection()
    if len(current) == 0:
        index = 0 if step > 0 else size - 1
    else:
        index = max(0, min(size - 1, current[0] + step))
    suggestion_box.selection_clear(0, "end")
    suggestion_box.selection_set(index)
    suggestion_box.see(index)
    return "break"


def accept_suggestion(event=None):
    chosen = suggestion_box.curselection()
    if len(chosen) == 0:
        return
    search_var.set(suggestion_box.get(chosen[0]))
    search_entry.icursor("end")
    hide_suggestions()
    do_search()


def on_search_enter(event=None):
    if suggestions_visible() and len(suggestion_box.curselection()) > 0:
        accept_suggestion()
    else:
        do_search()


def on_search_key(event):
    if event.keysym in NAVIGATION_KEYS:
        return
    show_suggestions()


def on_any_click(event):
    if event.widget is not suggestion_box and event.widget is not search_entry:
        hide_suggestions()


def load_name_list():
    global pokemon_names
    pokemon_names = suggestions.load_names()[0]


def show_browse_status(text):
    show_status(browse_status, text)
    root.update()


def show_tag_status(text):
    show_status(tag_status, text)
    root.update()


def values_for_kind(kind):
    if kind == "Set":
        return tuple(set_id_by_text)
    if kind == "Series":
        return browse.series_choices(browse_lists["sets"])
    if kind == "Type":
        return browse.TYPES
    if kind == "Supertype":
        return browse.SUPERTYPES
    if kind == "Subtype":
        return tuple(browse_lists["subtypes"])
    if kind == "Rarity":
        return tuple(browse_lists["rarities"])
    return browse.year_choices(browse_lists["sets"])


def on_kind_selected(event=None):
    global value_choices
    kind = kind_var.get()
    value_var.set("")
    value_choices = ()
    if browse_lists is not None and kind != "":
        value_choices = values_for_kind(kind)
    value_box.config(values=value_choices)
    if kind in browse.TYPEABLE_KINDS:
        value_box.config(state="normal")
    else:
        value_box.config(state="readonly")
    if kind == "" or browse_lists is None:
        return
    if len(value_choices) == 0:
        show_status(tag_status, "No " + kind.lower() + " choices are loaded. Click Reload lists to try again.")
    elif kind in browse.TYPEABLE_KINDS:
        show_status(tag_status, "Type part of a name to search the list (a year works too), or click the arrow to pick.")
    else:
        show_status(tag_status, "Pick a value from the list, then click Add tag.")


def on_value_typed(event):
    if kind_var.get() not in browse.TYPEABLE_KINDS:
        return
    if event.keysym in NAVIGATION_KEYS:
        return
    if value_var.get() == "":
        value_box.config(values=value_choices)
        show_status(tag_status, "Type part of a name to search the list (a year works too), or click the arrow to pick.")
        return
    typed, error = validation.check_tag_value(value_var.get(), kind_var.get(), True)
    if error:
        value_box.config(values=value_choices)
        show_status(tag_status, error, error=True)
        return
    matches = browse.narrow(value_choices, typed)
    value_box.config(values=matches)
    if len(matches) == 0:
        show_status(tag_status, 'Nothing matches "' + typed + '". Check the spelling, or clear the box and click the arrow to see the whole list.')
    elif len(matches) == 1:
        show_status(tag_status, "One match: " + matches[0] + ".  Press Enter or click Add tag.")
    else:
        show_status(tag_status, str(len(matches)) + " matches. Click the arrow to pick one, or keep typing.")


def ensure_lists(force=False):
    global browse_lists, set_id_by_text
    if browse_lists is not None and not force:
        return
    show_tag_status("Loading the lists of sets, series and rarities. The first time this can take a little while - please wait ...")
    browse_lists, note = browse.get_lists(show_tag_status, force)
    set_id_by_text = dict(browse.set_choices(browse_lists["sets"]))
    on_kind_selected()
    if note != "":
        show_status(tag_status, note)
    else:
        show_status(tag_status, "Pick a kind and a value, then click Add tag.")


def reload_lists():
    ensure_lists(force=True)


def on_tab_changed(event=None):
    hide_suggestions()
    if tabs.select() == str(browse_tab):
        ensure_lists()


def add_tag(event=None):
    kind = kind_var.get()
    error = validation.check_tag_kind(kind)
    if error:
        report_input_error("Add tag", error, tag_status, kind_box)
        return
    typed, error = validation.check_tag_value(value_var.get(), kind, kind in browse.TYPEABLE_KINDS)
    if error:
        report_input_error("Add tag", error, tag_status, value_box)
        return

    shown = typed
    if kind in browse.TYPEABLE_KINDS:
        shown, matches = browse.find_choice(typed, value_choices)
        if shown == "":
            if len(matches) == 0:
                show_status(tag_status, 'Nothing matches "' + typed + '". Check the spelling, or click the arrow to see the list.')
            else:
                show_status(tag_status, str(len(matches)) + ' choices match "' + typed + '". Click the arrow and pick one, or type more.')
            return

    value = shown
    if kind == "Set":
        value = set_id_by_text.get(shown, "")
    if value == "":
        show_status(tag_status, "That set is not in the list.")
        return
    tag = (kind, value, shown)
    if tag in browse_tags:
        show_status(tag_status, "That tag is already in the list.")
        return
    browse_tags.append(tag)
    value_var.set("")
    value_box.config(values=value_choices)
    show_status(tag_status, "Tag added. Add more tags, or click Browse.")
    redraw_tags()


def remove_tag(index):
    del browse_tags[index]
    redraw_tags()


def clear_tags():
    browse_tags.clear()
    redraw_tags()


def redraw_tags():
    for child in tags_frame.winfo_children():
        child.destroy()
    if len(browse_tags) == 0:
        ttk.Label(tags_frame, text="No tags yet.").pack(side="left", padx=6, pady=4)
    for index, tag in enumerate(browse_tags):
        ttk.Button(tags_frame, text=browse.tag_label(tag) + "  ×",
                   command=lambda number=index: remove_tag(number)).pack(side="left", padx=4, pady=4)
    describe_label.config(text=browse.describe(browse_tags, mode_var.get()))


def update_page_controls():
    pages = max(1, (browse_total + api.PAGE_SIZE - 1) // api.PAGE_SIZE)
    if browse_total == 0:
        page_label.config(text="")
    else:
        page_label.config(text="Page " + str(browse_page) + " of " + str(pages) +
                          "   -   " + str(browse_total) + " cards match")
    previous_button.config(state="normal" if browse_page > 1 else "disabled")
    next_button.config(state="normal" if browse_page < pages else "disabled")


def do_browse(page=1):
    global browse_results, browse_query, browse_page, browse_total
    if str(browse_button["state"]) == "disabled":
        return
    if page == 1:
        if len(browse_tags) == 0:
            messagebox.showwarning("Browse", "Add at least one tag first.")
            return
        query = browse.build_tag_query(browse_tags, mode_var.get())
    else:
        query = browse_query

    browse_button.config(state="disabled")
    previous_button.config(state="disabled")
    next_button.config(state="disabled")
    show_browse_status("Loading cards ... this can take a few seconds.")
    cards, total, error = api.fetch_cards(query, page, show_browse_status, api.BROWSE_ORDER)
    browse_button.config(state="normal")

    if error:
        show_status(browse_status, "The browse did not work.")
        update_page_controls()
        messagebox.showerror("Browse failed", error)
        return

    browse_results = cards
    browse_query = query
    browse_page = page
    browse_total = total
    fill_results_table(browse_table, browse_results)
    update_page_controls()
    if len(cards) == 0:
        show_status(browse_status, "No cards match these tags.")
    else:
        show_status(browse_status, "Showing " + str(len(cards)) + " cards. Click one, pick a condition, then click Add.")


def previous_page():
    do_browse(browse_page - 1)


def next_page():
    do_browse(browse_page + 1)


def on_browse_selected(event=None):
    show_selected(browse_table, browse_results, browse_picture, browse_info)


def do_browse_add():
    add_selected(browse_table, browse_results, browse_status)


def read_filters():
    filters = collection.empty_filters()
    problems = []

    filters["name"], error = validation.check_name_filter(filter_vars["name"].get())
    if error:
        problems.append(error)

    for key in filter_dropdowns:
        text = filter_vars[key].get().strip()
        filters[key] = "" if text == "All" else text

    filters["hp_min"], filters["hp_max"], errors = validation.check_number_pair(
        filter_vars["hp_min"].get(), filter_vars["hp_max"].get(), "HP at least", "HP at most", 60)
    problems.extend(errors)
    filters["qty_min"], filters["qty_max"], errors = validation.check_number_pair(
        filter_vars["qty_min"].get(), filter_vars["qty_max"].get(), "Quantity at least", "Quantity at most", 2)
    problems.extend(errors)
    return filters, problems


def show_filter_problems(problems):
    if len(problems) == 0:
        filter_problem_label.grid_remove()
        return
    filter_problem_label.config(text="\n".join(problems))
    filter_problem_label.grid()


def selected_collection_card():
    index = selected_index(collection_table)
    if index is None or index >= len(shown_cards):
        return None
    return shown_cards[index]


def refresh_collection(event=None):
    global shown_cards
    previous = selected_collection_card()

    filters, problems = read_filters()
    show_filter_problems(problems)
    matching = collection.filter_cards(my_cards, filters, match_var.get())
    shown_cards = collection.sort_cards(matching, sort_var.get(), order_var.get())

    for row in collection_table.get_children():
        collection_table.delete(row)
    for index, card in enumerate(shown_cards):
        collection_table.insert("", "end", iid=str(index), values=(
            card["name"], card["set"], card["number"], card["release_date"], card["rarity"],
            show_types(card), show_hp(card), card["condition"], card["quantity"], card["date_added"]))
        if card is previous:
            collection_table.selection_set(str(index))
            collection_table.see(str(index))

    if len(my_cards) == 0:
        count_label.config(text="Your collection is empty. Use the Search or Browse tab to add cards.")
    else:
        count_label.config(text=collection.count_text(shown_cards, my_cards))


def update_filter_choices():
    for key, box in filter_dropdowns.items():
        choices = ("All",) + collection.get_choices(my_cards, key)
        box.config(values=choices)
        if filter_vars[key].get() not in choices:
            filter_vars[key].set("All")


def collection_changed():
    update_filter_choices()
    refresh_collection()


def clear_filters():
    for key, variable in filter_vars.items():
        if key in filter_dropdowns:
            variable.set("All")
        else:
            variable.set("")
    refresh_collection()


def on_collection_selected(event=None):
    show_selected(collection_table, shown_cards, collection_picture, collection_info)


def do_remove():
    card = selected_collection_card()
    if card is None:
        messagebox.showinfo("Remove card", "Click a card in the table first.")
        return
    message = collection.remove_card(my_cards, card)
    show_status(collection_status, message)
    collection_changed()


root = tk.Tk()
root.title("Pokémon Card Collection Tracker")
root.geometry("1180x740")
root.minsize(980, 640)

tabs = ttk.Notebook(root)
tabs.pack(fill="both", expand=True, padx=6, pady=6)
search_tab = ttk.Frame(tabs)
browse_tab = ttk.Frame(tabs)
collection_tab = ttk.Frame(tabs)
tabs.add(search_tab, text="  Search cards  ")
tabs.add(browse_tab, text="  Browse cards  ")
tabs.add(collection_tab, text="  My collection  ")
tabs.bind("<<NotebookTabChanged>>", on_tab_changed)

condition_var = tk.StringVar(value="Near Mint")

search_row = ttk.Frame(search_tab)
search_row.pack(fill="x", padx=8, pady=8)
ttk.Label(search_row, text="Card name:").pack(side="left")
search_var = tk.StringVar()
search_entry = ttk.Entry(search_row, textvariable=search_var, width=SEARCH_BOX_WIDTH)
search_entry.pack(side="left", padx=6)
search_button = ttk.Button(search_row, text="Search", command=do_search)
search_button.pack(side="left")

results_row = ttk.Frame(search_tab)
results_row.pack(fill="both", expand=True, padx=8)
search_panel, search_picture, search_info = make_picture_panel(results_row)
search_panel.pack(side="right", fill="y", padx=(8, 0))
results_frame, results_table = make_table(results_row, SEARCH_COLUMNS)
results_frame.pack(side="left", fill="both", expand=True)
results_table.bind("<<TreeviewSelect>>", on_result_selected)

add_row = ttk.Frame(search_tab)
add_row.pack(fill="x", padx=8, pady=8)
ttk.Label(add_row, text="Condition:").pack(side="left")
condition_box = ttk.Combobox(add_row, textvariable=condition_var, values=collection.CONDITIONS,
                             state="readonly", width=CONDITION_BOX_WIDTH)
condition_box.pack(side="left", padx=6)
ttk.Button(add_row, text="Add to collection", command=do_add).pack(side="left")
search_status = ttk.Label(add_row, text="Type a card name and click Search.")
search_status.pack(side="left", padx=12)

suggestion_box = tk.Listbox(search_tab, height=1, activestyle="none", exportselection=False)
search_entry.bind("<KeyRelease>", on_search_key)
search_entry.bind("<Return>", on_search_enter)
search_entry.bind("<Down>", lambda event: move_suggestion(1))
search_entry.bind("<Up>", lambda event: move_suggestion(-1))
search_entry.bind("<Escape>", hide_suggestions)
search_entry.bind("<Button-1>", show_suggestions, add="+")
suggestion_box.bind("<ButtonRelease-1>", accept_suggestion)
root.bind("<Button-1>", on_any_click, add="+")

tag_row = ttk.Frame(browse_tab)
tag_row.pack(fill="x", padx=8, pady=(8, 4))
ttk.Label(tag_row, text="Add a tag:").pack(side="left")
kind_var = tk.StringVar()
kind_box = ttk.Combobox(tag_row, textvariable=kind_var, values=browse.KINDS, state="readonly", width=KIND_BOX_WIDTH)
kind_box.pack(side="left", padx=6)
kind_box.bind("<<ComboboxSelected>>", on_kind_selected)
value_var = tk.StringVar()
value_box = ttk.Combobox(tag_row, textvariable=value_var, values=(), state="readonly", width=VALUE_BOX_WIDTH)
value_box.pack(side="left", padx=6)
value_box.bind("<KeyRelease>", on_value_typed)
value_box.bind("<Return>", add_tag)
ttk.Button(tag_row, text="Add tag", command=add_tag).pack(side="left")
ttk.Button(tag_row, text="Reload lists", command=reload_lists).pack(side="right")
tag_status = ttk.Label(browse_tab, text="Pick a kind and a value, then click Add tag.", wraplength=WIDE_TEXT_WRAP, justify="left")
tag_status.pack(fill="x", padx=10, pady=(0, 2), anchor="w")

tags_frame = ttk.LabelFrame(browse_tab, text="Your tags (click a tag to remove it)")
tags_frame.pack(fill="x", padx=8, pady=4)

match_row = ttk.Frame(browse_tab)
match_row.pack(fill="x", padx=8, pady=2)
ttk.Label(match_row, text="Match:").pack(side="left")
mode_var = tk.StringVar(value="ALL")
ttk.Radiobutton(match_row, text="all tags (AND)", variable=mode_var, value="ALL",
                command=redraw_tags).pack(side="left", padx=6)
ttk.Radiobutton(match_row, text="any tag (OR)", variable=mode_var, value="ANY",
                command=redraw_tags).pack(side="left", padx=6)
browse_button = ttk.Button(match_row, text="Browse", command=do_browse)
browse_button.pack(side="left", padx=(20, 6))
ttk.Button(match_row, text="Clear tags", command=clear_tags).pack(side="left")
describe_label = ttk.Label(browse_tab, text="", wraplength=DESCRIPTION_WRAP)
describe_label.pack(fill="x", padx=10, pady=(0, 4), anchor="w")

browse_middle = ttk.Frame(browse_tab)
browse_middle.pack(fill="both", expand=True, padx=8)
browse_panel, browse_picture, browse_info = make_picture_panel(browse_middle)
browse_panel.pack(side="right", fill="y", padx=(8, 0))
browse_frame, browse_table = make_table(browse_middle, SEARCH_COLUMNS)
browse_frame.pack(side="left", fill="both", expand=True)
browse_table.bind("<<TreeviewSelect>>", on_browse_selected)

page_row = ttk.Frame(browse_tab)
page_row.pack(fill="x", padx=8, pady=(6, 0))
previous_button = ttk.Button(page_row, text="◀ Previous", command=previous_page, state="disabled")
previous_button.pack(side="left")
next_button = ttk.Button(page_row, text="Next ▶", command=next_page, state="disabled")
next_button.pack(side="left", padx=6)
page_label = ttk.Label(page_row, text="")
page_label.pack(side="left", padx=10)

browse_add_row = ttk.Frame(browse_tab)
browse_add_row.pack(fill="x", padx=8, pady=8)
ttk.Label(browse_add_row, text="Condition:").pack(side="left")
browse_condition_box = ttk.Combobox(browse_add_row, textvariable=condition_var, values=collection.CONDITIONS,
                                    state="readonly", width=CONDITION_BOX_WIDTH)
browse_condition_box.pack(side="left", padx=6)
ttk.Button(browse_add_row, text="Add to collection", command=do_browse_add).pack(side="left")
browse_status = ttk.Label(browse_add_row, text="")
browse_status.pack(side="left", padx=12)

filter_frame = ttk.LabelFrame(collection_tab, text="Filters")
filter_frame.pack(fill="x", padx=8, pady=(8, 4))

filter_vars = {}
filter_dropdowns = {}
filter_items = []


def new_filter_entry(key, label_text):
    variable = tk.StringVar()
    filter_vars[key] = variable
    entry = ttk.Entry(filter_frame, textvariable=variable, width=FILTER_BOX_WIDTH)
    entry.bind("<KeyRelease>", refresh_collection)
    filter_items.append((label_text, entry))


def new_filter_dropdown(key, label_text):
    variable = tk.StringVar(value="All")
    filter_vars[key] = variable
    box = ttk.Combobox(filter_frame, textvariable=variable, values=("All",), state="readonly", width=FILTER_BOX_WIDTH)
    box.bind("<<ComboboxSelected>>", refresh_collection)
    filter_dropdowns[key] = box
    filter_items.append((label_text, box))


new_filter_entry("name", "Name contains")
for label_text, key in FILTER_DROPDOWNS:
    new_filter_dropdown(key, label_text)
new_filter_entry("hp_min", "HP at least")
new_filter_entry("hp_max", "HP at most")
new_filter_entry("qty_min", "Quantity at least")
new_filter_entry("qty_max", "Quantity at most")

for slot, (label_text, widget) in enumerate(filter_items):
    grid_row = slot // 5
    grid_column = slot % 5
    ttk.Label(filter_frame, text=label_text).grid(row=grid_row * 2, column=grid_column, sticky="w", padx=6)
    widget.grid(row=grid_row * 2 + 1, column=grid_column, sticky="we", padx=6, pady=(0, 6))
for column in range(5):
    filter_frame.columnconfigure(column, weight=1)

match_var = tk.StringVar(value="ALL")
filter_match_row = ttk.Frame(filter_frame)
filter_match_row.grid(row=6, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))
ttk.Label(filter_match_row, text="Match:").pack(side="left")
ttk.Radiobutton(filter_match_row, text="all filters (AND)", variable=match_var, value="ALL",
                command=refresh_collection).pack(side="left", padx=6)
ttk.Radiobutton(filter_match_row, text="any filter (OR)", variable=match_var, value="ANY",
                command=refresh_collection).pack(side="left", padx=6)
ttk.Button(filter_frame, text="Clear filters", command=clear_filters).grid(
    row=6, column=4, sticky="e", padx=6, pady=(0, 6))
filter_problem_label = ttk.Label(filter_frame, text="", foreground=ERROR_COLOR, justify="left",
                                 wraplength=WIDE_TEXT_WRAP)
filter_problem_label.grid(row=7, column=0, columnspan=5, sticky="w", padx=6, pady=(0, 6))
filter_problem_label.grid_remove()

sort_row = ttk.Frame(collection_tab)
sort_row.pack(fill="x", padx=8, pady=4)
ttk.Label(sort_row, text="Sort by:").pack(side="left")
sort_var = tk.StringVar(value="Name")
sort_box = ttk.Combobox(sort_row, textvariable=sort_var, values=collection.SORT_OPTIONS,
                        state="readonly", width=SORT_BOX_WIDTH)
sort_box.pack(side="left", padx=6)
sort_box.bind("<<ComboboxSelected>>", refresh_collection)
order_var = tk.StringVar(value="Ascending")
order_box = ttk.Combobox(sort_row, textvariable=order_var, values=collection.ORDERS,
                         state="readonly", width=ORDER_BOX_WIDTH)
order_box.pack(side="left")
order_box.bind("<<ComboboxSelected>>", refresh_collection)
count_label = ttk.Label(sort_row, text="")
count_label.pack(side="right")

table_row = ttk.Frame(collection_tab)
table_row.pack(fill="both", expand=True, padx=8)
collection_panel, collection_picture, collection_info = make_picture_panel(table_row)
collection_panel.pack(side="right", fill="y", padx=(8, 0))
collection_frame, collection_table = make_table(table_row, COLLECTION_COLUMNS)
collection_frame.pack(side="left", fill="both", expand=True)
collection_table.bind("<<TreeviewSelect>>", on_collection_selected)

remove_row = ttk.Frame(collection_tab)
remove_row.pack(fill="x", padx=8, pady=8)
ttk.Button(remove_row, text="Remove one copy", command=do_remove).pack(side="left")
collection_status = ttk.Label(remove_row, text="Click a card, then click Remove to take out one copy.")
collection_status.pack(side="left", padx=12)


my_cards, load_warning = collection.load_collection()
collection_changed()
redraw_tags()
recent_searches = suggestions.load_recent()


def show_load_warning():
    messagebox.showwarning("Saved collection", load_warning)


if load_warning:
    root.after(LOAD_WARNING_DELAY_MS, show_load_warning)
root.after(LOAD_NAMES_DELAY_MS, load_name_list)

search_entry.focus()

if __name__ == "__main__":
    root.mainloop()
