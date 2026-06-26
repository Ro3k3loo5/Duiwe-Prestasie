import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin, urlparse
import gspread
from google.oauth2.service_account import Credentials
import re

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

def get_active_race_slugs(races_url):
    print("🔍 Scanning the complete Season Schedule for active race identifiers...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    race_slugs = []
    try:
        response = requests.get(races_url, headers=headers, timeout=15)
        if response.status_code != 200: return race_slugs
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Locate all structural rows on the schedule board
        for row in soup.find_all(['tr', 'div', 'li']):
            text_content = row.get_text()
            # Process rows flagged as completed or currently active
            if "Processed" in text_content or "Being evaluated" in text_content:
                for a_tag in row.find_all('a', href=True):
                    href = a_tag['href']
                    # Extract the unique race identifier slug (e.g., r-6317-middelburg-1)
                    match = re.search(r'/(r-\d+-[^/]+)/', href)
                    if match:
                        slug = match.group(1)
                        if slug not in race_slugs:
                            race_slugs.append(slug)
                            
        print(f"📋 Found {len(race_slugs)} active race slugs matching your rules: {race_slugs}")
    except Exception as e:
        print(f"⚠️ Failed parsing the main schedule page: {e}")
    return race_slugs

def scrape_on_the_fly_race(race_slug):
    """Loops through all pagination pages for a specific race slug using your exact HTML grid layout."""
    print(f"🌐 Commencing multi-page deep extraction for race: {race_slug}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    records = []
    page = 1
    
    # Human-friendly clean title extraction from slug string
    race_clean_name = race_slug.replace("r-", "").replace("-", " ").title()
    # Strip leading tracking numbers from the name if present
    race_clean_name = re.sub(r'^\d+\s+', '', race_clean_name).strip()

    while True:
        target_url = f"https://mypigeons.benzing.live/za/en/results/on-the-fly/{race_slug}/by-pigeons/?page={page}"
        print(f"📄 Scraping Page {page} -> {target_url}")
        
        try:
            response = requests.get(target_url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"🛑 Page {page} not found or blocked. Moving to next dataset.")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Target the outer container rows matching your element block profile
            arrival_blocks = soup.find_all('div', class_='row no-gutters')
            
            page_records_found = 0
            for block in arrival_blocks:
                # To prevent cross-contamination, confirm this sub-block contains a unique pigeon ID layout block
                pigeon_span = block.find('span', text=lambda t: t and ('ZA-' in t or 'ZA ' in t))
                if not pigeon_span:
                    # Alternative deep hunt for nested ring configurations
                    pigeon_span = block.find(lambda tag: tag.name == 'span' and any(yr in tag.text for yr in ['-202', '-201', 'ZA']))
                
                if pigeon_span:
                    pigeon_id = pigeon_span.text.strip()
                    
                    # Target layout column markers matching your exact inspect specifications
                    fancier_div = block.find('div', class_='col-5 col-md-5')
                    fancier = fancier_div.text.strip() if fancier_div else "Unknown"
                    
                    # Deep dive parsing for time text blocks, skipping structural clock icons
                    clock_div = block.find('div', class_='col-12 col-md-8')
                    arrival_time = "00:00:00"
                    speed = "0.000"
                    distance = "0.000"
                    
                    if clock_div:
                        cols = clock_div.find_all('div', class_=lambda c: c is None or 'text-center' in c or 'right' in c)
                        # Clean inner data structures out of responsive display blocks
                        raw_segments = [c.get_text(strip=True) for c in cols]
                        
                        # Strip standard sub-labels to leave pure numerical data
                        cleaned_segments = []
                        for seg in raw_segments:
                            cleaned = seg.replace("m/min", "").replace("km", "").strip()
                            if cleaned: cleaned_segments.append(cleaned)
                            
                        if len(cleaned_segments) >= 3:
                            arrival_time = cleaned_segments[0]
                            speed = cleaned_segments[1]
                            distance = cleaned_segments[2]
                    
                    # Prevent tracking duplications from responsive duplicate elements on same grid line
                    record_key = (pigeon_id, race_clean_name)
                    if not any(r["PigeonID"] == pigeon_id and r["Race"] == race_clean_name for r in records):
                        records.append({
                            "Race": race_clean_name,
                            "Nom": "", 
                            "Fancier": fancier,
                            "PigeonID": pigeon_id,
                            "Arrival": arrival_time,
                            "Speed": speed,
                            "Distance": distance
                        })
                        page_records_found += 1
            
            print(f"🎯 Successfully extracted {page_records_found} entries from page {page}.")
            
            # Break condition: If a page contains no visible bird configurations, pagination is complete
            if page_records_found == 0:
                print(f"🏁 Reached pagination limit for {race_clean_name}.")
                break
                
            page += 1
            
        except Exception as e:
            print(f"⚠️ Error handling dataset compilation on page {page}: {e}")
            break
            
    return records

def process_pigeon_data():
    print("⚙️ Initiating Two-Way Cloud Sync Engine...")
    gc = get_google_sheets_client()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # 1. DOWNLOAD INTERFACE CACHE VALUES (Bypassing messy duplicate columns natively)
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
                print(f"✅ Downloaded current tab successfully: {s_name}")
            else:
                data_maps[s_name] = pd.DataFrame()
        except Exception as e:
            print(f"⚠️ Tracking warning on sheet '{s_name}': {e}")
            data_maps[s_name] = pd.DataFrame()

    # 2. RUN HARVEST SCRIPT VIA THE DYNAMIC ON-THE-FLY ENGINE
    active_slugs = get_active_race_slugs(BENZING_RACES_PAGE_URL)
    all_scraped_arrivals = []
    for slug in active_slugs:
        all_scraped_arrivals.extend(scrape_on_the_fly_race(slug))

    # 3. APPEND NEW ENTRIES DIRECTLY INTO YOUR SPREADSHEET CELLS
    if all_scraped_arrivals:
        race_perf_sheet = spreadsheet.worksheet("RacePerformance")
        existing_rows = race_perf_sheet.get_all_values()
        
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

        new_rows_to_append = []
        for arrival in all_scraped_arrivals:
            key = (arrival["PigeonID"], arrival["Race"])
            if key not in existing_keys:
                new_row = [
                    "",                  # RaceID
                    "",                  # Date
                    arrival["Race"],     # RaceName
                    "",                  # Federation Total Birds
                    "",                  # Loft Total Birds
                    arrival["PigeonID"], # ChickID/PigeonID
                    arrival["Distance"], # Distance_km
                    arrival["Speed"],    # Speed_mpm
                ]
                new_rows_to_append.append(new_row)

        if new_rows_to_append:
            print(f"🚀 Appending {len(new_rows_to_append)} brand new race tracking lines directly to Google Sheets...")
            race_perf_sheet.append_rows(new_rows_to_append)
            print("📝 Google Sheet cells populated successfully!")
            
            # Force cache reload to populate the website instantly
            all_rows_updated = race_perf_sheet.get_all_values()
            headers_updated = [str(h).strip() if h else f"EmptyHeader_{i}" for i, h in enumerate(all_rows_updated[0])]
            seen_u = {}
            for idx, h in enumerate(headers_updated):
                if h in seen_u:
                    seen_u[h] += 1
                    headers_updated[idx] = f"{h}_{seen_u[h]}"
                else:
                    seen_u[h] = 0
            data_maps["RacePerformance"] = pd.DataFrame(all_rows_updated[1:], columns=headers_updated).fillna("")
        else:
            print("✨ Google Sheet is completely current with all active flights.")

    # 4. EXPORT COPIES FOR MOBILE FRONTEND DISPLAY
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
