import json
import time
import csv
from bs4 import BeautifulSoup
import requests
import re

from config import SEARCH_URLS, MAX_PRICE, BEDS

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
            price = listing.select_one('span:-soup-contains("£")').get_text(strip=True) if listing.select_one('span:-soup-contains("£")') else None
            availability = "".join(listing.select_one('h4').get_text(strip=True).splitlines(True)[1:]).strip() if listing.select_one('h4') else None
            bathrooms = listing.select_one('span:-soup-contains("bathrooms")').get_text(strip=True) if listing.select_one('span:-soup-contains("bathrooms")') else None
            
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
        price = float(listing['price'].replace('£', '').replace(',', ''))
        listing_beds = int(listing['title'].split()[0])  # Assuming the number of beds is the first word in the title

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
        
        time.sleep(0.3)

def save_to_csv(listings, filename='filtered_listings.csv'):
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
            if response.url.rstrip('/') == url.rstrip('/'):
                print(f"Reached last page at page {page}, stopping.")
                break

            soup = scrape_website(paginated_url)
            
            listings = extract_listings(soup, paginated_url)
            filtered_listings = basic_filter(listings, max_price=MAX_PRICE, beds=BEDS)

            time.sleep(0.3)  # Sleep for the specified interval in seconds
            
            advanced_extract(filtered_listings)
            all_listings.extend(filtered_listings)
            
            print(f"Scraped page {page} of {url}.")
            print(f"Total listings so far: {len(all_listings)}")
            page += 1

    print(f"Total listings found: {len(all_listings)}")
    save_to_csv(all_listings)

if __name__ == "__main__":
    main()