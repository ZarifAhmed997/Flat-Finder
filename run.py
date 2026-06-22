import time
import random
import os
from config import *

def get_new_listings(listing_ids, old_listings):
    new_listings = set()

    for listing in old_listings:
        if listing['property_id'] not in listing_ids:
            new_listings.add(listing['property_id'])
    
    return new_listings

def get_old_listings():
    import pandas as pd

    if not os.path.exists(LISTINGS_CSV_FILE):
        return set()

    try:
        # Read property_id as string to avoid type mismatches with scraped IDs
        old_listings = pd.read_csv(LISTINGS_CSV_FILE, dtype={"property_id": str})
        return set(old_listings['property_id'].astype(str).dropna().unique())
    except Exception as e:
        print(f"Error reading {LISTINGS_CSV_FILE}: {e}")
        return set()

def random_delay(lower_bound, upper_bound):
    time.sleep(random.random() *(upper_bound - lower_bound) + lower_bound)

def main():
    from scraper import UniHomesScraper
    from notifier import Notifier

    # Create an instance of the scraper with the specified parameters
    scraper = UniHomesScraper(MAX_PRICE, BEDS)
    notifier = Notifier(GMAIL_ADDRESS, GMAIL_PASSWORD, NOTIFY_EMAILS)
    listing_ids = get_old_listings()

    while True:
        # Scrape listings based on the search URLs
        print("Scraping flat listings...")
        print()

        scraper.extract_listings()

        print(f'Scraped {len(scraper.get_listings())} total listings in {scraper.get_url()}...')

        scraper.filter_listings(max_price=MAX_PRICE, beds=BEDS, central_location=CENTRAL_LOCATION, hmo_required=True, max_distance_km=MAXIMUM_DISTANCE)
        listings = scraper.get_listings()

        print(f"Found {len(listings)} listings after filtering")

        # Save the filtered listings to a CSV file
        scraper.save_to_csv(LISTINGS_CSV_FILE)

        print(f"Saved {len(listings)} listings to {LISTINGS_CSV_FILE}")
        print()
        print()

        # Notify the user with the filtered listings

        new_listings = get_new_listings(listing_ids, listings)
        
        if new_listings:
            notifier.notify_users(new_listings, scraper.get_dataframe())

        listing_ids = set([listing['property_id'] for listing in listings])
        
        random_delay(600, 1200)

if __name__ == "__main__":
    main()