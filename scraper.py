import os
import json
import pandas as pd

EXCEL_PATH = "DUIWE PRESTASIE.xlsx"
DATA_DIR = "data"

def process_pigeon_data():
    if not os.path.exists(EXCEL_PATH):
        print("❌ Error: Excel data file not found in the root directory!")
        return

    print("📖 Found data file. Extracting all sheets...")
    
    # List of all your tracking sheets
    sheets = ["RacePerformance", "Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}

    for sheet in sheets:
        try:
            df = pd.read_excel(EXCEL_PATH, sheet_name=sheet)
            df.columns = df.columns.str.strip()  # Clean up column header spaces
            data_maps[sheet] = df.fillna("")      # Clean empty cells safely for the web view
            print(f"✅ Loaded sheet: {sheet}")
        except Exception as e:
            print(f"⚠️ Sheet '{sheet}' skipped or not found. Details: {e}")
            # Initialize an empty DataFrame so the website layout doesn't crash if a tab is missing
            data_maps[sheet] = pd.DataFrame()

    print("⚙️ Processing background counts...")

    # Calculate chick totals dynamically for Cocks and Hens if the columns match
    chicks_df = data_maps["Chicks"]
    if not chicks_df.empty:
        if 'CockID' in chicks_df.columns and 'CockID' in data_maps["Cocks"].columns:
            data_maps["Cocks"]['Total Chicks'] = data_maps["Cocks"]['CockID'].map(chicks_df['CockID'].value_counts()).fillna(0).astype(int)
        if 'HenID' in chicks_df.columns and 'HenID' in data_maps["Hens"].columns:
            data_maps["Hens"]['Total Chicks'] = data_maps["Hens"]['HenID'].map(chicks_df['HenID'].value_counts()).fillna(0).astype(int)

    # Ensure output directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Export every layout cleanly to your web data folder
    for sheet, df in data_maps.items():
        # Convert sheet names to lowercase match conventions for web urls
        filename = "race_performance.json" if sheet == "RacePerformance" else f"{sheet.lower()}.json"
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")
    
    print("🚀 Success! All web datasets updated.")

if __name__ == "__main__":
    process_pigeon_data()
