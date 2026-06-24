import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import gspread
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = "1ulog31dbsBRfzdl_zNMroCBNwdKh89HwOfXPSEoIDLk"
DATA_DIR = "data"
BENZING_DASHBOARD_URL = "https://mypigeons.benzing.live/za/en/results/2026/o-2-gam-gamtoos-federation/dashboard/"

def get_google_sheets_client():
    """Authenticates using the encrypted GitHub Secret packet."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("⚠️ GOOGLE_CREDENTIALS secret is missing from GitHub Settings!")
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds_dict = json.loads(creds_json)
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)

def get_all_race_urls(dashboard_url):
    print("🔍 Scanning Benzing Dashboard for all active race links...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    race_urls = []
    try:
        response = requests.get(dashboard_url, headers=headers, timeout=15)
        if response.status_code != 200: return race_urls
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/race/' in href:
                full_url = urljoin(dashboard_url, href)
                if full_url not in race_urls: race_urls.append(full_url)
        print(f"📋 Found {len(race_urls)} total race links on Benzing.")
    except Exception as e:
        print(f"⚠️ Dashboard scanning skipped: {e}")
    return race_urls

def scrape_individual_race(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    records = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return records
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        
        title_elem = soup.find('h1') or soup.find('h2')
        race_name = title_elem.text.strip().split("\n")[0] if title_elem else "Live Race"

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:
                text_data = [c.text.strip() for c in cells]
                records.append({
                    "Race": race_name,
                    "Nom": text_data[0],
                    "Fancier": text_data[1],
                    "PigeonID": text_data[2],
                    "Arrival": text_data[3],
                    "Speed": text_data[4],
                    "Distance": text_data[5]
                })
    except Exception as e:
        print(f"⚠️ Error pulling race data from {url}: {e}")
    return records

def process_pigeon_data():
    print("⚙️ Initiating Two-Way Cloud Sync Engine...")
    
    # Authenticate directly with Google Sheets API
    gc = get_google_sheets_client()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # 1. READ ALL CURRENT DATA FROM GOOGLE FOR DASHBOARD
    sheets_to_load = ["RacePerformance", "Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}
    
    for s_name in sheets_to_load:
        try:
            worksheet = spreadsheet.worksheet(s_name)
            df = pd.DataFrame(worksheet.get_all_records())
            df.columns = df.columns.str.strip()
            data_maps[s_name] = df.fillna("")
            print(f"✅ Downloaded current tab: {s_name}")
        except Exception as e:
            print(f"⚠️ Tracking warning on sheet '{s_name}': {e}")
            data_maps[s_name] = pd.DataFrame()

    # 2. FETCH EVERYTHING FROM BENZING LIVE
    live_race_links = get_all_race_urls(BENZING_DASHBOARD_URL)
    all_scraped_arrivals = []
    for link in live_race_links:
        all_scraped_arrivals.extend(scrape_individual_race(link))

    # 3. COMPARE AND AUTOMATICALLY WRITE MISSING ROWS BACK TO GOOGLE SHEET
    if all_scraped_arrivals:
        race_perf_sheet = spreadsheet.worksheet("RacePerformance")
        existing_rows = race_perf_sheet.get_all_values()
        
        # Build an index of what birds/races already exist in his sheet to prevent duplicates
        existing_keys = set()
        if len(existing_rows) > 0:
            headers = [h.strip() for h in existing_rows[0]]
            pigeon_idx = headers.index("PigeonID") if "PigeonID" in headers else -1
            race_idx = headers.index("RaceName") if "RaceName" in headers else (headers.index("Race") if "Race" in headers else -1)
            
            for row in existing_rows[1:]:
                p_id = row[pigeon_idx] if pigeon_idx < len(row) else ""
                r_id = row[race_idx] if race_idx < len(row) else ""
                if p_id and r_id:
                    existing_keys.add((p_id.strip(), r_id.strip()))

        # Filter out anything your brother doesn't have yet (like the June 20th results!)
        new_rows_to_append = []
        for arrival in all_scraped_arrivals:
            key = (arrival["PigeonID"], arrival["Race"])
            if key not in existing_keys:
                # Map the scraped values directly to match his sheet's column structure
                new_row = [
                    "",                  # RaceID (Leave blank or manual fill)
                    "",                  # Date
                    arrival["Race"],     # RaceName
                    "",                  # Federation Total Birds
                    "",                  # Loft Total Birds
                    arrival["PigeonID"], # ChickID / Ring
                    arrival["Distance"], # Distance_km
                    arrival["Speed"],    # Speed_mpm
                ]
                new_rows_to_append.append(new_row)

        if new_rows_to_append:
            print(f"🚀 Found {len(new_rows_to_append)} missing race rows (including June 20th). Appending directly to Google Sheets...")
            race_perf_sheet.append_rows(new_rows_to_append)
            print("📝 Google Sheet cells updated successfully!")
            
            # Refresh local dataset cache so the webpage gets it instantly too
            updated_df = pd.DataFrame(race_perf_sheet.get_all_records())
            data_maps["RacePerformance"] = updated_df.fillna("")
        else:
            print("✨ Google Sheet is already fully up to date with all Benzing records.")

    # 4. SAVE LOCAL REFRESHED PACKETS FOR MOBILE WEB
    os.makedirs(DATA_DIR, exist_ok=True)
    for sheet_name, df in data_maps.items():
        if sheet_name == "RacePerformance": filename = "race_performance.json"
        elif sheet_name == "ByRound": filename = "byround.json"
        elif sheet_name == "ByMonth": filename = "bymonth.json"
        else: filename = f"{sheet_name.lower()}.json"
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")

    print("🏁 Automation loop finished successfully.")

if __name__ == "__main__":
    process_pigeon_data()
