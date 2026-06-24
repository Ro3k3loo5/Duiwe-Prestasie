import os
import json
import pandas as pd

# Matching your exact filename on GitHub
EXCEL_PATH = "DUIWE PRESTASIE.xlsx"
DATA_DIR = "data"

def process_pigeon_data():
    if not os.path.exists(EXCEL_PATH):
        # Let's check for lower-case version just in case
        if os.path.exists("duiwe prestasie.xlsx"):
            excel_file = "duiwe prestasie.xlsx"
        else:
            print("❌ Error: Excel data file not found in the root directory!")
            return
    else:
        excel_file = EXCEL_PATH

    print(f"📖 Found data file: {excel_file}. Extracting pigeon sheets...")
    
    try:
        race_perf = pd.read_excel(excel_file, sheet_name="RacePerformance")
        chicks = pd.read_excel(excel_file, sheet_name="Chicks")
        cocks = pd.read_excel(excel_file, sheet_name="Cocks")
        hens = pd.read_excel(excel_file, sheet_name="Hens")
        pairs = pd.read_excel(excel_file, sheet_name="Pairs")
        print("✅ All sheets loaded successfully.")
    except Exception as e:
        print(f"❌ Error reading sheets. Check your sheet tab names! Details: {e}")
        return

    print("⚙️ Processing calculations...")

    # Clean up column header spaces
    for df in [race_perf, chicks, cocks, hens, pairs]:
        df.columns = df.columns.str.strip()

    # Automatically calculate tracked chicks per Cock and Hen
    if 'CockID' in chicks.columns and 'CockID' in cocks.columns:
        cock_counts = chicks['CockID'].value_counts()
        cocks['Total Chicks'] = cocks['CockID'].map(cock_counts)
        
    if 'HenID' in chicks.columns and 'HenID' in hens.columns:
        hen_counts = chicks['HenID'].value_counts()
        hens['Total Chicks'] = hens['HenID'].map(hen_counts)

    # Clean out empty/NaN values so the web player reads them cleanly
    cocks = cocks.fillna("")
    hens = hens.fillna("")
    pairs = pairs.fillna("")
    chicks = chicks.fillna("")
    race_perf = race_perf.fillna("")

    # Ensure output directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Export clean records for your web tables
    cocks.to_json(os.path.join(DATA_DIR, "cocks.json"), orient="records")
    hens.to_json(os.path.join(DATA_DIR, "hens.json"), orient="records")
    pairs.to_json(os.path.join(DATA_DIR, "pairs.json"), orient="records")
    chicks.to_json(os.path.join(DATA_DIR, "chicks.json"), orient="records")
    race_perf.to_json(os.path.join(DATA_DIR, "race_performance.json"), orient="records")
    
    print("🚀 Success! Web data folders successfully populated.")

if __name__ == "__main__":
    process_pigeon_data()
