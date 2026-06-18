import time
import csv
from bs4 import BeautifulSoup
from math import radians, cos, sin, asin, sqrt
import requests
import re
import pandas as pd

from config import SEARCH_URLS, MAX_PRICE, BEDS, MOVE_IN_DATE, CENTRAL_LOCATION, FILTERED_LISTINGS_CSV_FILE

POSTCODE_COORDINATES_CSV = '/Users/zarif/Documents/python/Flat-Finder/NSPL_MAY_2025_UK_EH.csv'  # Path to your CSV file with postcode coordinates

def scrape_website(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    
    except requests.RequestException as e:
        print(f"Error scraping website: {e}")
        return None

#Extracts listings based on what provider is being used. Currently making it work for UniHomes.
def extract_listings(soup, website):
    final_listings = []
    if soup:
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

    return final_listings

def basic_filter(listings, max_price=None, beds=None):
    filtered_listings = []
    for listing in listings:
        price = listing['price']
        try:
            listing_beds = int(listing['title'].split()[0])  # Assuming the number of beds is the first word in the title
        except ValueError:
            listings.remove(listing)  # Remove listing if beds cannot be determined
            continue

        if price <= max_price and listing_beds == beds:
            filtered_listings.append(listing)

    return filtered_listings

def get_postcode(description):
    match = re.search(r'[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}', description)
    if match:
        return match.group()
    return None

def is_hmo_check(soup):
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

def advanced_extract(listings):
    for listing in listings:
        url = listing['url']
        scraped_soup = scrape_website(url)

        if scraped_soup:
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

            is_hmo = is_hmo_check(scraped_soup)
            postcode = get_postcode(scraped_soup.find('meta', attrs={'name': 'description'})['content']) if scraped_soup.find('meta', attrs={'name': 'description'}) else None

            listing.update({
                'postcode': postcode,
                'is_hmo': is_hmo,
            })
        
        time.sleep(0.2)

def get_postcode_coordinates(postcode):
    df = pd.read_csv(POSTCODE_COORDINATES_CSV)  # Assuming you have a CSV file with postcode coordinates
    row = df[df['pcd'] == postcode]
    
    return (float(row['lat'].iloc[0]), float(row['long'].iloc[0])) if not row.empty else None

def measure_distance(location1, postcode): #location given in (latitude, longitude) format
    location2 = get_postcode_coordinates(postcode)
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

def in_proximity(postcode, central_location, max_distance_km=2):
    distance = measure_distance(central_location, postcode)
    return distance <= max_distance_km 

def advanced_filter(listings, bills_required=None, central_location=None, hmo_required=None, max_distance_km=100):
    filtered_listings = []
    for listing in listings:
        if bills_required:
            if not all(listing.get(bill, False) for bill in bills_required):
                continue

        if not central_location or not in_proximity(listing.get('postcode'), central_location, max_distance_km):
            continue

        if hmo_required and not listing.get('is_hmo', False):
            continue

        filtered_listings.append(listing)

    return filtered_listings

def sort_listings(listings):
    listings.sort(key=lambda x: x['bathrooms'], reverse=True)
    listings.sort(key=lambda x: x['price'], reverse=False)
    return listings

def save_to_csv(listings, filename=FILTERED_LISTINGS_CSV_FILE):
    if listings:
        keys = listings[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(listings)
            
def main():

    all_listings = []
    
    for url in SEARCH_URLS:
        page = 1
        while True:
            paginated_url = f"{url}&page={page}"
            response = requests.get(paginated_url) 
            
            # Stop if redirected back to base URL
            if response.url.rstrip('/') == "https://www.unihomes.co.uk/student-accommodation/edinburgh":
                print(f"Reached last page at page {page}, stopping.")
                break

            soup = scrape_website(paginated_url)
            
            listings = extract_listings(soup, paginated_url)
            filtered_listings = basic_filter(listings, max_price=MAX_PRICE, beds=BEDS)

            time.sleep(0.1)  # Sleep for the specified interval in seconds
            
            advanced_extract(filtered_listings)
            filtered_listings = advanced_filter(filtered_listings, bills_required=['has_gas', 'has_electricity', 'has_broadband'], central_location=CENTRAL_LOCATION, hmo_required=True, max_distance_km=2)

            all_listings.extend(filtered_listings)
            
            print(f"Scraped page {page} of {url}.")
            print(f"Total listings so far: {len(all_listings)}")
            page += 1

    all_listings = sort_listings(all_listings)

    print(f"Total listings found: {len(all_listings)}")
    save_to_csv(all_listings)

if __name__ == "__main__":
    main()