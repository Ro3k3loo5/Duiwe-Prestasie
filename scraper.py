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
TARGET_LOFT = "GEORGE VAN ONSELEN"

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
        if response.status_code != 200: return race_list
        raw_json = response.json()
        races_data = raw_json.get('clubRaces', [])
        for race in races_data:
            race_id = race.get('id')
            race_name = race.get('raceName')
            if race_id and race_name:
                race_list.append({
                    'id': str(race_id),
                    'name': str(race_name).strip(),
                    'date': race.get('raceDate', ''),
                    'total_fed_birds': race.get('numberOfPigeons', 0)
                })
        print(f"📋 API Schedule Scan Found {len(race_list)} total races.")
    except Exception as e:
        print(f"⚠️ Failed reading API schedule: {e}")
    return race_list

def scrape_api_arrivals(race_id):
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_arrivals = []
    page = 1
    limit = 50
    while True:
        target_url = f"https://mypigeons.benzing.live/api/v2/za/club-races/{race_id}/on-the-fly/arrivals?page_number={page}&limit={limit}"
        try:
            response = requests.get(target_url, headers=headers, timeout=15)
            if response.status_code != 200: break
            data = response.json()
            arrivals = data if isinstance(data, list) else data.get('arrivals', [])
            if not arrivals: break
            for index, item in enumerate(arrivals):
                fed_pos = ((page - 1) * limit) + (index + 1)
                all_arrivals.append({
                    "Fancier": str(item.get('fancier_name', 'Unknown')).strip().upper(),
                    "PigeonID": str(item.get('pigeon_string', 'Unknown')).strip(),
                    "Arrival": str(item.get('time_of_arrival', '00:00:00')).strip(),
                    "Speed": str(item.get('speed', '0.000')).strip(),
                    "Distance": str(item.get('distance', '0.000')).strip(),
                    "FedPos": fed_pos
                })
            if len(arrivals) < limit: break
            page += 1
        except:
            break
    return all_arrivals

def process_pigeon_data():
    print("⚙️ Initiating Two-Way Cloud Sync Engine...")
    gc = get_google_sheets_client()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # 1. INDEX MASTER RINGS
    pigeon_lookup_map = {}
    try:
        chicks_sheet = spreadsheet.worksheet("Chicks")
        chicks_raw = chicks_sheet.get_all_values()
        if len(chicks_raw) > 0:
            headers = [str(h).strip() for h in chicks_raw[0]]
            chick_id_idx = headers.index('ChickID') if 'ChickID' in headers else 0
            ring_idx = headers.index('Ring') if 'Ring' in headers else -1
            
            for row in chicks_raw[1:]:
                if len(row) > chick_id_idx:
                    full_chick_id = str(row[chick_id_idx]).strip()
                    if not full_chick_id: continue
                    norm_full = full_chick_id.replace("-", "").replace(" ", "").upper()
                    pigeon_lookup_map[norm_full] = full_chick_id
                    
                    if ring_idx != -1 and len(row) > ring_idx:
                        short_ring = str(row[ring_idx]).strip()
                        if short_ring:
                            pigeon_lookup_map[short_ring.upper()] = full_chick_id
    except Exception as e:
        print(f"❌ Inventory Load Error: {e}")
        return

    # 2. RUN EXTRACTION AND MATCH LEDGER ENTRIES
    all_races = get_all_api_races()
    performance_matrix = [["RaceID", "Date", "RaceName", "FederationTotalBirds", "LoftTotalBirds", "ChickID", "Distance_km", "Speed_mpm", "FederationPos", "LoftPos", "RaceIndex_calc", "LoftRaced In"]]
    row_counter = 2

    for race in all_races:
        arrivals = scrape_api_arrivals(race['id'])
        if not arrivals: continue
        
        # Isolate every single bird clocked by George to figure out his accurate total and rank order
        georges_arrivals = [bird for bird in arrivals if bird["Fancier"] == TARGET_LOFT]
        loft_total_birds = len(georges_arrivals)
        
        if loft_total_birds > 0:
            # Sort George's birds by speed descending to establish true internal loft positions
            georges_arrivals.sort(key=lambda x: float(x["Speed"]) if x["Speed"].replace('.','',1).isdigit() else 0.0, reverse=True)
            
            # Map ranks out dynamically
            for internal_idx, bird in enumerate(georges_arrivals):
                loft_pos = internal_idx + 1
                benz_id = bird["PigeonID"].upper()
                benz_id_clean = benz_id.replace("-", "").replace(" ", "")
                
                matched_chick_id = None
                if benz_id_clean in pigeon_lookup_map:
                    matched_chick_id = pigeon_lookup_map[benz_id_clean]
                else:
                    for key, master_id in pigeon_lookup_map.items():
                        if len(key) <= 5 and (benz_id.endswith("-" + key) or benz_id.endswith(" " + key) or benz_id == key):
                            matched_chick_id = master_id
                            break
                
                # Append row ONLY if this specific bird is part of your Chicks inventory team
                if matched_chick_id:
                    formula_string = f'=IFERROR(((D{row_counter} - I{row_counter} + 1)/D{row_counter} + (E{row_counter} - J{row_counter} + 1)/E{row_counter})/2,"")'
                    performance_matrix.append([
                        race['name'].upper().split()[0], race['date'], race['name'],
                        int(race['total_fed_birds']), int(loft_total_birds), matched_chick_id,
                        float(bird["Distance"]), float(bird["Speed"]), int(bird["FedPos"]),
                        int(loft_pos), formula_string, TARGET_LOFT
                    ])
                    row_counter += 1

    # 3. OVERWRITE RACEPERFORMANCE SHEET SAFELY
    perf_sheet = spreadsheet.worksheet("RacePerformance")
    perf_sheet.batch_clear(["A1:L2000"])
    perf_sheet.update(
        range_name='A1', 
        values=performance_matrix, 
        value_input_option='USER_ENTERED'
    )
    
    if len(performance_matrix) > 1:
        perf_sheet.format(f"K2:K{len(performance_matrix)}", {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}})
        
    print(f"✅ 'RacePerformance' ledger completely rebuilt for {TARGET_LOFT}. Rows synced: {len(performance_matrix) - 1}")

    # 4. DOWNLOAD CACHE DATA FOR APP EXPORT
    sheets_to_load = ["Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary", "RacePerformance"]
    data_maps = {}
    for s_name in sheets_to_load:
        try:
            worksheet = spreadsheet.worksheet(s_name)
            all_rows = worksheet.get_all_values()
            if len(all_rows) > 0:
                raw_headers = [str(h).strip() if h else f"BlankHeader" for h in all_rows[0]]
                clean_headers = []
                counts = {}
                for h in raw_headers:
                    if h in clean_headers:
                        counts[h] = counts.get(h, 0) + 1
                        clean_headers.append(f"{h}_{counts[h]}")
                    else:
                        clean_headers.append(h)
                df = pd.DataFrame(all_rows[1:], columns=clean_headers)
                data_maps[s_name] = df.fillna("")
        except:
            data_maps[s_name] = pd.DataFrame()

    # 5. GENERATE EXPORTS
    os.makedirs(DATA_DIR, exist_ok=True)
    for sheet_name, df in data_maps.items():
        lowered_name = sheet_name.lower().strip()
        if lowered_name == "raceperformance": filename = "race_performance.json"
        elif lowered_name == "byround": filename = "byround.json"
        elif lowered_name == "bymonth": filename = "bymonth.json"
        else: filename = f"{lowered_name}.json"
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")
        
    print("🏁 Full automation sync loop finished successfully.")

if __name__ == "__main__":
    process_pigeon_data()
