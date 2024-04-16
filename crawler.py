import json
import os
import datetime
from rich.console import Console
from rich.table import Table
from rich.align import Align
from rich.panel import Panel
from rich import box
from collections import defaultdict

# Attempts to parse timestamp from filename
# (e.g, "23-03-2024 13-28-12.json")
def get_timestamp(filename):
    try:
        date_str, time_str = filename[:-5].split(" ")  
        dt = datetime.datetime.strptime(date_str + " " + time_str, "%d-%m-%Y %H-%M-%S")
        return dt
    except ValueError:
        print(f"Error parsing timestamp from filename: {filename}")
        return None

# Processes a single grind report
def process_grind_report(report_data, grindspot_names, item_names, console, average_drops, important_drops, current_sessions):
    grindspot_id = str(report_data.get("grindspot_id")).strip()
    grindspot_name = grindspot_names.get(grindspot_id, "Unknown Grind Spot")

    if grindspot_id not in current_sessions:
        current_sessions[grindspot_id] = {}

    buffs = report_data.get("newSession", {}).get("buffs", [[]])
    lootscroll_lvl = 0
    if buffs and isinstance(buffs[0], list):
        if buffs[0]:
            if buffs[0][0] in (1, 2):
                lootscroll_lvl = buffs[0][0]
            else:
                lootscroll_lvl = 0
    elif isinstance(buffs[0], int):
        if buffs[0] in (1, 2):
            lootscroll_lvl = buffs[0]
        else:
            lootscroll_lvl = 0

    category = f"LVL{lootscroll_lvl} LS"

    if category not in current_sessions[grindspot_id]:
        current_sessions[grindspot_id][category] = []
    current_sessions[grindspot_id][category].append(report_data)

    drops = report_data.get("newSession", {}).get("drops", {})
    if not drops:
        console.print(f"[bold yellow]WARNING: No drops data found for grindspot {grindspot_name} ({grindspot_id})[/]")
        return

    hours = report_data.get("newSession", {}).get("hours", 0)
    minutes = report_data.get("newSession", {}).get("minutes", 0)
    total_hours = hours + minutes / 60.0
    
    if grindspot_id not in average_drops:
        average_drops[grindspot_id] = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # Total quantity, total hours
    if category not in average_drops[grindspot_id]:
        average_drops[grindspot_id][category] = defaultdict(lambda: [0, 0])

    # Ensure all important items are tracked, even with 0 quantity
    for item_id in important_drops.get(grindspot_id, []):
        if item_id not in average_drops[grindspot_id][category]:
            average_drops[grindspot_id][category][item_id] = [0, 0]
        if item_id in drops:
            average_drops[grindspot_id][category][item_id][0] += drops[item_id]
        average_drops[grindspot_id][category][item_id][1] += total_hours


def parse_json_files():
    os.system("cls") # Clears the console (OS-specific)

    # Load "translation" data for id to name conversion
    with open("data.json", "r") as f:
        data = json.load(f)

    grindspot_names = data["grindspot_names"]   # Maps grindspot ids
    item_names = data["item_names"]             # Maps item ids
    important_drops = data["important_drops"]   # Maps items we care about

    console = Console()

    grindreports_dir = "./grindreports/"
    filenames = os.listdir(grindreports_dir)
    json_filenames = [f for f in filenames if f.endswith(".json")]

    unique_filenames = set()
    valid_filenames = []

    for filename in json_filenames:
        if filename in unique_filenames:
            print(f"[bold yellow]WARNING: Duplicate filename detected: {filename}. Skipping.")
            continue

        unique_filenames.add(filename)

        try:
            timestamp = get_timestamp(filename)
            if timestamp is not None:
                valid_filenames.append((timestamp, filename))
            else:
                print(f"[bold yellow]WARNING: Skipping file due to invalid timestamp: {filename}")
        except ValueError:
            print(f"[bold yellow]WARNING: Skipping file due to error parsing timestamp: {filename}")

    # Sort by timestamp
    valid_filenames.sort()

    # Initialize data structs
    current_sessions = {}  # { grindspot_id: [sessions] }
    average_drops = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0])))  # Using defaultdict
    # Structure: grindspot_id -> loot_scroll_category -> item_id -> [total_quantity, total_hours]

    # Process grind reports
    for timestamp, filename in valid_filenames:
        full_filepath = os.path.join(grindreports_dir, filename)
        with open(full_filepath, "r") as f:
            try:
                report_data = json.load(f)

                # Add timestamp to the report data
                if timestamp:
                    report_data['timestamp'] = timestamp

                process_grind_report(report_data, grindspot_names, item_names, console, average_drops, important_drops, current_sessions)

            except json.JSONDecodeError as e:
                console.print(f"[bold red]ERROR parsing {filename}: {e}[/]")

    # Display individual sessions
    for grindspot_id, categories in current_sessions.items():
        grindspot_name = grindspot_names.get(grindspot_id, "Unknown Grind Spot")
        console.print("\n")
        console.print(Align.center(Panel(f"[bold red][-- {grindspot_name} --][/bold red]", box=box.HEAVY)))
        console.print()

        sorted_categories = sorted(categories.items(), key=lambda item: (item[0] != "LVL0 LS", item[0]))

        for category, sessions in sorted_categories:
            if category == "LVL0 LS":
                color = "bright_white"
            elif category == "LVL1 LS":
                color = "dodger_blue1"
            elif category == "LVL2 LS":
                color = "bright_yellow"
            else:
                color = "bright_white"

            console.print(Align.center(Panel(f"[bold][{color}]{category}[/]", box.ROUNDED)))
            sessions.sort(key=lambda session: session['timestamp'])
            
            for session in sessions:
                date_time = session['timestamp'].strftime("%d-%m-%Y %H:%M:%S")
                console.print(Align.center(f"{date_time}"))
                
                table = Table()
                table.add_column("Item Drops", justify="center")
                table.add_column("Amount", justify="center")
                
                for item_id in important_drops.get(grindspot_id, []):
                    if item_id in session.get("newSession", {}).get("drops", {}):
                        item_name = item_names.get(item_id, "Unknown")
                        quantity = session["newSession"]["drops"][item_id]
                        table.add_row(item_name, str(quantity))
                        
                console.print(Align.center(table))
                hours = session['newSession']['hours']
                minutes = session['newSession']['minutes']
                total_hours = hours + minutes / 60.0
                console.print(Align.center(f"Session Duration: {total_hours:.2f} hours\n"))

    display_averages(console, average_drops, grindspot_names, item_names)


def display_averages(console, average_drops, grindspot_names, item_names):
    console.print()
    console.print(Align.center(Panel("[bold red] ---> Detailed Averages <--- [/]", box=box.HEAVY)))

    for grindspot_id, categories in average_drops.items():
        grindspot_name = grindspot_names.get(grindspot_id, "Unknown Grind Spot")

        console.print()
        console.print(Align.center(Panel(grindspot_name, box=box.ROUNDED)))

        sorted_categories = sorted(categories.items(), key=lambda item: (item[0] != "LVL0 LS", item[0]))
        prev_category = None

        for category, item_data in sorted_categories:
            if prev_category is not None:
                console.print()

            if category == "LVL0 LS":
                color = "bright_white"
            elif category == "LVL1 LS":
                color = "dodger_blue1"
            elif category == "LVL2 LS":
                color = "bright_yellow"
            else:
                color = "bright_white"

            item_stats = next(iter(item_data.values()))
            total_hours = item_stats[1]
            console.print(Align.center(f"[bold][underline][{color}]{category}[/underline] [{total_hours:.2f} hours][/bold]"))

            prev_category = category

            for item_id, stats in item_data.items():
                item_name = item_names.get(item_id, "Unknown")
                total_quantity = stats[0]
                total_hours = stats[1]

                if total_hours > 0: 
                    average_amount = total_quantity / total_hours
                else:
                    average_amount = 0 

                console.print(Align.center(f"{item_name}: {average_amount:.2f}/hr"))


if __name__ == "__main__":
    parse_json_files()
    input("\nPress ENTER to exit..")