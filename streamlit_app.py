import streamlit as st
import requests
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import logging
import boto3
from botocore.exceptions import ClientError
import uuid
import pytz
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Create a StringIO object to capture log output
log_output = io.StringIO()
# Add a StreamHandler to the logger that writes to our StringIO object
string_handler = logging.StreamHandler(log_output)
logger.addHandler(string_handler)

# Set Beijing timezone
beijing_tz = pytz.timezone('Asia/Shanghai')

class CalendarGeneratorApp:
    def __init__(self):
        self.url = "https://thisedu.schoology.com/calendar/feed/ical/1723100182/cd2029d8706e2eb5ad4bba0da6232869/ical.ics"
        self.s3_bucket_name = 'josh-this-2425'
        self.s3_access_key = st.secrets["s3_access_key"]
        self.s3_secret_key = st.secrets["s3_secret_key"]
        self.update_interval = 3600  # Default to 1 hour
        self.webcal_url = f"webcal://s3.amazonaws.com/{self.s3_bucket_name}/generated_calendar.ics"
        self.current_year = datetime.now().year
        self.next_year = self.current_year + 1

    def get_schedule(self, day, date):
        logger.info(f"Getting schedule for {day} on {date}")
        is_wednesday = date.weekday() == 2  # 2 represents Wednesday

        time_schedules = {
            "regular": [
                ("08:00", "08:10", "Homeroom"),
                ("08:15", "08:55", "Period 1A"),
                ("08:55", "09:35", "Period 1B"),
                ("09:35", "09:50", "Break"),
                ("09:55", "11:15", "Period 2"),
                ("11:22", "12:05", "Period 3A"),
                ("12:10", "13:00", "Lunch"),
                ("13:05", "13:48", "Period 3B"),
                ("13:55", "14:35", "Period 4A"),
                ("14:35", "15:15", "Period 4B")
            ],
            "wednesday": [
                ("08:00", "08:10", "Homeroom"),
                ("08:15", "08:55", "Period 1A"),
                ("08:15", "08:55", "Period 1B"),
                ("09:02", "09:42", "Period 2"),
                ("09:47", "10:27", "Extended Homeroom"),
                ("10:27", "10:40", "Break"),
                ("10:45", "11:25", "Period 3A"),
                ("11:30", "12:10", "Period 3B"),
                ("12:15", "12:55", "Lunch"),
                ("13:00", "13:40", "Period 4A"),
                ("13:00", "13:40", "Period 4B"),
                ("13:40", "17:00", "Professional Development")
            ]
        }

        class_schedules = {
            "Day 1": {
                "Period 1A": "Period 1A - Free",
                "Period 1B": "Period 1B - Free",
                "Period 2": "Improv Theatre (ART229.101)", 
                "Period 3A": "Theatre 8 (ART083.101)",
                "Period 3B": "Theatre 8 (ART083.101) continued",
                "Period 4A": "Theatre 6 (ART063.103)",
                "Period 4B": "Theatre 6 (ART063.104)"
            },
            "Day 2": {
                "Period 1A": "Period 1A - Free",
                "Period 1B": "Period 1B - Free",
                "Period 2": "Period 2 - Free",
                "Period 3A": "Period 3A - Free",
                "Period 3B": "Period 3B- Free",
                "Period 4A": "Period 4A - Free",
                "Period 4B": "Period 4B- Free"
            },
            "Day 3": {
                "Period 1A": "Theatre 7 (ART073.103)",
                "Period 1B": "Theatre 7 (ART073.104)",
                "Period 2": "Period 2 - Free",
                "Period 3A": "Period 3A - Free",
                "Period 3B": "Period 3B- Free",
                "Period 4A": "Period 4A - Free",
                "Period 4B": "Period 4B- Free"
            },
            "Day 4": {
                "Period 1A": "Period 1A - Free",
                "Period 1B": "Period 1B - Free",
                "Period 2": "Improv Theatre (ART229.101)", 
                "Period 3A": "Theatre 8 (ART083.101)",
                "Period 3B": "Theatre 8 (ART083.101) continued",
                "Period 4A": "Theatre 6 (ART063.103)",
                "Period 4B": "Theatre 6 (ART063.104)"
            },
            "Day 5": {
                "Period 1A": "Period 1A - Free",
                "Period 1B": "Period 1B - Free",
                "Period 2": "Period 2 - Free",
                "Period 3A": "Period 3A - Free",
                "Period 3B": "Period 3B- Free",
                "Period 4A": "Period 4A - Free",
                "Period 4B": "Period 4B- Free"
            },
            "Day 6": {
                "Period 1A": "Theatre 7 (ART073.103)",
                "Period 1B": "Theatre 7 (ART073.104)",
                "Period 2": "Period 2 - Free",
                "Period 3A": "Period 3A - Free",
                "Period 3B": "Period 3B- Free",
                "Period 4A": "Period 4A - Free",
                "Period 4B": "Period 4B- Free"
            },
        }
        
        if day not in class_schedules:
            logger.info(f"Day type '{day}' not found in class_schedules")
            return []

        base_schedule = time_schedules["wednesday" if is_wednesday else "regular"]
        day_schedule = class_schedules[day]
        
        events = []

        # Add the day event starting at 7:59 AM
        day_start = beijing_tz.localize(datetime.combine(date, datetime.strptime("07:59", "%H:%M").time()))
        day_event = Event()
        day_event.add('summary', day)
        day_event.add('dtstart', day_start)
        day_event.add('dtend', day_start + timedelta(minutes=1))  # 1 minute duration
        day_event.add('uid', str(uuid.uuid4()) + "@yourdomain.com")
        day_event.add('dtstamp', datetime.now(beijing_tz))
        events.append(day_event)
        
        for start_time, end_time, activity in base_schedule:
            start_dt = beijing_tz.localize(datetime.combine(date, datetime.strptime(start_time, "%H:%M").time()))
            end_dt = beijing_tz.localize(datetime.combine(date, datetime.strptime(end_time, "%H:%M").time()))

            # Log event details
            logger.info(f"Creating event: {activity} | Start: {start_dt} | End: {end_dt}")

            if activity.startswith("Period"):
                period = activity
                class_name = day_schedule.get(period, activity)
                event = Event()
                event.add('summary', class_name)
                event.add('dtstart', start_dt)
                event.add('dtend', end_dt)
                event.add('uid', str(uuid.uuid4()) + "@yourdomain.com")
                event.add('dtstamp', datetime.now(beijing_tz))
                events.append(event)
            else:
                event = Event()
                event.add('summary', activity)
                event.add('dtstart', start_dt)
                event.add('dtend', end_dt)
                event.add('uid', str(uuid.uuid4()) + "@yourdomain.com")
                event.add('dtstamp', datetime.now(beijing_tz))
                events.append(event)
                
        return events

    def generate_calendar(self):
        logger.info(f"Fetching calendar from URL: {self.url}")
        st.text("Fetching original calendar...")
        ical_string = requests.get(self.url).text
        original_cal = Calendar.from_ical(ical_string)
        
        events_added = 0
        events_replaced = 0

        st.text("Generating detailed calendar...")
        for component in original_cal.walk():
            if component.name == "VEVENT":
                summary = component.get('summary')
                dtstart = component.get('dtstart').dt
                
                if isinstance(dtstart, datetime):
                    # Preserve the original timezone
                    if dtstart.tzinfo is None:
                        dtstart = beijing_tz.localize(dtstart)
                    
                    if dtstart.year in [self.current_year, self.next_year]:
                        if summary and summary.startswith("Day"):
                            # Remove the original Day event
                            original_cal.subcomponents.remove(component)
                            events_replaced += 1
                            
                            # Generate detailed schedule for this day
                            detailed_events = self.get_schedule(summary, dtstart.date())
                            for event in detailed_events:
                                original_cal.add_component(event)
                                events_added += 1

        logger.info(f"Updated calendar: replaced {events_replaced} events, added {events_added} detailed events")
        st.success(f"Updated calendar: replaced {events_replaced} events, added {events_added} detailed events")
        return original_cal

    def save_calendar(self, cal):
        file_content = cal.to_ical()
        s3_client = boto3.client('s3', 
                                 aws_access_key_id=self.s3_access_key,
                                 aws_secret_access_key=self.s3_secret_key)

        # Generate a file name with a timestamp
        timestamp = datetime.now(beijing_tz).strftime('%Y%m%d_%H%M%S')
        history_file_name = f"history/generated_calendar_{timestamp}.ics"
        main_file_name = "generated_calendar.ics"

        try:
            # Upload timestamped file to /history folder
            s3_client.put_object(Bucket=self.s3_bucket_name, Key=history_file_name, Body=file_content, ContentType='text/calendar')
            logger.info(f"Saved timestamped calendar to S3: {history_file_name}")
            st.success(f"Saved timestamped calendar to S3: {history_file_name}")

            # Upload main file to bucket root
            s3_client.put_object(Bucket=self.s3_bucket_name, Key=main_file_name, Body=file_content, ContentType='text/calendar')
            logger.info(f"Saved main calendar to S3: {main_file_name}")
            st.success(f"Saved main calendar to S3: {main_file_name}")

        except ClientError as e:
            logger.error(f"Failed to save calendar to S3: {e}")
            st.error(f"Failed to save calendar to S3: {e}")

    def perform_generation(self):
        try:
            logger.info("Generating new calendar")
            st.text("Generating new calendar...")
            new_cal = self.generate_calendar()
            self.save_calendar(new_cal)
            logger.info("Calendar generated successfully")
            st.success("Calendar generated successfully")
        except Exception as e:
            logger.error(f"Calendar generation failed: {e}")
            st.error(f"Calendar generation failed: {e}")

def main():
    st.title("Calendar Generator App")
    
    app = CalendarGeneratorApp()
    
    st.write("This app generates a detailed school calendar and saves it to an S3 bucket.")
    st.write(f"Processing events for years: {app.current_year} and {app.next_year}")
    
    if st.button("Generate Now"):
        app.perform_generation()
    
    st.write("---")
    
    st.write("Set Update Interval:")
    new_interval = st.number_input("Enter update interval in minutes:", min_value=1, value=10080)
    if st.button("Set Interval"):
        app.update_interval = new_interval * 60
        logger.info(f"Update interval set to {new_interval} minutes")
        st.success(f"Update interval set to {new_interval} minutes")
    
    st.write("---")
    
    st.write("Webcal URL:")
    st.text(app.webcal_url)
    if st.button("Copy Webcal URL"):
        st.write("Webcal URL copied to clipboard!")
        st.code(app.webcal_url)
    
    st.write("---")
    
    # Display log output
    st.subheader("Log Output")
    st.text_area("Logs", value=log_output.getvalue(), height=350)

if __name__ == "__main__":
    main()