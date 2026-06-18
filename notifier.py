import pandas as pd
import requests
import smtplib

from config import GMAIL_ADRESS, GMAIL_PASSWORD, LISTINGS_CSV_FILE

def get_listings_from_csv(csv_file=LISTINGS_CSV_FILE):
    try:
        df = pd.read_csv(csv_file)
        return df
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None

def notify_user(listings, email_address):
    df = pd.DataFrame(listings)
    
    # Create a simple HTML table from the DataFrame
    html_table = df.to_html(index=False, escape=False)
    
    # Here you would implement the logic to send an email with the HTML table
    # For example, using smtplib or any email-sending service
    print(f"Sending email to {email_address} with the following listings:\n{html_table}")