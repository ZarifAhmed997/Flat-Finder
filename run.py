import time

def main():
    from config import MAX_PRICE, BEDS, CENTRAL_LOCATION, LISTINGS_CSV_FILE
    from scraper import UniHomesScraper

    # Create an instance of the scraper with the specified parameters
    scraper = UniHomesScraper(MAX_PRICE, BEDS)

    while True:
        # Scrape listings based on the search URLs
        print("Scraping flat listings...")
        print()

        scraper.extract_listings()

        print(f'Scraped {len(scraper.get_listings())} total listings in {scraper.get_url()}...')

        scraper.filter_listings(max_price=MAX_PRICE, beds=BEDS, central_location=CENTRAL_LOCATION, hmo_required=True, max_distance_km=2)
        listings = scraper.get_listings()

        print(f"Found {len(listings)} listings after filtering")

        # Save the filtered listings to a CSV file
        scraper.save_to_csv(LISTINGS_CSV_FILE)

        print(f"Saved {len(listings)} listings to {LISTINGS_CSV_FILE}")
        print()
        print()

        # Notify the user with the filtered listings
        
        time.sleep(900) # Wait for 15 minutes before the next scrape

if __name__ == "__main__":
    main()