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
# Main page showing the season's itinerary
BENZING_RACES_PAGE_URL = "https://mypigeons.benzing.live/za/en/results/2026/o-2-gam-gamtoos-federation/races/"

def get_google_sheets_client():
    """Authenticates using the encrypted GitHub Secret packet."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("⚠️ GOOGLE_CREDENTIALS secret is missing from GitHub Settings!")
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(creds_json)
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))

def get_active_race_links(races_url):
    """Scans the season schedule and dynamically grabs hyperlinks for active/completed races."""
    print("🔍 Scanning the complete Season Schedule for active rows...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    links_to_scrape = []
    try:
        response = requests.get(races_url, headers=headers, timeout=15)
        if response.status_code != 200: return links_to_scrape
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look at every single structural container block on the schedule table layout
        for row in soup.find_all(['tr', 'div', 'li']):
            text_content = row.get_text()
            # Target rows matching your exact criteria
            if "Processed" in text_content or "Being evaluated" in text_content:
                # Capture every valid hyperlink nested inside that completed block
                for a_tag in row.find_all('a', href=True):
                    href = a_tag['href']
                    if "/race/" in href or "/results/" in href:
                        full_url = urljoin(races_url, href)
                        if full_url not in links_to_scrape:
                            links_to_scrape.append(full_url)
                            
        print(f"📋 Found {len(links_to_scrape)} active race result links matching your status rules.")
    except Exception as e:
        print(f"⚠️ Failed parsing the main schedule page: {e}")
    return links_to_scrape

def scrape_individual_race(url):
    """Downloads a specific live race table and converts it into structured dictionary data."""
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
        # Clean background navigational text tags out of title string
        race_name = race_name.replace("Races", "").replace("-", "").strip()

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >=
