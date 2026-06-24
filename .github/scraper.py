import os
import json
import pandas as pd

EXCEL_PATH = "DUIWE PRESTASIE.xlsx"
DATA_DIR = "data"

def process_pigeon_data():
    if not os.path.exists(EXCEL_PATH):
        print(f"❌ Error: '{EXCEL_PATH}' not found in the root folder!")
        return

    print("📖 Successfully located Excel file. Reading sheets...")
    
    # Safely load each sheet individual to pinpoint exactly where an error happens
    try:
        race_perf = pd.read_excel(EXCEL_PATH, sheet_name="RacePerformance")
        print("✅ Loaded sheet: RacePerformance")
    except Exception as e:
        print(f"❌ Error loading 'RacePerformance' sheet. Check tab name! Details: {e}")
        return

    try:
        chicks = pd.read_excel(EXCEL_PATH, sheet_name="Chicks")
        print("✅ Loaded sheet: Chicks")
    except Exception as e:
        print(f"❌ Error loading 'Chicks' sheet. Details: {e}")
        return

    try:
        cocks = pd.read_excel(EXCEL_PATH, sheet_name="Cocks")
        print("✅ Loaded sheet: Cocks")
    except Exception as e:
        print(f"❌ Error loading 'Cocks' sheet. Details: {e}")
        return

    try:
        hens = pd.read_excel(EXCEL_PATH, sheet_name="Hens")
        print("✅ Loaded sheet: Hens")
    except Exception as e:
        print(f"❌ Error loading 'Hens' sheet. Details: {e}")
        return

    try:
        pairs = pd.read_excel(EXCEL_PATH, sheet_name="Pairs")
        print("✅ Loaded sheet: Pairs")
    except Exception as e:
        print(f"❌ Error loading 'Pairs' sheet. Details: {e}")
        return

    print("⚙️ Running automated background calculations...")

    # Clean trailing whitespaces from column headers
    for df in [race_perf, chicks, cocks, hens, pairs]:
        df.columns = df.columns.str.strip()

    # Calculate totals dynamically
    if 'CockID' in chicks.columns and 'CockID' in cocks.columns:
        cocks['Total Chicks'] = cocks['CockID'].map(chicks['CockID'].value_counts()).fillna(0).astype(int)
    
    if 'HenID' in chicks.columns and 'HenID' in hens.columns:
        hens['Total Chicks'] = hens['HenID'].map(chicks['HenID'].value_counts()).fillna(0).astype(int)

    # Convert spaces/NaNs safely for JSON export
    cocks = cocks.fillna("")
    hens = hens.fillna("")
    pairs = pairs.fillna("")
    chicks = chicks.fillna("")
    race_perf = race_perf.fillna("")

    os.makedirs(DATA_DIR, exist_ok=True)

    # Write output maps
    cocks.to_json(os.path.join(DATA_DIR, "cocks.json"), orient="records")
    hens.to_json(os.path.join(DATA_DIR, "hens.json"), orient="records")
    pairs.to_path = os.path.join(DATA_DIR, "pairs.json")
    pairs.to_json(os.path.join(DATA_DIR, "pairs.json"), orient="records")
    chicks.to_json(os.path.join(DATA_DIR, "chicks.json"), orient="records")
    race_perf.to_json(os.path.join(DATA_DIR, "race_performance.json"), orient="records")
    
    print("🚀 Success! All web matrices generated and ready.")

if __name__ == "__main__":
    process_pigeon_data()
