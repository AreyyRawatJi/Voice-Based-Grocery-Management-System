import os
import csv
import wave
import struct
import speech_recognition as sr
import sqlite3
import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from deep_translator import GoogleTranslator
from gtts import gTTS  # ✅ TTS

# ================== SETTINGS ==================

DB_NAME = "mydatabase.db"

WAKE_PHRASES = (
    "hello device",
    "hey device",
    "hello assistant",
    "hey assistant",
    "wake up",
    "start listening",
)

# number words + some Hindi-ish
NUMBER_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10,
    "do": 2, "teen": 3, "char": 4, "paanch": 5,
    "half": 0.5, "aadha": 0.5, "adha": 0.5
}

# units – extended for normal household use
UNIT_MAP = {
    "kg": "kg", "kilo": "kg", "kilogram": "kg",
    "g": "g", "gram": "g", "grams": "g", "gm": "g", "gms": "g",
    "liter": "l", "litre": "l", "l": "l", "ltr": "l",
    "ml": "ml", "milliliter": "ml", "millilitre": "ml",
    "packet": "packet", "packets": "packet", "pack": "packet",
    "bottle": "bottle", "botal": "bottle", "box": "box",
    "piece": "pcs", "pieces": "pcs", "pc": "pcs", "pcs": "pcs"
}

def normalize_unit(u: str) -> str:
    return UNIT_MAP.get(u.lower(), u)

# Common household / grocery keywords – used for fallback
HOUSEHOLD_KEYWORDS = [
    # vegetables
    "aloo", "aalu", "potato", "pyaj", "pyaaz", "onion",
    "gajar", "carrot", "mirchi", "chilli", "chili",
    "tomato", "tamatar",
    # staples
    "rice", "chawal", "atta", "flour", "maida",
    "salt", "namak", "sugar", "cheeni", "dal", "pulses",
    "oil", "refined", "ghee",
    # dairy
    "milk", "dahi", "curd", "butter", "paneer",
    # snacks
    "biscuit", "biscuits", "chips", "kurkure", "namkeen",
    "cold drink", "cola", "coke", "pepsi", "juice",
    # condiments
    "achar", "aachar", "aachaar", "pickle",
    "sauce", "ketchup", "masala", "powder",
    # hygiene / bathroom
    "soap", "detergent", "washing powder",
    "shampoo", "conditioner", "toothpaste", "brush",
    "handwash", "facewash",
    # personal
    "condom", "sanitary", "pad", "tissue",
    # clothes / misc
    "t-shirt", "shirt", "jeans",
    "mobile", "charger",
    # general
    "bottle", "packet"
]

# ================== VOICE (with small silence to avoid cut) ==================

def ensure_silence_wav():
    """
    Create a short 0.5 second silence.wav if it does not exist.
    Used to wake up Bluetooth speaker before speaking.
    """
    if os.path.exists("silence.wav"):
        return

    framerate = 16000
    duration = 0.5  # seconds
    nframes = int(framerate * duration)

    with wave.open("silence.wav", "w") as wf:
        wf.setnchannels(1)      # mono
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(framerate)

        silence_frame = struct.pack("<h", 0)
        wf.writeframes(silence_frame * nframes)


def speak(text: str):
    if not text:
        return

    print("VOICE:", text)

    # 1) ensure silence file exists
    ensure_silence_wav()

    # 2) play brief silence to wake speaker
    os.system("aplay -q silence.wav")

    # 3) now play actual speech
    raw_file = "voice_raw.mp3"
    try:
        tts = gTTS(text=text, lang="en")
        tts.save(raw_file)
        os.system(f"mpg123 -q {raw_file}")
    except Exception as e:
        print("TTS error:", e)

# ================== DATABASE ==================

def create_db():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS speech_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number REAL,
            unit TEXT,
            item TEXT,
            date TEXT
        )
    """)
    con.commit()
    con.close()
    print("✅ Database ready")

def add_item(number, unit, item):
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    today = datetime.date.today().isoformat()
    cur.execute(
        "INSERT INTO speech_data (number, unit, item, date) VALUES (?, ?, ?, ?)",
        (number, unit, item, today)
    )
    con.commit()
    con.close()
    speak(f"{number} {unit} {item} added")

def delete_last():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("SELECT id, item FROM speech_data ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM speech_data WHERE id = ?", (row[0],))
        con.commit()
        speak(f"Deleted last item {row[1]}")
    else:
        speak("No data found")
    con.close()

def delete_item(item_name):
    item_name = item_name.lower().strip()
    if not item_name:
        speak("No item name given to delete")
        return
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute(
        "DELETE FROM speech_data WHERE LOWER(item) LIKE ?",
        (f"%{item_name}%",)
    )
    count = cur.rowcount
    con.commit()
    con.close()
    speak(f"{count} item deleted")

def delete_all():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("DELETE FROM speech_data")
    con.commit()
    con.close()
    speak("All data deleted")

def update_last(number, unit, item):
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("SELECT id FROM speech_data ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        cur.execute("""
            UPDATE speech_data
            SET number=?, unit=?, item=?
            WHERE id=?
        """, (number, unit, item, row[0]))
        con.commit()
        speak("Last item updated")
    else:
        speak("No item found")
    con.close()

def update_item(old, number, unit, item):
    old = old.lower().strip()
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("""
        UPDATE speech_data
        SET number=?, unit=?, item=?
        WHERE LOWER(item) LIKE ?
    """, (number, unit, item, f"%{old}%"))
    count = cur.rowcount
    con.commit()
    con.close()
    speak(f"{count} item updated")

# ================== CSV EXPORT ==================

def export_to_csv(filename="grocery_list.csv"):
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("SELECT number, unit, item, date FROM speech_data")
    rows = cur.fetchall()
    con.close()

    if not rows:
        speak("No data to export")
        return

    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["NUM", "UNIT", "ITEM", "DATE"])
            writer.writerows(rows)
        speak(f"CSV file {filename} created")
    except Exception as e:
        print("CSV export error:", e)
        speak("Export failed")

# ================== TRANSLATION ==================

def translate_to_english(text):
    try:
        english = GoogleTranslator(source="auto", target="en").translate(text)
        print(f"ORIGINAL: {text} → ENGLISH: {english}")
        return english
    except Exception as e:
        print("Translation error:", e)
        return text

# ================== SPEECH INPUT ==================

def listen():
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening... (speak now)")
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=8, phrase_time_limit=10)

        text = r.recognize_google(audio)
        print("Heard:", text)
        return text
    except sr.WaitTimeoutError:
        print("No speech detected")
        return ""
    except sr.UnknownValueError:
        print("Could not understand")
        return ""
    except sr.RequestError as e:
        print("Speech API error:", e)
        return ""

# ================== GUI ==================

def gui():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("SELECT number, unit, item, date FROM speech_data")
    rows = cur.fetchall()
    con.close()

    root = tk.Tk()
    root.title("Voice Database")

    tree = ttk.Treeview(root, columns=("num","unit","item","date"), show="headings")
    for c in ("num","unit","item","date"):
        tree.heading(c, text=c.upper())
        tree.column(c, width=160)

    for row in rows:
        tree.insert("", tk.END, values=row)

    tree.pack(expand=True, fill=tk.BOTH)

    # buttons
    btn_frame = tk.Frame(root)
    btn_frame.pack(fill=tk.X, pady=5)

    def on_export_csv():
        export_to_csv()
        messagebox.showinfo("Export", "grocery_list.csv has been created in this folder.")

    btn_csv = tk.Button(btn_frame, text="Export to CSV", command=on_export_csv)
    btn_csv.pack(side=tk.LEFT, padx=10)

    root.mainloop()

# ================== SMART PARSING HELPERS ==================

def parse_number(word: str):
    """Return float number if word looks like number/number-word, else None."""
    w = word.lower()
    if w in NUMBER_MAP:
        return float(NUMBER_MAP[w])
    # digits or decimal like 2.0
    try:
        return float(w.replace(",", ""))
    except ValueError:
        return None

def parse_number_unit_item(words):
    """
    Flexible parser:
      1) Try: <number> [unit] <item...>
         e.g. 2 kilo aloo, 2 litre milk, one t-shirt, 500 g lal mirchi powder
      2) If no number pattern, but contains household keyword:
         -> assume 1 item, unit "", item = full phrase
    """
    if not words:
        return None

    # ---------- PATH 1: number-first ----------
    if len(words) >= 2:
        num = parse_number(words[0])
        if num is not None:
            idx = 1
            unit = ""
            # optional unit
            if idx < len(words) and words[idx].lower() in UNIT_MAP:
                unit = normalize_unit(words[idx])
                idx += 1
            if idx < len(words):
                item = " ".join(words[idx:]).strip()
                if item:
                    return num, unit, item

    # ---------- PATH 2: item-only with known grocery words ----------
    joined = " ".join(words).lower()
    if any(kw in joined for kw in HOUSEHOLD_KEYWORDS):
        # default to 1 item, no specific unit
        return 1.0, "", joined

    return None

# ================== MAIN ==================

def main():
    create_db()
    active = False
    speak("System ready. Say hello device.")

    while True:
        print("---- Waiting for speech ----")
        spoken = listen()
        if not spoken:
            continue

        english = translate_to_english(spoken).lower()
        print("LOGIC TEXT:", english)

        # GLOBAL EXIT
        if "exit" in english or "goodbye" in english:
            speak("Goodbye")
            gui()
            break

        # WAKE
        if not active:
            if any(w in english for w in WAKE_PHRASES):
                active = True
                speak("I am ready to make list")
            continue

        # DELETE
        if english.startswith("delete"):
            if "all" in english:
                delete_all()
                continue
            if "last" in english:
                delete_last()
                continue

            item_name = english.replace("delete", "").strip()
            delete_item(item_name)
            continue

        # UPDATE LAST: "update last to 3 kilo aloo"
        if "update last to" in english:
            right = english.split("to", 1)[1].strip().split()
            parsed = parse_number_unit_item(right)
            if parsed:
                num, unit, item = parsed
                update_last(num, unit, item)
            else:
                speak("Unable to update last, say like update last to two kilo aloo")
            continue

        # FULL UPDATE: "update aloo to 3 kilo aloo" or rename "update aloo to achar"
        if english.startswith("update ") and " to " in english:
            left, right = english.split(" to ", 1)
            old = left.replace("update", "").strip()
            parts = right.strip().split()

            parsed = parse_number_unit_item(parts)
            if parsed:
                num, unit, item = parsed
                update_item(old, num, unit, item)
            elif len(parts) == 1:
                new_item = parts[0]
                con = sqlite3.connect(DB_NAME)
                cur = con.cursor()
                cur.execute("""
                    UPDATE speech_data
                    SET item=?
                    WHERE LOWER(item) LIKE ?
                """, (new_item, f"%{old.lower()}%"))
                count = cur.rowcount
                con.commit()
                con.close()
                speak(f"{count} item renamed to {new_item}")
            else:
                speak("Could not understand update command")
            continue

        # INTERACTIVE UPDATE: "update aachar"
        if english.startswith("update ") and " to " not in english:
            old_item = english.replace("update", "").strip()
            speak(f"Tell me the new value for {old_item}")
            second = listen()
            second_en = translate_to_english(second).lower()
            words2 = second_en.split()

            parsed = parse_number_unit_item(words2)
            if parsed:
                num, unit, item = parsed
                update_item(old_item, num, unit, item)
            else:
                speak("Update failed. Say like two kilo aloo.")
            continue

        # ADD ITEM
        words = english.split()
        parsed = parse_number_unit_item(words)
        if parsed:
            num, unit, item = parsed
            add_item(num, unit, item)
        else:
            speak("Format not understood. Say like two kilo aloo.")

if _name_ == "_main_":
    main()