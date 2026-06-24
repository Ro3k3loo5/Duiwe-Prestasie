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
    
    # Load all sheets safely
    try:
        race_perf = pd.read_excel(EXCEL_PATH, sheet_name="RacePerformance")
        chicks = pd.read_excel(EXCEL_PATH, sheet_name="Chicks")
        cocks = pd.read_excel(EXCEL_PATH, sheet_name="Cocks")
        hens = pd.read_excel(EXCEL_PATH, sheet_name="Hens")
        pairs = pd.read_excel(EXCEL_PATH, sheet_name="Pairs")
    except Exception as e:
        print(f"Error reading sheets: {e}")
        return

    print("Running calculations and auto-index mapping...")
    
    # Clear any trailing whitespace from IDs to prevent matching issues
    for df in [race_perf, chicks, cocks, hens, pairs]:
        for col in df.columns:
            if 'ID' in col or 'Ring' in col:
                df[col] = df[col].astype(str).str.strip()

    # 1. Automate Cock stats from Chicks sheet
    if 'CockID' in chicks.columns and 'CockID' in cocks.columns:
        chick_counts = chicks['CockID'].value_counts()
        cocks['Total Chicks'] = cocks['CockID'].map(chick_counts).fillna(0).astype(int)

    # 2. Automate Hen stats from Chicks sheet
    if 'HenID' in chicks.columns and 'HenID' in hens.columns:
        hen_counts = chicks['HenID'].value_counts()
        hens['Total Chicks'] = hens['HenID'].map(hen_counts).fillna(0).astype(int)

    # Clean up NaN (blank values) so JavaScript doesn't break
    cocks = cocks.fillna("")
    hens = hens.fillna("")
    pairs = pairs.fillna("")
    chicks = chicks.fillna("")
    race_perf = race_perf.fillna("")

    # Ensure output directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Save to JSON format for the web dashboard to instantly grab
    cocks.to_json(os.path.join(DATA_DIR, "cocks.json"), orient="records")
    hens.to_json(os.path.join(DATA_DIR, "hens.json"), orient="records")
    pairs.to_json(os.path.join(DATA_DIR, "pairs.json"), orient="records")
    chicks.to_json(os.path.join(DATA_DIR, "chicks.json"), orient="records")
    race_perf.to_json(os.path.join(DATA_DIR, "race_performance.json"), orient="records")
    
    print("All web data matrices updated successfully!")

if __name__ == "__main__":
    process_pigeon_data()
