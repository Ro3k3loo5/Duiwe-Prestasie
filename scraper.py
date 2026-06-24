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
# Using your exact new target page that lists the entire season's itinerary
BENZING_RACES_PAGE_URL = "https://mypigeons.benzing.live/za/en/results/2026/o-2-gam-gamtoos-federation/races/"

def get_google_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("⚠️ GOOGLE_CREDENTIALS secret is missing from GitHub Settings!")
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(creds_json)
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))

def get_active_race_links(races_url):
    print("🔍 Scanning the complete Season Schedule for active rows...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    links_to_scrape = []
    try:
        response = requests.get(races_url, headers=headers, timeout=15)
        if response.status_code != 200: return links_to_scrape
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Benzing lists each race inside individual list-items or distinct block containers
        # We find blocks that contain our keywords, then grab their arrival data links
        for element in soup.find_all(['li', 'div', 'tr']):
            text_content = element.get_text()
            
            # Check for your exact criteria: 'Processed' or 'Being evaluated'
            if "Processed" in text_content or "Being evaluated" in text_content:
                # Inside this active race block, look for the data-table hyperlinks
                for a_tag in element.find_all('a', href=True):
                    href = a_tag['href']
                    # Look for the sub-link that shows arrivals sorted by speed or by pigeons
                    if "By speed" in a_tag.get_text() or "Arrivals" in a_tag.get_text() or "/race/" in href:
                        full_url = urljoin(races_url, href)
                        if full_url not in links_to_scrape:
                            links_to_scrape.append(full_url)
                            
        print(f"📋 Found {len(links_to_scrape)} active race result tables matching your rule.")
    except Exception as e:
        print(f"⚠️ Failed parsing the main schedule page: {e}")
    return links_to_scrape

def scrape_individual_race(url):
    print(f"🌐 Extracting arrivals from: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    records = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return records
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        
        title_elem = soup.find('h1') or soup.find('h2') or soup.find('title')
        race_name = title_elem.text.strip().split("\n")[0] if title_elem else "Live Race"
        # Clean up any leftover menu navigation text from the header string
        race_name = race_name.replace("Races", "").replace("-", "").strip()

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
        print(f"⚠️ Error pulling table from {url}: {e}")
    return records

def process_pigeon_data():
    print("⚙️ Initiating Two-Way Cloud Sync Engine...")
    gc = get_google_sheets_client()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # 1. DOWNLOAD SYSTEM DATA ROWS FOR INTERFACE (Bypassing duplicate warning sheets safely)
    sheets_to_load = ["RacePerformance", "Pairs", "ByRound", "ByMonth"]
    data_maps = {}
    
    for s_name in sheets_to_load:
        try:
            worksheet = spreadsheet.worksheet(s_name)
            df = pd.DataFrame(worksheet.get_all_records())
            df.columns = df.columns.str.strip()
            data_maps[s_name] = df.fillna("")
            print(f"✅ Downloaded current tab: {s_name}")
        except Exception as e:
            print(f"⚠️ Skipping tab layout validation on '{s_name}': {e}")
            data_maps[s_name] = pd.DataFrame()

    # 2. RUN DYNAMIC STATUS CHECK IN THE BACKGROUND
    active_tables = get_active_race_links(BENZING_RACES_PAGE_URL)
    all_scraped_arrivals = []
    for table_url in active_tables:
        all_scraped_arrivals.extend(scrape_individual_race(table_url))

    # 3. COMPARE AND APPEND NEW ARRIVALS BACK TO THE TAB
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
                    arrival["PigeonID"], # ChickID
                    arrival["Distance"], # Distance_km
                    arrival["Speed"],    # Speed_mpm
                ]
                new_rows_to_append.append(new_row)

        if new_rows_to_append:
            print(f"🚀 Appending {len(new_rows_to_append)} new rows directly to Google Sheets...")
            race_perf_sheet.append_rows(new_rows_to_append)
            print("📝 Google Sheet cells populated successfully!")
            
            updated_df = pd.DataFrame(race_perf_sheet.get_all_records())
            data_maps["RacePerformance"] = updated_df.fillna("")
        else:
            print("✨ Google Sheet is completely up to date with the season itinerary.")

    # 4. SAVE CACHED JSON DATA FOR THE WEBSITE VIEW
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
