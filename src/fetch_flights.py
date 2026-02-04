"""
Flight Data Ingestion Script

Fetches "Anywhere" flight deals from SerpApi Google Flights Explore engine,
compares with previous data to calculate price differences, and saves to CSV.

Usage:
    python src/fetch_flights.py

Environment Variables:
    SERPAPI_KEY: Your SerpApi API key (required)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from serpapi import GoogleSearch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FLIGHTS_CSV = DATA_DIR / "flights.csv"
PRICE_HISTORY_CSV = DATA_DIR / "price_history.csv"

# API Configuration
DEPARTURE_ID = "SIN"  # Singapore Changi Airport
CURRENCY = "SGD"

# Travel duration options (SerpApi values)
TRAVEL_DURATIONS = {
    "1": "Weekend",
    "2": "1 Week",
    "3": "2 Weeks",
}

# Month options (SerpApi values)
MONTHS = {
    "0": "Flexible (All)",
    "1": "January",
    "2": "February",
    "3": "March",
    "4": "April",
    "5": "May",
    "6": "June",
    "7": "July",
    "8": "August",
    "9": "September",
    "10": "October",
    "11": "November",
    "12": "December",
}


def get_available_months() -> list[str]:
    """
    Get the next 6 months available for search (SerpApi supports only next 6 months).

    Returns:
        List of month codes (0-12) that are available
    """
    now = datetime.now()
    current_month = now.month
    available = ["0"]  # Always include "Flexible"

    for i in range(0, 6):  # Current month + next 5 months
        month = ((current_month - 1 + i) % 12) + 1
        available.append(str(month))

    return available


def load_env() -> str:
    """Load environment variables and return the API key."""
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        logger.error("SERPAPI_KEY environment variable not set")
        sys.exit(1)

    return api_key


def load_previous_data() -> pd.DataFrame:
    """
    Load existing flight data from CSV.

    Returns:
        DataFrame with previous flight data, or empty DataFrame if file doesn't exist.
    """
    try:
        df = pd.read_csv(FLIGHTS_CSV)
        logger.info(
            f"Loaded {len(df)} existing flight records from {FLIGHTS_CSV}")
        return df
    except FileNotFoundError:
        logger.info("No existing flight data found. Starting fresh.")
        return pd.DataFrame()
    except pd.errors.EmptyDataError:
        logger.warning("Existing CSV is empty. Starting fresh.")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading previous data: {e}")
        return pd.DataFrame()


def fetch_flights_from_api(api_key: str, travel_duration: str, month: str) -> list[dict]:
    """
    Fetch flight deals from SerpApi Google Flights Explore engine.

    Args:
        api_key: SerpApi API key
        travel_duration: Duration code ("1"=weekend, "2"=1week, "3"=2weeks)
        month: Month code ("0"=flexible, "1"-"12"=specific month)

    Returns:
        List of flight deal dictionaries
    """
    duration_name = TRAVEL_DURATIONS.get(travel_duration, "Unknown")
    month_name = MONTHS.get(month, "Unknown")
    params = {
        "engine": "google_travel_explore",
        "departure_id": DEPARTURE_ID,
        "travel_duration": travel_duration,
        "currency": CURRENCY,
        "api_key": api_key,
    }

    # Add month parameter if not flexible
    if month != "0":
        params["month"] = month

    logger.info(
        f"Fetching {duration_name} flights for {month_name} from SerpApi (departure: {DEPARTURE_ID}, currency: {CURRENCY})")

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            logger.warning(f"API Error: {results['error']}. Skipping this request.")
            return []

        # The API returns data under different keys depending on the response
        # Try multiple possible keys: flights, destinations, results
        flights = results.get("flights", [])
        if not flights:
            flights = results.get("destinations", [])
        if not flights:
            flights = results.get("results", [])
        if not flights:
            # Try to find any list in the response
            for key, value in results.items():
                if isinstance(value, list) and len(value) > 0:
                    flights = value
                    break

        logger.info(f"Retrieved {len(flights)} flight deals from API")

        return flights

    except Exception as e:
        logger.warning(f"Failed to fetch flights from API: {e}. Skipping this request.")
        return []


def parse_flight_data(flights: list[dict], travel_duration: str, month: str) -> pd.DataFrame:
    """
    Parse raw API response into a structured DataFrame.

    Based on SerpApi Google Travel Explore API response structure:
    - name: destination name
    - country: destination country
    - flight_price: price of the flight
    - thumbnail: image URL
    - start_date: departure date
    - end_date: return date (for round trips)
    - airline: airline name
    - number_of_stops: number of stops

    Args:
        flights: List of destination dictionaries from API

    Returns:
        DataFrame with parsed flight data
    """
    parsed_data = []
    zero_price_destinations = []
    for dest in flights:
        # Extract destination name and country
        name = dest.get("name", "Unknown")
        country = dest.get("country", "")
        destination = f"{name}, {country}" if country else name

        # Extract flight price (it's already a number in the API response)
        price = dest.get("flight_price", 0)
        if price is None:
            price = 0
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0.0

        # Skip destinations with no flight price data
        if price == 0:
            zero_price_destinations.append(destination)
            continue

        # Extract thumbnail
        thumbnail = dest.get("thumbnail", "")

        # Extract dates
        start_date = dest.get("start_date", "")
        end_date = dest.get("end_date", "")

        # Extract additional useful info
        airline = dest.get("airline", "")
        stops = dest.get("number_of_stops", 0)
        duration = dest.get("flight_duration", 0)  # in minutes

        # Get airport info
        airport_info = dest.get("destination_airport", {})
        airport_code = airport_info.get(
            "code", "") if isinstance(airport_info, dict) else ""

        parsed_data.append({
            "destination": destination,
            "price": price,
            "thumbnail": thumbnail,
            "start_date": start_date,
            "end_date": end_date,
            "airline": airline,
            "stops": stops,
            "duration_mins": duration,
            "airport_code": airport_code,
            "travel_duration": TRAVEL_DURATIONS.get(travel_duration, "Unknown"),
            "month": MONTHS.get(month, "Unknown"),
            "fetched_at": datetime.utcnow().isoformat(),
        })

    df = pd.DataFrame(parsed_data)
    logger.info(
        f"Parsed {len(df)} flight records from {len(flights)} API results")

    # Log skipped destinations
    if zero_price_destinations:
        logger.info(
            f"Skipped {len(zero_price_destinations)} destinations with no flight price data:")
        for dest in zero_price_destinations[:5]:  # Show first 5
            logger.info(f"  - {dest}")
        if len(zero_price_destinations) > 5:
            logger.info(f"  ... and {len(zero_price_destinations) - 5} more")

    # Log price statistics
    if "price" in df.columns and len(df) > 0:
        price_stats = df["price"].describe()
        logger.info(
            f"Price statistics: min=${price_stats['min']:.0f}, max=${price_stats['max']:.0f}, mean=${price_stats['mean']:.0f}")

    return df


def calculate_price_diff(new_data: pd.DataFrame, previous_data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate price differences between new and previous data.
    Preserves historical price information.
    Uses composite key: destination|travel_duration|start_date for accurate matching.

    Args:
        new_data: DataFrame with current flight data
        previous_data: DataFrame with previous flight data

    Returns:
        DataFrame with price_diff and previous_price columns
    """
    if previous_data.empty:
        logger.info("No previous data for comparison. Setting price_diff to 0.")
        new_data["previous_price"] = new_data["price"]
        new_data["price_diff"] = 0.0
        return new_data

    # Create composite key for accurate matching: destination|travel_duration|start_date
    def make_composite_key(df: pd.DataFrame) -> pd.Series:
        return df["destination"].astype(str) + "|" + df["travel_duration"].astype(str) + "|" + df["start_date"].astype(str)

    previous_data = previous_data.copy()
    previous_data["_composite_key"] = make_composite_key(previous_data)
    prev_prices = previous_data.set_index("_composite_key")["price"].to_dict()

    # Also preserve historical previous_price if it exists
    if "previous_price" in previous_data.columns:
        hist_prev_prices = previous_data.set_index(
            "_composite_key")["previous_price"].to_dict()
    else:
        hist_prev_prices = prev_prices.copy()

    def get_composite_key(row):
        return f"{row['destination']}|{row['travel_duration']}|{row['start_date']}"

    def get_previous_price(row):
        key = get_composite_key(row)
        # Use the most recent known price as previous
        if key in prev_prices:
            return prev_prices[key]
        return row["price"]  # New flight, no history

    def get_price_diff(row):
        key = get_composite_key(row)
        if key in prev_prices:
            return row["price"] - prev_prices[key]
        return 0.0  # New flight

    new_data["previous_price"] = new_data.apply(get_previous_price, axis=1)
    new_data["price_diff"] = new_data.apply(get_price_diff, axis=1)

    # Log summary of price changes
    drops = (new_data["price_diff"] < 0).sum()
    increases = (new_data["price_diff"] > 0).sum()
    unchanged = (new_data["price_diff"] == 0).sum()

    logger.info(
        f"Price changes: {drops} drops, {increases} increases, {unchanged} unchanged")

    return new_data


def save_to_csv(df: pd.DataFrame) -> None:
    """
    Save flight data to CSV file.

    Args:
        df: DataFrame to save
    """
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Define column order
    columns = [
        "destination",
        "price",
        "previous_price",
        "price_diff",
        "thumbnail",
        "start_date",
        "end_date",
        "airline",
        "stops",
        "duration_mins",
        "airport_code",
        "travel_duration",
        "month",
        "fetched_at",
    ]

    # Reorder columns (only include columns that exist)
    existing_cols = [c for c in columns if c in df.columns]
    df = df[existing_cols]

    df.to_csv(FLIGHTS_CSV, index=False)
    logger.info(f"Saved {len(df)} flight records to {FLIGHTS_CSV}")


def load_price_history() -> pd.DataFrame:
    """
    Load existing price history from CSV.

    Returns:
        DataFrame with historical price data, or empty DataFrame if not found.
    """
    if not PRICE_HISTORY_CSV.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(PRICE_HISTORY_CSV)
        logger.info(f"Loaded {len(df)} price history records")
        return df
    except Exception as e:
        logger.warning(f"Could not load price history: {e}")
        return pd.DataFrame()


def append_to_price_history(df: pd.DataFrame) -> None:
    """
    Append current price snapshot to price history CSV.
    Includes duplicate prevention - skips if last entry was within 1 hour.

    Args:
        df: DataFrame with current flight data to append
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check for duplicate prevention
    if PRICE_HISTORY_CSV.exists():
        try:
            existing = pd.read_csv(PRICE_HISTORY_CSV)
            if not existing.empty and "fetched_at" in existing.columns:
                last_timestamp = pd.to_datetime(existing["fetched_at"]).max()
                now = datetime.utcnow()
                if (now - last_timestamp).total_seconds() < 3600:
                    logger.info(
                        "Price history already updated in last hour. Skipping append.")
                    return
        except Exception as e:
            logger.warning(f"Could not check duplicate prevention: {e}")

    # Select only the columns we want to track in history
    history_columns = [
        "destination", "price", "start_date", "end_date",
        "travel_duration", "month", "airline", "stops", "fetched_at"
    ]
    existing_cols = [c for c in history_columns if c in df.columns]
    history_snapshot = df[existing_cols].copy()

    # Append to existing history or create new file
    if PRICE_HISTORY_CSV.exists():
        history_snapshot.to_csv(
            PRICE_HISTORY_CSV, mode='a', header=False, index=False)
    else:
        history_snapshot.to_csv(PRICE_HISTORY_CSV, index=False)

    logger.info(f"Appended {len(history_snapshot)} entries to price history")


def cleanup_old_flights(flights_df: pd.DataFrame, history_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Remove flights where end_date has passed (trip completed).

    Args:
        flights_df: Current flights DataFrame
        history_df: Price history DataFrame

    Returns:
        Tuple of (cleaned flights_df, cleaned history_df)
    """
    today = datetime.now().date()

    # Filter flights.csv
    if not flights_df.empty and 'end_date' in flights_df.columns:
        flights_df = flights_df.copy()
        flights_df['_end_date_parsed'] = pd.to_datetime(
            flights_df['end_date'], errors='coerce').dt.date
        before_count = len(flights_df)
        flights_df = flights_df[flights_df['_end_date_parsed'] >= today]
        flights_df = flights_df.drop(columns=['_end_date_parsed'])
        removed = before_count - len(flights_df)
        if removed > 0:
            logger.info(f"Cleaned {removed} expired flights from flights.csv")

    # Filter price_history.csv similarly
    if not history_df.empty and 'end_date' in history_df.columns:
        history_df = history_df.copy()
        history_df['_end_date_parsed'] = pd.to_datetime(
            history_df['end_date'], errors='coerce').dt.date
        before_count = len(history_df)
        history_df = history_df[history_df['_end_date_parsed'] >= today]
        history_df = history_df.drop(columns=['_end_date_parsed'])
        removed = before_count - len(history_df)
        if removed > 0:
            logger.info(
                f"Cleaned {removed} expired entries from price_history.csv")

    return flights_df, history_df


def save_price_history(df: pd.DataFrame) -> None:
    """
    Save cleaned price history back to CSV (full overwrite).

    Args:
        df: DataFrame with price history to save
    """
    if df.empty:
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(PRICE_HISTORY_CSV, index=False)
    logger.info(f"Saved {len(df)} price history records")


def main() -> None:
    """Main entry point for the flight data ingestion script."""
    logger.info("=" * 50)
    logger.info("Starting Flight Data Ingestion")
    logger.info("=" * 50)

    # Load API key
    api_key = load_env()

    # Load previous data for comparison
    previous_data = load_previous_data()

    # Load and clean price history (remove expired flights)
    price_history = load_price_history()
    previous_data, price_history = cleanup_old_flights(
        previous_data, price_history)

    # Save cleaned price history if cleanup removed any entries
    if not price_history.empty:
        save_price_history(price_history)

    # Get available months (next 6 months from today)
    available_months = get_available_months()

    # Fetch data for all travel durations and months
    all_data = []
    for month_code in available_months:
        for duration_code in TRAVEL_DURATIONS.keys():
            logger.info(
                f"Fetching {MONTHS[month_code]} - {TRAVEL_DURATIONS[duration_code]}")
            raw_flights = fetch_flights_from_api(
                api_key, duration_code, month_code)

            if not raw_flights:
                logger.warning(
                    f"No flights returned for {MONTHS[month_code]} {TRAVEL_DURATIONS[duration_code]}")
                continue

            # Parse the raw data
            new_data = parse_flight_data(
                raw_flights, duration_code, month_code)
            all_data.append(new_data)

    if not all_data:
        logger.warning("No flights returned from API. Keeping existing data.")
        return

    # Combine all duration and month data
    final_data = pd.concat(all_data, ignore_index=True)

    # Calculate price differences (group by destination + duration + month)
    if not previous_data.empty:
        final_data = calculate_price_diff(final_data, previous_data)
    else:
        final_data["previous_price"] = final_data["price"]
        final_data["price_diff"] = 0.0

    # Save to CSV
    save_to_csv(final_data)

    # Append to price history for tracking
    append_to_price_history(final_data)

    logger.info("=" * 50)
    logger.info("Flight Data Ingestion Complete")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
