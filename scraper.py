import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin

# Wired directly to your live Google Sheet ID
SPREADSHEET_ID = "1ulog31dbsBRfzdl_zNMroCBNwdKh89HwOfXPSEoIDLk"
EXCEL_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
DATA_DIR = "data"

# Main Federation Dashboard link to find ALL races dynamically
BENZING_DASHBOARD_URL = "https://mypigeons.benzing.live/za/en/results/2026/o-2-gam-gamtoos-federation/dashboard/"

def get_all_race_urls(dashboard_url):
    print("🔍 Scanning Benzing Dashboard for all active race links...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    race_urls = []
    try:
        response = requests.get(dashboard_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return race_urls
            
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find all hyperlinks on the dashboard page
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Look for links that point directly to an individual race layout
            if '/race/' in href and href not in race_urls:
                # Convert relative links into full web URLs safely
                full_url = urljoin(dashboard_url, href)
                if full_url not in race_urls:
                    race_urls.append(full_url)
        print(f"📋 Found {len(race_urls)} active race(s) on Benzing.")
    except Exception as e:
        print(f"⚠️ Could not scan dashboard for links: {e}")
    return race_urls

def scrape_individual_race(url):
    print(f"🌐 Extracting arrivals from: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    records = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return records
            
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:
                text_data = [c.text.strip() for c in cells]
                # Fallback to identify the race name from the page header if possible
                title_elem = soup.find('h1') or soup.find('h2')
                race_name = title_elem.text.strip() if title_elem else "Live Race"
                
                record = {
                    "Race": race_name.split("\n")[0], # Cleans up dynamic header breaks
                    "Nom": text_data[0] if len(text_data) > 0 else "",
                    "Fancier": text_data[1] if len(text_data) > 1 else "",
                    "PigeonID": text_data[2] if len(text_data) > 2 else "",
                    "Arrival": text_data[3] if len(text_data) > 3 else "",
                    "Speed": text_data[4] if len(text_data) > 4 else "",
                    "Distance": text_data[5] if len(text_data) > 5 else ""
                }
                records.append(record)
    except Exception as e:
        print(f"⚠️ Failed to extract rows from {url}: {e}")
    return records

def process_pigeon_data():
    print("📖 Fetching latest data rows from Google Sheets...")
    sheets = ["RacePerformance", "Chicks", "Cocks", "Hens", "Pairs", "ByRound", "ByMonth", "Summary"]
    data_maps = {}

    # 1. CORE GOOGLE SHEETS DOWNLOAD (Protected)
    for sheet in sheets:
        try:
            df = pd.read_excel(EXCEL_URL, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            data_maps[sheet] = df.fillna("")
            print(f"✅ Downloaded tab: {sheet} ({len(df)} rows)")
        except Exception as e:
            print(f"⚠️ Tab tracking error on '{sheet}': {e}")
            data_maps[sheet] = pd.DataFrame()

    # 2. DYNAMIC MULTI-RACE BENZING SCRAIPING (Isolated so it can never crash the core sheets)
    try:
        all_race_links = get_all_race_urls(BENZING_DASHBOARD_URL)
        all_benzing_records = []
        
        for race_link in all_race_links:
            # Scrape each individual race found on the main dashboard page
            race_data = scrape_individual_race(race_link)
            all_benzing_records.extend(race_data)
            
        if all_benzing_records:
            benzing_df = pd.DataFrame(all_benzing_records)
            
            # Combine your existing local race data with the live scraped data
            if data_maps["RacePerformance"].empty:
                data_maps["RacePerformance"] = benzing_df
            else:
                data_maps["RacePerformance"] = pd.concat([data_maps["RacePerformance"], benzing_df], ignore_index=True).drop_duplicates().fillna("")
            print(f"✅ Combined {len(all_benzing_records)} live Benzing records into RacePerformance data stream.")
    except Exception as master_benzing_err:
        print(f"⚠️ Benzing background sync paused to protect data layout: {master_benzing_err}")

    # 3. SAVE REPOSITORIES
    os.makedirs(DATA_DIR, exist_ok=True)
    for sheet, df in data_maps.items():
        if sheet == "RacePerformance":
            filename = "race_performance.json"
        elif sheet == "ByRound":
            filename = "byround.json"
        elif sheet == "ByMonth":
            filename = "bymonth.json"
        else:
            filename = f"{sheet.lower()}.json"
            
        df.to_json(os.path.join(DATA_DIR, filename), orient="records")
    
    print("🚀 All data matrices refreshed successfully!")

if __name__ == "__main__":
    process_pigeon_data()
