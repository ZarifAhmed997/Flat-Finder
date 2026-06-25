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
    from scraper import UniHomesScraper, DJAlexanderScraper
    from notifier import Notifier

    # Create an instance of the scraper with the specified parameters
    scrapers = [UniHomesScraper(MAX_PRICE, BEDS), DJAlexanderScraper(MAX_PRICE, BEDS)]
    notifier = Notifier(GMAIL_ADDRESS, GMAIL_PASSWORD, NOTIFY_EMAILS)
    listing_ids = get_old_listings()

    while True:
        print("Scraping flat listings...")
        print()

        all_listings = []

        for scraper in scrapers:
            scraper.extract_listings()
            print(f'Scraped {len(scraper.get_listings())} listings from {scraper.get_url()}')

            scraper.filter_listings(
                move_in_date=MOVE_IN_DATE,
                central_location=CENTRAL_LOCATION,
                hmo_required=True,
                max_distance_km=MAXIMUM_DISTANCE
            )

            all_listings.extend(scraper.get_listings())
            print(f'Found {len(scraper.get_listings())} listings after filtering from {scraper.get_url()}')

        print(f'\nTotal listings across all scrapers: {len(all_listings)}')

        # Save combined listings to CSV
        if all_listings:
            import pandas as pd
            df = pd.DataFrame(all_listings)
            if 'property_id' in df.columns:
                df['property_id'] = df['property_id'].astype(str)
            tmp = LISTINGS_CSV_FILE + '.tmp'
            df.to_csv(tmp, index=False)
            os.replace(tmp, LISTINGS_CSV_FILE)
            print(f'Saved {len(all_listings)} listings to {LISTINGS_CSV_FILE}')

        # Notify on new listings
        new_listings = get_new_listings(listing_ids, all_listings)
        if new_listings:
            notifier.notify_users(new_listings, pd.DataFrame(all_listings))

        listing_ids = set(listing['property_id'] for listing in all_listings)

        print()
        random_delay(INTERVAL * 48, INTERVAL * 72)

if __name__ == "__main__":
    main()