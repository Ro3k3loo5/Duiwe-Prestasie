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
            return race_list
        
        raw_json = response.json()
        races_data = raw_json.get('clubRaces', [])
        
        for race in races_data:
            race_id = race.get('id')
            race_name = race.get('raceName')
            race_date = race.get('raceDate', '')
            total_birds = race.get('numberOfPigeons', 0)
            
            if race_id and race_name:
                race_list.append({
                    'id': str(race_id),
                    'name': str(race_name).strip(),
                    'date': race_date,
                    'total_fed_birds': total_birds
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
            if response.status_code != 200:
                break
                
            data = response.json()
            arrivals = data if isinstance(data, list) else data.get('arrivals', [])
            
            if not arrivals:
                break
                
            for index, item in enumerate(arrivals):
                # Calculate absolute federation position based on page and index
                fed_pos = ((page - 1) * limit) + (index + 1)
                
                all_arrivals.append({
                    "Fancier": str(item.get('fancier_name', 'Unknown')).strip(),
                    "PigeonID": str(item.get('pigeon_string', 'Unknown')).strip(),
                    "Arrival": str(item.get('time_of_arrival', '00:00:00')).strip(),
                    "Speed": str(item.get('speed', '0.000')).strip(),
                    "Distance": str(item.get('distance', '0.000')).strip(),
                    "FedPos": fed_pos
                })
                
            if len(arrivals) < limit:
                break
            page += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"⚠️ Error pulling pages: {e}")
            break
            
    return all_arrivals

def process_pigeon_data():
    print("⚙️ Initiating Two-Way Cloud Sync Engine...")
    gc = get_google_sheets_client()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # 1. READ MASTER RING NUMBERS FROM CHICKS SHEET
    try:
        chicks_sheet = spreadsheet.worksheet("Chicks")
        chicks_rows = chicks_sheet.get_all_records()
        # Create a set of your active ring numbers for fast lookup mapping
        my_birds_rings = {str(row.get('Ring', row.get('ChickID', ''))).strip() for row in chicks_rows if row.get('Ring') or row.get('ChickID')}
        print(f"💎 Successfully indexed {len(my_birds_rings)} master rings from 'Chicks' sheet.")
    except Exception as e:
        print(f"❌ Critical error loading your bird inventory from 'Chicks': {e}")
        return

    # 2. CACHE DASHBOARD LAYOUTS FOR BACKEND EXPORTS
    sheets_to_load = ["Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}
    for s_name in sheets_to_load:
        try:
            worksheet = spreadsheet.worksheet(s_name)
            all_rows = worksheet.get_all_values()
            if len(all_rows) > 0:
                headers = [str(h).strip() if h else f"EmptyHeader_{i}" for i, h in enumerate(all_rows[0])]
                df = pd.DataFrame(all_rows[1:], columns=headers)
                data_maps[s_name] = df.fillna("")
        except:
            pass

    # 3. HARVEST AND COMPILE MATCHING RACE LEDGER ENTRIES
    all_races = get_all_api_races()
    performance_matrix = []
    
    # Header definition matching your exact layout
    performance_matrix.append([
        "RaceID", "Date", "RaceName", "FederationTotalBirds", "LoftTotalBirds", 
        "ChickID", "Distance_km", "Speed_mpm", "FederationPos", "LoftPos", 
        "RaceIndex_calc", "Loft"
    ])
    
    row_counter = 2 # Starts at row 2 because line 1 is headings
    
    for race in all_races:
        arrivals = scrape_api_arrivals(race['id'])
        if not arrivals:
            continue
            
        # Filter down to only your birds found in the Chicks inventory list
        my_clocked_birds = [bird for bird in arrivals if bird["PigeonID"] in my_birds_rings]
        loft_total_birds = len(my_clocked_birds)
        
        if loft_total_birds > 0:
            print(f"🚀 Match Found! {race['name']} -> Clocked {loft_total_birds} of your birds out of {len(arrivals)} total entries.")
            
            # Sort your birds by speed descending to correctly compute Loft Position
            my_clocked_birds.sort(key=lambda x: float(x["Speed"]) if x["Speed"].replace('.','',1).isdigit() else 0.0, reverse=True)
            
            for loft_idx, bird in enumerate(my_clocked_birds):
                loft_pos = loft_idx + 1
                
                # Dynamic formula string referencing the correct row index live
                formula_string = f'=IFERROR(((D{row_counter} - I{row_counter} + 1)/D{row_counter} + (E{row_counter} - J{row_counter} + 1)/E{row_counter})/2,"")'
                
                performance_matrix.append([
                    race['name'].upper().split()[0],       # RaceID (e.g., 'KOMGA')
                    race['date'],                         # Date
                    race['name'],                         # RaceName (e.g., 'Komga 1')
                    int(race['total_fed_birds']),         # FederationTotalBirds (Col D)
                    int(loft_total_birds),                # LoftTotalBirds (Col E)
                    bird["PigeonID"],                     # ChickID
                    float(bird["Distance"]),              # Distance_km
                    float(bird["Speed"]),                 # Speed_mpm
                    int(bird["FedPos"]),                  # FederationPos (Col I)
                    int(loft_pos),                        # LoftPos (Col J)
                    formula_string,                       # RaceIndex_calc Formula Text
                    bird["Fancier"]                       # Loft (Fancier Name)
                ])
                row_counter += 1

    # 4. OVERWRITE RACEPERFORMANCE SHEET
    try:
        perf_sheet = spreadsheet.worksheet("RacePerformance")
        perf_sheet.clear()
        perf_sheet.update(range_name='A1', values=performance_matrix)
        print(f"✅ 'RacePerformance' ledger completely rebuilt. Total rows synced: {len(performance_matrix) - 1}")
    except gspread.exceptions.WorksheetNotFound:
        perf_sheet = spreadsheet.add_worksheet(title="RacePerformance", rows="2000", cols="15")
        perf_sheet.update(range_name='A1', values=performance_matrix)
        print("🆕 'RacePerformance' worksheet did not exist. Generated and populated layout.")

    # 5. GENERATE EXPORT FILES FOR APP INTERFACES
    # Append the newly structured ledger data to our JSON cache mapping dictionary
    try:
        final_perf_rows = perf_sheet.get_all_records()
        data_maps["RacePerformance"] = pd.DataFrame(final_perf_rows)
    except:
        pass

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
