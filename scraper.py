import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Your live Google Sheet ID
SPREADSHEET_ID = "1ulog31dbsBRfzdl_zNMroCBNwdKh89HwOfXPSEoIDLk"
EXCEL_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
DATA_DIR = "data"

# Direct Benzing URL for Colesberg 2
BENZING_RACE_URL = "https://mypigeons.benzing.live/za/en/results/2026/o-2-gam-gamtoos-federation/race/7/"

def scrape_benzing_race(url):
    print(f"🌐 Fetching live data from Benzing: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Could not reach Benzing (Status {response.status_code})")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        race_records = []
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:
                text_data = [c.text.strip() for c in cells]
                record = {
                    "Nom": text_data[0] if len(text_data) > 0 else "",
                    "Fancier": text_data[1] if len(text_data) > 1 else "",
                    "PigeonID": text_data[2] if len(text_data) > 2 else "",
                    "Arrival": text_data[3] if len(text_data) > 3 else "",
                    "Speed": text_data[4] if len(text_data) > 4 else "",
                    "Distance": text_data[5] if len(text_data) > 5 else ""
                }
                race_records.append(record)
                
        print(f"✅ Successfully extracted {len(race_records)} arrivals from Benzing.")
        return race_records
    except Exception as e:
        print(f"⚠️ Warning: Benzing scraping engine encountered a hitch: {e}")
        return []

def process_pigeon_data():
    print("📖 Connecting to Live Google Sheet Engine... Fetching latest sheets...")
    
    # Exact tab names from your Google Sheet
    sheets = ["RacePerformance", "Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}

    for sheet in sheets:
        try:
            df = pd.read_excel(EXCEL_URL, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            data_maps[sheet] = df.fillna("")
            print(f"✅ Processed live cloud sheet: {sheet}")
        except Exception as e:
            print(f"⚠️ Sheet '{sheet}' skipped or empty. Details: {e}")
            data_maps[sheet] = pd.DataFrame()

    # --- SAFE BENZING SYNC INJECTION ---
    try:
        benzing_data = scrape_benzing_race(BENZING_RACE_URL)
        if benzing_data:
            benzing_df = pd.DataFrame(benzing_data)
            if data_maps["RacePerformance"].empty:
                data_maps["RacePerformance"] = benzing_df
            else:
                # Safely combine data without breaking on schema differences
                data_maps["RacePerformance"] = pd.concat([data_maps["RacePerformance"], benzing_df], ignore_index=True).drop_duplicates().fillna("")
            print("✅ Integrated Benzing rows into RacePerformance data stream.")
    except Exception as benzing_err:
        print(f"⚠️ Benzing integration skipped to protect core data. Reason: {benzing_err}")

    # --- DYNAMIC COUNTS PROCESSING ---
    try:
        chicks_df = data_maps["Chicks"]
        if not chicks_df.empty:
            if 'CockID' in chicks_df.columns and 'CockID' in data_maps["Cocks"].columns:
                data_maps["Cocks"]['Total Chicks'] = data_maps["Cocks"]['CockID'].map(chicks_df['CockID'].value_counts()).fillna(0).astype(int)
            if 'HenID' in chicks_df.columns and 'HenID' in data_maps["Hens"].columns:
                data_maps["Hens"]['Total Chicks'] = data_maps["Hens"]['HenID'].map(chicks_df['HenID'].value_counts()).fillna(0).astype(int)
    except Exception as count_err:
        print(f"⚠️ Dynamic counts calculation skipped: {count_err}")

    # --- SAVE ALL JSON DATA GENERATIONS ---
    os.makedirs(DATA_DIR, exist_ok=True)
    for sheet, df in data_maps.items():
        filename = "race_performance.json" if sheet == "RacePerformance" else f"{sheet.lower()}.json"
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")
    
    print("🚀 Success! All sheets written to web directory.")

if __name__ == "__main__":
    process_pigeon_data()
