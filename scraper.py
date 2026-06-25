from bs4 import BeautifulSoup
from math import radians, cos, sin, asin, sqrt
from run import random_delay
from playwright.sync_api import sync_playwright

import requests
import re
import pandas as pd
import os
from datetime import datetime

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

class Scraper:
    def __init__(self, max_price, beds, search_url):
        self.max_price = max_price
        self.beds = beds
        self.search_url = search_url
        self.base_url = None
        self.listings = list()

    def get_listings(self):
        return self.listings
    
    def get_url(self):
        return self.base_url
    
    def paginate_url(self, url, page_number):
        return None if not url else f"{url}&page={page_number}" if "?" in url else f"{url}?page={page_number}"
    
    def scrape_page(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses

            random_delay(0.05, 0.2)

            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
        
        except requests.RequestException as e:
            print(f"Error scraping website: {e}")
            return None

    def scrape_website(self, url):
        page_number = 1
        new_url = self.paginate_url(url, page_number)
        soups = []

        while True:
            try:
                response = requests.get(new_url)

                if response.url == self.base_url:
                    return soups 

                response.raise_for_status()  # Raise an error for bad responses

                random_delay(0.05, 0.2)

                soup = BeautifulSoup(response.text, 'html.parser')
                
                if soup:
                    soups.append(soup) 
            
            except requests.RequestException as e:
                print(f"Error scraping website: {e}")
                return None
            
            page_number += 1
            new_url = self.paginate_url(url, page_number)

    def sort_listings(self, target_date=None):
        self.listings = sorted(self.listings, key=lambda x: x['bathrooms'], reverse=True)

        target_date = datetime(*[int(x) for x in target_date.split('-')]) if target_date else None
        if target_date:
            self.listings = sorted(self.listings, key=lambda x : self.date_distance(target_date, x))

        self.listings = sorted(self.listings, key=lambda x: x['price'], reverse=False)

    def filter_listings(self, bills_required=None, central_location=None, hmo_required=None, max_distance_km=100, move_in_date=None):
        self.advanced_extract()
        self.advanced_filter(bills_required, central_location, hmo_required, max_distance_km)
        self.sort_listings(move_in_date)

    def get_postcode_coordinates(self, postcode):
            POSTCODE_COORDINATES_CSV = 'data/NSPL_MAY_2025_UK_EH.csv'  # Path to your CSV file with postcode coordinates
            df = pd.read_csv(POSTCODE_COORDINATES_CSV)  # Assuming you have a CSV file with postcode coordinates
            row = df[df['pcd'] == postcode]
            
            return (float(row['lat'].iloc[0]), float(row['long'].iloc[0])) if not row.empty else None

    def measure_distance(self, location1, postcode): #location given in (latitude, longitude) format
        location2 = self.get_postcode_coordinates(postcode)
        if location2 is None or location2[0] is None or location2[1] is None:
            return float('inf')  # Return a large distance if postcode is invalid
        
        EARTH_RADIUS_KM = 6371  # Radius of the Earth in kilometers
        lat1, lon1 = location1[0], location1[1]
        lat2, lon2 = location2[0], location2[1]

        # Haversine formula to calculate the great-circle distance
        lat1, lon1, lat2, lon2 = radians(lat1), radians(lon1), radians(lat2), radians(lon2)
        lon_diff = lon2 - lon1
        lat_diff = lat2 - lat1

        distance = 2 * EARTH_RADIUS_KM * asin(sqrt(sin(lat_diff / 2) ** 2 + cos(lat1) * cos(lat2) * sin(lon_diff / 2) ** 2))
        return distance

    def in_proximity(self, postcode, central_location, max_distance_km=2):
        distance = self.measure_distance(central_location, postcode)
        return distance <= max_distance_km 
    
    def get_dataframe(self):
        df = pd.DataFrame(self.listings)
        return df
    
    def save_to_csv(self, filename):
        if self.listings:
            listings = pd.DataFrame(self.listings)
            # Ensure property_id is stored as a string to match scraped IDs
            if 'property_id' in listings.columns:
                listings['property_id'] = listings['property_id'].astype(str)
            tmp = filename + '.tmp'
            listings.to_csv(tmp, index=False)
            os.replace(tmp, filename)


class UniHomesScraper(Scraper):

    def __init__(self, max_price, beds):
        BASE = "https://www.unihomes.co.uk/student-accommodation/edinburgh"

        # Build URL with filters baked in
        search_url = f"{BASE}?bedrooms={beds}&max-price={max_price}&type=house%2Capartment"
        super().__init__(max_price, beds, search_url)
        
        self.base_url = BASE

    def extract_listings(self):
        final_listings = []
        soups = self.scrape_website(self.search_url)
        
        for soup in soups:
            for listing in soup.select('div.property'):
                property_id = listing.find_parent('div', attrs={'data-id': True})['data-id'] if listing.find_parent('div', attrs={'data-id': True}) else None
                url = listing.select_one('a[data-cy="property-listing"]')['href'] if listing.select_one('a[data-cy="property-listing"]') else None
                title = listing.select_one('h2').get_text(strip=True) if listing.select_one('h2') else None
                price = float(listing.select_one('span:-soup-contains("£")').get_text(strip=True).replace('£', '').replace(',', '')) if listing.select_one('span:-soup-contains("£")') else None
                availability = "".join(listing.select_one('h4').get_text(strip=True).splitlines(True)[1:]).strip() if listing.select_one('h4') else None
                bathrooms = int(listing.select_one('span:-soup-contains("bathrooms")').get_text(strip=True)[0]) if listing.select_one('span:-soup-contains("bathrooms")') else None
                
                final_listings.append({
                    'property_id': property_id,
                    'url': url,
                    'title': title,
                    'price': price,
                    'availability': availability,
                    'bathrooms': bathrooms
                })
            
            #availability,has_gas,has_electricity,has_broadband,has_tv_licence,bills_included,postcode,is_hmo
        
        self.listings = final_listings

    def date_distance(self, target_date, listing):
        availability = listing.get('availability', '')
        try:
            # Parses "available from 22nd July 2026"
            cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', availability)
            date = datetime.strptime(cleaned.strip(), "available from %d %B %Y")
            return abs((date - target_date).days)
        except:
            return float('inf')  # Push unparseable dates to the end

    def advanced_extract(self):
        for listing in self.listings:
            url = listing['url']
            scraped_soup = self.scrape_page(url)

            if not scraped_soup:
                return 
        
            bills_section = scraped_soup.find('div', attrs={'dusk': "included-utility-bills"})
            if bills_section:
                if bills_section:
                    has_gas = bool(bills_section.find(attrs={'dusk': 'utility-gas'}))
                    has_electricity = bool(bills_section.find(attrs={'dusk': 'utility-electricity'}))
                    has_broadband   = bool(bills_section.find(attrs={'dusk': 'utility-internet'}))
                    has_tv_licence  = bool(bills_section.find(attrs={'dusk': 'utility-tv-license'}))
                    
                    listing.update({
                        'has_gas': has_gas,
                        'has_electricity': has_electricity,
                        'has_broadband': has_broadband,
                        'has_tv_licence': has_tv_licence,
                    })


                bills_included = [span.get_text(strip=True) for span in bills_section.select('span') if span.get_text(strip=True)]
                listing['bills_included'] = bills_included
                # bills = ['Gas', 'Electricity', 'Broadband', 'TV licence']

            is_hmo = self.is_hmo_check(scraped_soup)
            postcode = self.get_postcode(scraped_soup.find('meta', attrs={'name': 'description'})['content']) if scraped_soup.find('meta', attrs={'name': 'description'}) else None

            listing.update({
                'postcode': postcode,
                'is_hmo': is_hmo,
            })

    def advanced_filter(self, bills_required=None, central_location=None, hmo_required=None, max_distance_km=100):
        filtered_listings = []
        for listing in self.listings:
            if bills_required:
                if not all(listing.get(bill, False) for bill in bills_required):
                    continue

            if not central_location or not self.in_proximity(listing.get('postcode'), central_location, max_distance_km):
                continue

            if hmo_required and not listing.get('is_hmo', False):
                continue

            filtered_listings.append(listing)

        self.listings = filtered_listings
    
    def get_postcode(self, description):
        match = re.search(r'[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}', description)
        if match:
            return match.group()
        return None

    def is_hmo_check(self, soup):
        # First check the explicit HMO badge
        if soup.find('img', alt='HMO'):
            return True
        
        # Fall back to description text
        description_div = soup.find('div', attrs={'data-id': 'listing-description'})
        if description_div:
            description_text = description_div.get_text().lower()
            # Check for HMO mention but exclude "non-hmo" or "not hmo"
            if re.search(r'(?<!non[\s-])(?<!not )\bhmo\b', description_text):
                return True
        
        return False
    
class DJAlexanderScraper(Scraper):

    BASE = "https://www.djalexander.co.uk/property/to-rent/in-edinburgh"

    def __init__(self, max_price, beds):
        #from-3-to-3-bedrooms/below-2000/
        search_url = f"{self.BASE}/from-{beds}-to-{beds}-bedrooms/below{4.345 * beds * max_price}/"
        super().__init__(max_price, beds, search_url)
        self.base_url = self.BASE

    def scrape_page(self, url):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector('.slide-content', timeout=10000)
            html = page.content()
            browser.close()
        
        return BeautifulSoup(html, 'html.parser')
    
    def paginate_url(self, url, page_number):
        return f"{url}/page-{page_number}/"

    def scrape_website(self, url):
        soups = []
        page_number = 1
        while True:
            paginated = self.paginate_url(url, page_number)
            soup = self.scrape_page(paginated)
            listings = soup.select('.slide-content')  # selector TBC
            if not listings:
                break
            soups.append(soup)
            page_number += 1

        return soups

    def extract_listings(self):
        final_listings = []
        soups = self.scrape_website(self.search_url)

        for soup in soups:
            for listing in soup.select('.slide-content'):  # selector TBC
                property_id = listing.get('id')
                url = listing.select_one('a.slide-content')['href'] if listing.select_one('a.slide-content') else None
                title = title = listing.select_one('div.title-wrap h3').get_text(strip=True) if listing.select_one('div.title-wrap h3') else None
                price_el = listing.select_one('p.highlight-text')  # selector TBC
                price = price_el.get_text(strip=True).replace('£', '').replace(',', '') if price_el else None
                availability = listing.select_one('.availability').get_text(strip=True) if listing.select_one('.availability') else None
                bathrooms_el = listing.select_one('i.icon-bath + span.count')  # selector TBC
                bathrooms = int(re.search(r'\d+', bathrooms_el.get_text()).group()) if bathrooms_el else None

                final_listings.append({
                    'property_id': property_id,
                    'url': url,
                    'title': title,
                    'price': price,
                    'availability': availability,
                    'bathrooms': bathrooms
                })

        self.listings = final_listings

    def advanced_extract(self):
        for listing in self.listings:
            soup = self.scrape_page(listing['url'])
            if not soup:
                continue

            # Description
            desc_div = soup.find('div', class_=re.compile('description'))  # selector TBC
            description = desc_div.get_text(strip=True) if desc_div else None

            is_hmo = self.is_hmo_check(soup, description)
            postcode = self.get_postcode(soup.find('meta', attrs={'name': 'description'})['content']) if soup.find('meta', attrs={'name': 'description'}) else None

            # Bills — DJA puts them in the description text so parse from there
            has_gas         = bool(re.search(r'\bgas\b', description or '', re.I))
            has_electricity = bool(re.search(r'\belectric(ity)?\b', description or '', re.I))
            has_broadband   = bool(re.search(r'\b(broadband|internet|wifi)\b', description or '', re.I))
            has_tv_licence  = bool(re.search(r'\btv\s*licen[sc]e\b', description or '', re.I))

            listing.update({
                'postcode': postcode,
                'is_hmo': is_hmo,
                'has_gas': has_gas,
                'has_electricity': has_electricity,
                'has_broadband': has_broadband,
                'has_tv_licence': has_tv_licence,
                'bills_included': [b for b, v in {
                    'Gas': has_gas, 'Electricity': has_electricity,
                    'Broadband': has_broadband, 'TV Licence': has_tv_licence
                }.items() if v]
            })

    def date_distance(self, target_date, listing):
        availability = listing.get('availability', '')
        try:
            cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', availability)
            date = datetime.strptime(cleaned.strip(), "%d %B %Y")  # DJA format TBC
            return abs((date - target_date).days)
        except:
            return float('inf')

    def basic_filter(self, max_price=None, beds=None):
        filtered = []
        for listing in self.listings:
            if listing['price'] is None:
                continue
            if listing['price'] <= max_price:
                filtered.append(listing)
        self.listings = filtered

    def advanced_filter(self, bills_required=None, central_location=None, hmo_required=None, max_distance_km=100):
        filtered = []
        for listing in self.listings:
            if bills_required:
                if not all(listing.get(bill, False) for bill in bills_required):
                    continue
            if not central_location or not self.in_proximity(listing.get('postcode'), central_location, max_distance_km):
                continue
            if hmo_required and not listing.get('is_hmo', False):
                continue
            filtered.append(listing)
        self.listings = filtered

    def filter_listings(self, bills_required=None, central_location=None, hmo_required=None, max_distance_km=100, move_in_date=None):
        self.basic_filter(self.max_price, self.beds)
        self.advanced_extract()
        self.advanced_filter(bills_required, central_location, hmo_required, max_distance_km)
        self.sort_listings(move_in_date)

    def get_postcode(self, text):
        match = re.search(r'[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}', text or '')
        return match.group() if match else None

    def is_hmo_check(self, soup, description=None):
        if soup.find(string=re.compile(r'\bHMO\b')):
            return True
        if description and re.search(r'(?<!non[\s-])(?<!not )\bhmo\b', description, re.I):
            return True
        return False