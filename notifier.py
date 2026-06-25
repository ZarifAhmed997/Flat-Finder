import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import LISTINGS_CSV_FILE

class Notifier:
    def __init__(self, email, password, recipients):
        self.email = email
        self.password = password
        self.recipients = recipients

    def notify_users(self, listing_ids, listings):

        new_listings = listings[listings['property_id'].isin(listing_ids)]
        new_listings = new_listings[['url','title','price','availability','bathrooms','bills_included','postcode']]

        msg = MIMEMultipart()
        msg["From"] = self.email
        msg["To"] = ", ".join(self.recipients)
        msg["Subject"] = "New flat found!"

        html_table = new_listings.to_html(index=False, border=1)
        html_body = f"""
            <html>
                <body>
                    <p>New listings found: </p>
                    {html_table}
                </body>
            </html>
        """

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            try:
                server.login(self.email, self.password)
            except smtplib.SMTPAuthenticationError:
                print('Credentials are wrong in config.py')
                return

            server.send_message(msg)

        print(f"Sending notification to {', '.join(self.recipients)} with the following listings: \n{new_listings['url'].to_string(index=False)}")

