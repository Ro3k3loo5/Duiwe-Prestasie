import os
import json
import pandas as pd

# Your exact Google Sheet ID
SPREADSHEET_ID = "1ulog31dbsBRfzdl_zNMroCBNwdKh89HwOfXPSEoIDLk"
EXCEL_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
DATA_DIR = "data"

def process_pigeon_data():
    print("📖 Fetching latest data rows from Google Sheets...")
    
    # Matching your exact live sheet tab names case-by-case
    sheets = ["RacePerformance", "Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}

    for sheet in sheets:
        try:
            df = pd.read_excel(EXCEL_URL, sheet_name=sheet)
            df.columns = df.columns.str.strip()  # Clear empty padding spaces
            data_maps[sheet] = df.fillna("")      # Convert blank cells safely to text strings
            print(f"✅ Successfully downloaded tab: {sheet} ({len(df)} rows)")
        except Exception as e:
            print(f"⚠️ Tab tracking error on '{sheet}': {e}")
            data_maps[sheet] = pd.DataFrame()

    # Create the data folder if it vanished
    os.makedirs(DATA_DIR, exist_ok=True)

    # Save the files using the exact lower-case filenames your index.html looks for
    for sheet, df in data_maps.items():
        if sheet == "RacePerformance":
            filename = "race_performance.json"
        elif sheet == "ByRound":
            filename = "byround.json"
        elif sheet == "ByMonth":
            filename = "bymonth.json"
        else:
            filename = f"{sheet.lower()}.json"
            
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")
        print(f"💾 Saved web file: {filename}")
    
    print("🚀 All data matrices refreshed successfully!")

if __name__ == "__main__":
    process_pigeon_data()
