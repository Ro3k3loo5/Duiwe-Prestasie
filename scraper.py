import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# Configuration
SPREADSHEET_ID = "1ulog31dbsBRfzdl_zNMroCBNwdKh89HwOfXPSEoIDLk"
DATA_DIR = "data"
BENZING_API_RACES_URL = "https://mypigeons.benzing.live/api/v2/za/smartclub/2/2026/races"

def get_google_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("⚠️ GOOGLE_CREDENTIALS secret is missing from GitHub Settings!")
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(creds_json)
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))

def get_all_api_races():
    print("🔍 Fetching season schedule directly from Benzing API...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    race_list = []
    try:
        response = requests.get(BENZING_API_RACES_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"❌ API Rejected request. Status: {response.status_code}")
            return race_list
        
        # --- DIAGNOSTIC PRINT ---
        # This logs the exact layout Benzing sends back so we can map keys perfectly
        raw_json = response.json()
        print("====== RAW BENZING API DATA RESPONSE ======")
        print(json.dumps(raw_json, indent=2)[:3000])
        print("===========================================")
        
        # Attempt defensive nested parsing loops
        races_data = []
        if isinstance(raw_json, list):
            races_data = raw_json
        elif isinstance(raw_json, dict):
            # Check common key wrappers
            for key in ['data', 'races', 'result', 'flights', 'smartclub']:
                if key in raw_json:
                    if isinstance(raw_json[key], list):
                        races_data = raw_json[key]
                        break
                    elif isinstance(raw_json[key], dict) and 'races' in raw_json[key]:
                        races_data = raw_json[key]['races']
                        break
            if not races_data and 'races' not in raw_json:
                # If it's a flat dict with multiple items, check if it's iterable
                races_data = raw_json.get('data', [])

        for race in races_data:
            if isinstance(race, dict):
                race_id = race.get('id') or race.get('race_id') or race.get('club_race_id')
                race_name = race.get('name') or race.get('station_name') or race.get('title')
                
                if race_id and race_name:
                    race_list.append({
                        'id': str(race_id),
                        'name': str(race_name).strip()
                    })
                
        print(f"📋 API Schedule Scan Found {len(race_list)} total races.")
    except Exception as e:
        print(f"⚠️ Failed reading API schedule: {e}")
    return race_list

def scrape_api_arrivals(race_id, race_name):
    print(f"🌐 Deep pulling arrivals from API for: {race_name} (ID: {race_id})")
    headers = {'User-Agent': 'Mozilla/5.0'}
    raw_records = []
    page = 1
    limit = 50

    while True:
        target_url = f"https://mypigeons.benzing.live/api/v2/za/club-races/{race_id}/on-the-fly/arrivals?page_number={page}&limit={limit}"
        print(f"📄 Requesting Page {page} -> {target_url}")
        
        try:
            response = requests.get(target_url, headers=headers, timeout=15)
            if response.status_code != 200:
                break
                
            data = response.json()
            arrivals = data if isinstance(data, list) else data.get('arrivals', data.get('data', []))
            
            if not arrivals or len(arrivals) == 0:
                print(f"🏁 No records found on page {page}. Finishing race collection.")
                break
                
            page_count = 0
            for item in arrivals:
                # Dynamically extract values based on raw Benzing field patterns
                fancier = item.get('fancier_name') or item.get('fancier', {}).get('name', 'Unknown')
                pigeon_id = item.get('pigeon_id') or item.get('pigeon_ring') or item.get('ring_number') or item.get('pigeon', {}).get('ring', 'Unknown')
                arrival_time = item.get('arrival_time') or item.get('arrival', '00:00:00')
                speed = item.get('speed') or item.get('m_min', '0.000')
                distance = item.get('distance') or item.get('km', '0.000')
                
                raw_records.append({
                    "Fancier": str(fancier).strip(),
                    "PigeonID": str(pigeon_id).strip(),
                    "Arrival": str(arrival_time).strip(),
                    "Speed": str(speed).strip(),
                    "Distance": str(distance).strip()
                })
                page_count += 1
                
            print(f"🎯 Extracted {page_count} rows from page {page}.")
            
            # If the page returned fewer items than the limit, we've reached the final page
            if page_count < limit:
                break
                
            page += 1
            time.sleep(0.3)
            
        except Exception as e:
            print(f"⚠️ Error parsing arrivals api payload on page {page}: {e}")
            break
            
    return raw_records

def process_pigeon_data():
    print("⚙️ Initiating Two-Way Cloud Sync Engine...")
    gc = get_google_sheets_client()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # 1. PRESERVE AND DOWNLOAD SYSTEM DASHBOARD INTERFACES
    sheets_to_load = ["RacePerformance", "Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}
    
    for s_name in sheets_to_load:
        try:
            worksheet = spreadsheet.worksheet(s_name)
            all_rows = worksheet.get_all_values()
            if len(all_rows) > 0:
                headers = [str(h).strip() if h else f"EmptyHeader_{i}" for i, h in enumerate(all_rows[0])]
                seen = {}
                for idx, h in enumerate(headers):
                    if h in seen:
                        seen[h] += 1
                        headers[idx] = f"{h}_{seen[h]}"
                    else:
                        seen[h] = 0
                df = pd.DataFrame(all_rows[1:], columns=headers)
                data_maps[s_name] = df.fillna("")
            else:
                data_maps[s_name] = pd.DataFrame()
        except Exception as e:
            data_maps[s_name] = pd.DataFrame()

    # 2. RUN FULL SCHEDULE RAW EXTRACTION VIA DISCOVERED API LINKS
    all_races = get_all_api_races()
    
    for race in all_races:
        sheet_title = race['name'][:30].strip()
        raw_data = scrape_api_arrivals(race['id'], race['name'])
        
        if raw_data:
            print(f"🚀 Found {len(raw_data)} arrivals. Syncing directly to sheet: '{sheet_title}'")
            
            try:
                race_sheet = spreadsheet.worksheet(sheet_title)
                race_sheet.clear()
                print(f"🧹 Cleared old records from existing '{sheet_title}' worksheet.")
            except gspread.exceptions.WorksheetNotFound:
                race_sheet = spreadsheet.add_worksheet(title=sheet_title, rows="1000", cols="10")
                print(f"🆕 Created brand new dedicated worksheet tab: '{sheet_title}'")
            
            sheet_matrix = [["Fancier", "PigeonID", "Arrival", "Speed", "Distance"]]
            for bird in raw_data:
                sheet_matrix.append([
                    bird["Fancier"],
                    bird["PigeonID"],
                    bird["Arrival"],
                    bird["Speed"],
                    bird["Distance"]
                ])
                
            race_sheet.update('A1', sheet_matrix)
            print(f"✅ Sheet '{sheet_title}' raw upload completed successfully!")
        else:
            print(f"✨ '{race['name']}' returned 0 data points from API. Skipping sheet execution.")

    # 3. COMPILING EXPORT FILES FOR APP VISUALIZATION LAYOUTS
    os.makedirs(DATA_DIR, exist_ok=True)
    for sheet_name, df in data_maps.items():
        lowered_name = sheet_name.lower().strip()
        if lowered_name == "raceperformance": filename = "race_performance.json"
        elif lowered_name == "byround": filename = "byround.json"
        elif lowered_name == "bymonth": filename = "bymonth.json"
        else: filename = f"{lowered_name}.json"
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")

    print("🏁 Automation loop finished successfully.")

if __name__ == "__main__":
    process_pigeon_data()
