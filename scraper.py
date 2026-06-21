import csv
import random
from bs4 import BeautifulSoup
from math import radians, cos, sin, asin, sqrt
import requests
import re
import pandas as pd
import time

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
        return None if not url else f"{self.search_url}&page={page_number}" if "?" in url else f"{url}?page={page_number}"
    
    def scrape_page(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses

            time.sleep(random.random() * 0.2 + 0.05) # Delay between server requests to not get banned for DDOSing

            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
        
        except requests.RequestException as e:
            print(f"Error scraping website: {e}")
            return None

    def scrape_website(self, url):
        page_number = 1
        url = self.paginate_url(url, page_number)
        soups = []

        while True:
            try:
                response = requests.get(url)

                if response.url == self.base_url:
                    return soups 

                response.raise_for_status()  # Raise an error for bad responses

                time.sleep(random.random() * 0.2 + 0.05) # Delay between server requests to not get banned for DDOSing

                soup = BeautifulSoup(response.text, 'html.parser')
                
                if soup:
                    soups.append(soup) 
            
            except requests.RequestException as e:
                print(f"Error scraping website: {e}")
                return None
            
            page_number += 1
            url = self.paginate_url(url, page_number)

    def sort_listings(self):
        self.listings = sorted(self.listings, key=lambda x: x['bathrooms'], reverse=True)
        # Maybe sort by move in date here?
        self.listings = sorted(self.listings, key=lambda x: x['price'], reverse=False)

    def get_postcode_coordinates(self, postcode):
            POSTCODE_COORDINATES_CSV = '/Users/zarif/Documents/python/Flat-Finder/NSPL_MAY_2025_UK_EH.csv'  # Path to your CSV file with postcode coordinates
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
    
    def save_to_csv(self, filename):
        if self.listings:
            keys = self.listings[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(self.listings)


class UniHomesScraper(Scraper):
    def __init__(self, max_price, beds):
        super().__init__(max_price, beds, "https://www.unihomes.co.uk/student-accommodation/edinburgh?type=house%2Capartment")
        self.base_url = "https://www.unihomes.co.uk/student-accommodation/edinburgh"

    def extract_listings(self):
        final_listings = []
        soups = self.scrape_website(self.search_url)
        
        for page_number in range(len(soups)):
            soup = soups[page_number]
            listings = soup.select('div.property') 
            for listing in listings:
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
        
        self.listings = final_listings

    def basic_filter(self, max_price=None, beds=None):
        filtered_listings = []
        for listing in self.listings:
            price = listing['price']
            try:
                listing_beds = int(listing['title'].split()[0])  # Assuming the number of beds is the first word in the title
            except ValueError:
                self.listings.remove(listing)  # Remove listing if beds cannot be determined
                continue

            if price <= max_price and listing_beds == beds:
                filtered_listings.append(listing)

        self.listings = filtered_listings

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

    def filter_listings(self, max_price=None, beds=None, bills_required=None, central_location=None, hmo_required=None, max_distance_km=100):
        self.basic_filter(max_price, beds)
        self.advanced_extract()
        self.advanced_filter(bills_required, central_location, hmo_required, max_distance_km)
        self.sort_listings()
    
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