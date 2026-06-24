import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd

EXCEL_PATH = "data/DUIWE_PRESTASIE.xlsx"
BENZING_URL = "https://mypigeons.benzing.live/za/en/results/2026/o-2-gam-gamtoos-federation/dashboard/"

def fetch_benzing_results():
    print("Checking Benzing Live for Gamtoos Federation updates...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(BENZING_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Custom parsing rules for your specific pigeon ring numbers go here
            return [] 
    except Exception as e:
        print(f"Error accessing Benzing Live: {e}")
    return []

def process_breeding_indices():
    if not os.path.exists(EXCEL_PATH):
        print("Excel data file not found. Skipping calculations.")
        return

    print("Recalculating Breeding Performance Metrics...")
    # Read the sheets exactly matching your structural sheets
    race_perf = pd.read_excel(EXCEL_PATH, sheet_name="RacePerformance")
    chicks = pd.read_excel(EXCEL_PATH, sheet_name="Chicks")
    cocks = pd.read_excel(EXCEL_PATH, sheet_name="Cocks")
    hens = pd.read_excel(EXCEL_PATH, sheet_name="Hens")

    # Example Automation: Instead of coping formulas down manually, Python handles it:
    # Count how many chicks each Cock has in the Chicks sheet
    if 'CockID' in chicks.columns and 'CockID' in cocks.columns:
        chick_counts = chicks['CockID'].value_counts()
        cocks['TotalChicks'] = cocks['CockID'].map(chick_counts).fillna(0).astype(int)

    # Ensure output directory exists
    os.makedirs("web/data", exist_ok=True)

    # Save lightweight JSON files for your website frontend to read instantly
    cocks.to_json("web/data/cocks.json", orient="records")
    race_perf.to_json("web/data/race_performance.json", orient="records")
    
    print("Web assets updated successfully.")

if __name__ == "__main__":
    new_results = fetch_benzing_results()
    process_breeding_indices()
