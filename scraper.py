import os
import json
import pandas as pd

EXCEL_PATH = "DUIWE PRESTASIE.xlsx"
DATA_DIR = "data"

def process_pigeon_data():
    if not os.path.exists(EXCEL_PATH):
        print(f"Error: {EXCEL_PATH} not found in the root directory!")
        return

    print("Reading sheets from DUIWE PRESTASIE.xlsx...")
    
    try:
        # Load sheets matching your exact workbook structures
        race_perf = pd.read_excel(EXCEL_PATH, sheet_name="RacePerformance")
        chicks = pd.read_excel(EXCEL_PATH, sheet_name="Chicks")
        cocks = pd.read_excel(EXCEL_PATH, sheet_name="Cocks")
        hens = pd.read_excel(EXCEL_PATH, sheet_name="Hens")
        pairs = pd.read_excel(EXCEL_PATH, sheet_name="Pairs")
    except Exception as e:
        print(f"Error reading sheet names. Please check matching names: {e}")
        return

    print("Running background calculations...")

    # Helper to clean up column whitespace
    for df in [race_perf, chicks, cocks, hens, pairs]:
        df.columns = df.columns.str.strip()

    # Safely calculate Chick counts for Cocks
    if 'CockID' in chicks.columns and 'CockID' in cocks.columns:
        chick_counts = chicks['CockID'].value_counts()
        cocks['Total Chicks'] = cocks['CockID'].map(chick_counts)
    
    # Safely calculate Chick counts for Hens
    if 'HenID' in chicks.columns and 'HenID' in hens.columns:
        hen_counts = chicks['HenID'].value_counts()
        hens['Total Chicks'] = hens['HenID'].map(hen_counts)

    # Clean missing values so the web tables don't break
    cocks = cocks.fillna("")
    hens = hens.fillna("")
    pairs = pairs.fillna("")
    chicks = chicks.fillna("")
    race_perf = race_perf.fillna("")

    # Create storage folder if missing
    os.makedirs(DATA_DIR, exist_ok=True)

    # Save to your output directory
    cocks.to_json(os.path.join(DATA_DIR, "cocks.json"), orient="records")
    hens.to_json(os.path.join(DATA_DIR, "hens.json"), orient="records")
    pairs.to_json(os.path.join(DATA_DIR, "pairs.json"), orient="records")
    chicks.to_json(os.path.join(DATA_DIR, "chicks.json"), orient="records")
    race_perf.to_json(os.path.join(DATA_DIR, "race_performance.json"), orient="records")
    
    print("Success! Data layers extracted safely.")

if __name__ == "__main__":
    process_pigeon_data()
