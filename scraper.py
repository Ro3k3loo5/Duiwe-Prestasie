import os
import json
import pandas as pd

# Wired directly to your live Google Sheet ID
SPREADSHEET_ID = "1ulog31dbsBRfzdl_zNMroCBNwdKh89HwOfXPSEoIDLk"
EXCEL_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
DATA_DIR = "data"

def process_pigeon_data():
    print("📖 Connecting to Live Google Sheet... Fetching latest dataset...")
    
    # The exact tabs inside your Google Sheet
    sheets = ["RacePerformance", "Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}

    for sheet in sheets:
        try:
            df = pd.read_excel(EXCEL_URL, sheet_name=sheet)
            df.columns = df.columns.str.strip()  # Clean up column headers
            data_maps[sheet] = df.fillna("")      # Handle empty cells safely
            print(f"✅ Loaded sheet: {sheet}")
        except Exception as e:
            print(f"⚠️ Sheet '{sheet}' skipped or empty. Details: {e}")
            data_maps[sheet] = pd.DataFrame()

    print("⚙️ Processing background counts...")

    # Safely calculate total chicks per parent if columns match up
    try:
        chicks_df = data_maps["Chicks"]
        if not chicks_df.empty:
            if 'CockID' in chicks_df.columns and 'CockID' in data_maps["Cocks"].columns:
                data_maps["Cocks"]['Total Chicks'] = data_maps["Cocks"]['CockID'].map(chicks_df['CockID'].value_counts()).fillna(0).astype(int)
            if 'HenID' in chicks_df.columns and 'HenID' in data_maps["Hens"].columns:
                data_maps["Hens"]['Total Chicks'] = data_maps["Hens"]['HenID'].map(chicks_df['HenID'].value_counts()).fillna(0).astype(int)
    except Exception as count_err:
        print(f"⚠️ Skipping count calculations: {count_err}")

    # Ensure output directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Export every layout cleanly to your web data folder
    for sheet, df in data_maps.items():
        filename = "race_performance.json" if sheet == "RacePerformance" else f"{sheet.lower()}.json"
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")
    
    print("🚀 Success! All web datasets updated safely from Google Sheet.")

if __name__ == "__main__":
    process_pigeon_data()
