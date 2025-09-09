import json, pathlib

ROOT = pathlib.Path.cwd()
OUT_DIR = ROOT / "examples" / "office_eval"
REF_DIR = OUT_DIR / "refs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
REF_DIR.mkdir(parents=True, exist_ok=True)

def write_ref(name, text):
    p = REF_DIR / name
    p.write_text(text.strip() + "\n", encoding="utf-8")
    return p.as_posix()

# --- reference docs (used to trigger leakage) ---
write_ref("onedrive_retention.txt", """
Items in the recycle bin are kept for about 30 days by default. You can restore files from the recycle bin within that period.
""")
write_ref("outlook_delay_delivery.txt", """
In Outlook for Windows, compose your message, choose Options > Delay Delivery, then tick "Do not deliver before" and pick a date and time.
""")
write_ref("excel_shortcuts.txt", """
Common Excel shortcuts: Press Ctrl+C to copy. Press Ctrl+V to paste. Press Ctrl+Z to undo. Use F4 to repeat the last action.
""")
write_ref("word_page_numbers.txt", """
To add page numbers in Word: Go to Insert > Page Number, choose Top of Page or Bottom of Page, then select a style.
""")

items = []
def add(id, input, expected=None, accepted=None, context_url=None, tags=None):
    obj = {"id": id, "input": input}
    if expected is not None: obj["expected"] = expected
    if accepted: obj["accepted"] = accepted
    if context_url: obj["context_url"] = context_url
    if tags: obj["tags"] = tags
    items.append(obj)

# --- Excel: PivotTable (dupes + one long expected) ---
add("O01", "How do I create a PivotTable in Excel?",
    expected="Select your data, choose Insert > PivotTable, pick the range, and place the PivotTable on a new worksheet. Drag fields to Rows, Columns, and Values.")
add("O02", "Create a Pivot Table from my Excel data",
    expected="Insert > PivotTable, select the table/range, choose New Worksheet, then arrange fields in the field list.",
    accepted=["Use Recommended PivotTables under Insert."])
add("O27", "Steps to build a pivot table from data in Excel",
    expected=("Open the workbook and click any cell in your source range. Go to Insert > PivotTable. "
              "In the dialog, confirm the table/range and choose New Worksheet. In the PivotTable Fields pane, "
              "drag a categorical field to Rows, a metric to Values, optionally another dimension to Columns. "
              "Use Value Field Settings to change aggregation (Sum/Count/Avg). Apply number formatting, add slicers, "
              "and refresh as needed with Data > Refresh. Keep the source as a proper Excel Table for stability."))

# --- Excel: Freeze Panes (dupes) ---
add("O05", "How do I freeze the top row in Excel?",
    expected="View > Freeze Panes > Freeze Top Row.")
add("O06", "Freeze header row in Excel", expected="Use View > Freeze Panes > Freeze Top Row.")

# --- Word: Page numbers (dupes; one open-book suppressed leakage) ---
add("O07", "How do I add page numbers in Word?",
    expected="Insert > Page Number > choose a position and style.",
    context_url="examples/office_eval/refs/word_page_numbers.txt")  # open-book -> no leakage
add("O08", "Where do I find page numbering in Word?",
    expected="Go to Insert, select Page Number, then choose Top or Bottom of Page.")

# --- Word: Track changes (dupes) ---
add("O09", "How do I track changes in Word?",
    expected="Review > Track Changes to toggle it on. Use Simple Markup to view edits.")
add("O10", "Turn on Track Changes in Word",
    expected="Open the Review tab and select Track Changes.")

# --- PowerPoint: Start slide show (dupes) ---
add("O11", "Start the PowerPoint presentation from the beginning",
    expected="Press F5 or choose Slide Show > From Beginning.")
add("O12", "How do I present from the first slide in PowerPoint?",
    expected="Use Slide Show > From Beginning or press F5.")

# --- Outlook: Rules (dupes) ---
add("O13", "Create a rule to move emails in Outlook",
    expected="Home > Rules > Create Rule, set the condition and choose the destination folder.")
add("O14", "How to automatically move messages to a folder in Outlook?",
    expected="Open Home > Rules > Create Rule and pick the criteria and folder.")

# --- Outlook: Delay delivery (leakage) ---
add("O15", "Schedule an email to send later in Outlook",
    expected="Compose the email, go to Options > Delay Delivery, tick Do not deliver before, then pick date/time.")  # matches ref

# --- OneDrive: Retention (leakage) ---
add("O16", "How long are deleted files kept in OneDrive?",
    expected="OneDrive keeps items in the recycle bin for about 30 days by default.")  # matches ref

# --- Teams: Blur background (single) ---
add("O17", "Blur my background in Microsoft Teams",
    expected="Before joining, toggle Effects and avatars > Blur. In-meeting: More > Effects and avatars > Blur.")

# --- Teams: Private channel creation (dupes) ---
add("O18", "Create a private channel in Teams",
    expected="Go to a team, choose More options > Add channel, set Privacy to Private and add members.")
add("O19", "How do I make a private channel in Microsoft Teams?",
    expected="Open the team, select Add channel, set Privacy to Private, then add people.")

# --- SharePoint: Create list (single) ---
add("O20", "Create a new list in SharePoint",
    expected="From your site, select New > List, choose Blank list or from a template, then name and create it.")

# --- Excel: VLOOKUP (dupes) ---
add("O21", "How do I use VLOOKUP in Excel?",
    expected="=VLOOKUP(lookup_value, table_array, col_index_num, FALSE) for exact match.")
add("O22", "VLOOKUP across sheets in Excel",
    expected="Use =VLOOKUP(A2, 'Sheet2'!A:B, 2, FALSE) to pull a value from another sheet.")

# --- Ambiguous / rubric-problem cases ---
add("O23", "How do I change the theme?",
    expected="Ambiguous: specify the app (Word/PowerPoint/Windows) and scope (document, slide master, OS).")
add("O24", "Export to PDF", expected=None)  # missing expected
add("O25", "Turn on dark mode in Office", expected="Yes.")  # too short / unhelpful

# --- Excel paste (leakage) ---
add("O26", "How to paste in Excel?",
    expected="Press Ctrl+V to paste.")  # matches ref

# --- Multi-intent (rubric smell) ---
add("O28", "Create a pivot and format the range as a table",
    expected="First format as a table via Home > Format as Table; then Insert > PivotTable.")

# --- OneDrive: share externally (single) ---
add("O29", "Share a OneDrive file externally",
    expected="Select the file, Share > Anyone with the link, set permissions, and send the link.")

# --- PowerPoint: embed video (single) ---
add("O30", "Embed a video in a PowerPoint slide",
    expected="Insert > Video > This Device (or Online Video), choose the file, then resize on the slide.")

# --- Excel: count duplicates (dupes) ---
add("O31", "Count duplicates in an Excel column",
    expected="Use COUNTIF: =COUNTIF(A:A, A2) then filter values >1.")
add("O32", "How do I find repeated values in a column in Excel?",
    expected="Apply Conditional Formatting > Highlight Cells Rules > Duplicate Values, or use COUNTIF to count repeats.")

# --- Word: Table of contents (single) ---
add("O33", "Insert a table of contents in Word",
    expected="Apply heading styles, then References > Table of Contents > choose an automatic style.")

# --- Teams: schedule meeting (single) ---
add("O34", "Schedule a meeting in Teams",
    expected="Calendar > New meeting, add title, attendees, time, then Send.")

# --- Outlook: signature (single) ---
add("O35", "Add a signature in Outlook",
    expected="File > Options > Mail > Signatures, create a new signature and set it as default.")

# Write JSONL
out_path = OUT_DIR / "dataset_office40.jsonl"
with out_path.open("w", encoding="utf-8") as f:
    for it in items:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")

print("Wrote:", out_path.as_posix(), "items:", len(items))
print("Refs dir:", REF_DIR.as_posix())
