import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import gspread
from google.oauth2.service_account import Credentials
import re
import time

# Configuration
SPREADSHEET_ID = "1ulog31dbsBRfzdl_zNMroCBNwdKh89HwOfXPSEoIDLk"
DATA_DIR = "data"
BENZING_RACES_PAGE_URL = "https://mypigeons.benzing.live/za/en/results/2026/o-2-gam-gamtoos-federation/races/"

def get_google_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("⚠️ GOOGLE_CREDENTIALS secret is missing from GitHub Settings!")
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(creds_json)
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))

def get_all_season_race_slugs(races_url):
    print("🔍 Harvesting all scheduled races from the main calendar page...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    race_list = [] # List of dictionaries holding slug and readable name
    try:
        response = requests.get(races_url, headers=headers, timeout=15)
        if response.status_code != 200: return race_list
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Scan every link on the calendar layout
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Match the pattern you identified: e.g., /results/2026/r-6317-middelburg-1/
            match = re.search(r'/(r-\d+-[^/]+)/', href)
            if match:
                slug = match.group(1)
                # Clean up the display name from the inner tag text
                raw_text = a_tag.get_text().strip()
                race_name = raw_text.split('\n')[0].strip() if raw_text else slug
                # Fallback clean up if text extraction is muddy
                if not race_name or "results" in race_name.lower():
                    race_name = slug.replace("r-", "").replace("-", " ").title()
                    race_name = re.sub(r'^\d+\s+', '', race_name).strip()
                
                # Deduplicate slugs
                if not any(r['slug'] == slug for r in race_list):
                    race_list.append({'slug': slug, 'name': race_name})
                            
        print(f"📋 Found {len(race_list)} total scheduled season races on the board.")
    except Exception as e:
        print(f"⚠️ Failed parsing calendar slugs: {e}")
    return race_list

def scrape_entire_raw_race(race_slug, clean_name):
    """Iterates page-by-page to collect every single data point from the live arrival list."""
    print(f"🌐 Deep scraping raw listings for: {clean_name} ({race_slug})")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    raw_records = []
    page = 1

    while True:
        target_url = f"https://mypigeons.benzing.live/za/en/results/on-the-fly/{race_slug}/by-pigeons/?page={page}"
        print(f"📄 Reading Page {page} -> {target_url}")
        
        try:
            response = requests.get(target_url, headers=headers, timeout=15)
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            arrival_blocks = soup.find_all('div', class_='row no-gutters')
            
            page_records_found = 0
            for block in arrival_blocks:
                # Identify if this row block contains a pigeon ring string sequence
                pigeon_span = block.find('span', text=lambda t: t and ('ZA-' in t or 'ZA ' in t))
                if not pigeon_span:
                    pigeon_span = block.find(lambda tag: tag.name == 'span' and any(yr in tag.text for yr in ['-202', '-201', 'ZA']))
                
                if pigeon_span:
                    pigeon_id = pigeon_span.text.strip()
                    
                    fancier_div = block.find('div', class_='col-5 col-md-5')
                    fancier = fancier_div.text.strip() if fancier_div else "Unknown"
                    
                    arrival_time = "00:00:00"
                    speed = "0.000"
                    distance = "0.000"
                    
                    clock_div = block.find('div', class_='col-12 col-md-8')
                    if clock_div:
                        cols = clock_div.find_all('div', class_=lambda c: c is None or 'text-center' in c or 'right' in c)
                        raw_segments = [c.get_text(strip=True) for c in cols]
                        
                        cleaned_segments = []
                        for seg in raw_segments:
                            cleaned = seg.replace("m/min", "").replace("km", "").strip()
                            if cleaned: cleaned_segments.append(cleaned)
                            
                        if len(cleaned_segments) >= 3:
                            arrival_time = cleaned_segments[0]
                            speed = cleaned_segments[1]
                            distance = cleaned_segments[2]
                    
                    # Deduplicate within this run context
                    if not any(r["PigeonID"] == pigeon_id for r in raw_records):
                        raw_records.append({
                            "Fancier": fancier,
                            "PigeonID": pigeon_id,
                            "Arrival": arrival_time,
                            "Speed": speed,
                            "Distance": distance
                        })
                        page_records_found += 1
            
            if page_records_found == 0:
                break
                
            page += 1
            time.sleep(0.5) # Soft throttling to remain under security firewall radars
            
        except Exception as e:
            print(f"⚠️ Problem processing page {page}: {e}")
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

    # 2. RUN FULL SCHEDULE RAW EXTRACTION
    all_races = get_all_season_race_slugs(BENZING_RACES_PAGE_URL)
    
    for race in all_races:
        # Sheet names have a max limit of 31 characters in Google Sheets
        sheet_title = race['name'][:30].strip()
        
        # Pull raw arrays
        raw_data = scrape_entire_raw_race(race['slug'], race['name'])
        
        if raw_data:
            print(f"🚀 Found {len(raw_data)} arrivals. Syncing directly to sheet: '{sheet_title}'")
            
            # Find or generate the individual blank sheet tab dynamically
            try:
                race_sheet = spreadsheet.worksheet(sheet_title)
                race_sheet.clear() # Clear out previous data to ensure a fresh raw pull
                print(f"🧹 Cleared old records from existing '{sheet_title}' worksheet.")
            except gspread.exceptions.WorksheetNotFound:
                race_sheet = spreadsheet.add_worksheet(title=sheet_title, rows="1000", cols="10")
                print(f"🆕 Created brand new dedicated worksheet tab: '{sheet_title}'")
            
            # Formulate layout row matrix headers
            sheet_matrix = [["Fancier", "PigeonID", "Arrival", "Speed", "Distance"]]
            for bird in raw_data:
                sheet_matrix.append([
                    bird["Fancier"],
                    bird["PigeonID"],
                    bird["Arrival"],
                    bird["Speed"],
                    bird["Distance"]
                ])
                
            # Deliver full block payload instantly via a single API write call
            race_sheet.update('A1', sheet_matrix)
            print(f"✅ Sheet '{sheet_title}' raw upload completed successfully!")
        else:
            print(f"✨ '{race['name']}' returned 0 data points (Planned or empty). Skipping sheet creation.")

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
