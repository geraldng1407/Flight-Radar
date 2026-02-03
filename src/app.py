"""
Flight Explorer Dashboard

A Streamlit dashboard for exploring flight deals from Singapore.
Displays flight cards with price tracking and filtering options.

Usage:
    streamlit run src/app.py
"""

from __future__ import annotations

import json
import hashlib
import os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# Page configuration
st.set_page_config(
    page_title="Flight Explorer",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
FLIGHTS_CSV = PROJECT_ROOT / "data" / "flights.csv"
PRICE_HISTORY_CSV = PROJECT_ROOT / "data" / "price_history.csv"
WISHLIST_JSON = PROJECT_ROOT / "data" / "wishlist.json"


def require_password() -> None:
    """
    Gate the app behind a simple password.

    Uses Streamlit secrets (APP_PASSWORD) or falls back to env var.
    If no password is configured, the gate is skipped.
    """
    configured_password = st.secrets.get(
        "APP_PASSWORD") or os.getenv("APP_PASSWORD")
    if not configured_password:
        return

    if "authed" not in st.session_state:
        st.session_state.authed = False

    if not st.session_state.authed:
        st.subheader("🔒 Protected")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if password == configured_password:
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("Incorrect password")
        st.stop()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_flight_data() -> pd.DataFrame:
    """
    Load flight data from CSV with caching.

    Returns:
        DataFrame with flight data, or empty DataFrame if file doesn't exist.
    """
    try:
        df = pd.read_csv(FLIGHTS_CSV)
        return df
    except FileNotFoundError:
        return pd.DataFrame()
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def load_wishlist() -> list[str]:
    """
    Load wishlist from JSON file.

    Returns:
        List of saved flight destinations
    """
    try:
        if WISHLIST_JSON.exists():
            with open(WISHLIST_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_wishlist(wishlist: list[str]) -> None:
    """
    Save wishlist to JSON file.

    Args:
        wishlist: List of flight destinations to save
    """
    try:
        WISHLIST_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(WISHLIST_JSON, "w", encoding="utf-8") as f:
            json.dump(wishlist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Failed to save wishlist: {e}")


def render_empty_state() -> None:
    """Render an informative empty state when no data is available."""
    st.markdown(
        """
        <div style="text-align: center; padding: 60px 20px;">
            <h1 style="font-size: 4rem; margin-bottom: 0;">✈️</h1>
            <h2 style="color: #666;">No Flight Data Available</h2>
            <p style="color: #888; max-width: 500px; margin: 0 auto;">
                Flight data hasn't been fetched yet. The data will be automatically 
                updated by the scheduled GitHub Actions workflow, or you can run 
                the ingestion script manually:
            </p>
            <code style="display: block; margin-top: 20px; padding: 15px; 
                        background: #f0f2f6; border-radius: 5px;">
                python src/fetch_flights.py
            </code>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(df: pd.DataFrame, wishlist: list[str]) -> tuple[float, bool, str]:
    """
    Render sidebar with filters and wishlist.

    Args:
        df: Flight data DataFrame
        wishlist: List of saved flight destinations

    Returns:
        Tuple of (max_budget, show_drops_only, selected_month)
    """
    st.sidebar.header("🔍 Filters")

    # Month selector
    months_in_data = []
    if not df.empty and "month" in df.columns:
        months_in_data = sorted(df["month"].unique().tolist())

    if months_in_data:
        selected_month = st.sidebar.selectbox(
            "📅 Travel Month",
            options=months_in_data,
            index=0,
        )
    else:
        selected_month = None

    # Budget slider
    if not df.empty and "price" in df.columns:
        min_price = float(df["price"].min())
        max_price = float(df["price"].max())

        # Add some padding to the range
        price_range = max_price - min_price
        slider_max = max_price + \
            (price_range * 0.1) if price_range > 0 else max_price + 100

        max_budget = st.sidebar.slider(
            "💰 Maximum Budget (SGD)",
            min_value=min_price,
            max_value=slider_max,
            value=slider_max,
            step=10.0,
            format="$%.0f",
        )
    else:
        max_budget = float("inf")

    # Price drops filter
    show_drops_only = st.sidebar.checkbox(
        "📉 Show Price Drops Only",
        value=False,
        help="Only show destinations where the price has decreased since the last update",
    )

    # Wishlist section
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### ❤️ Wishlist ({len(wishlist)} items)")

    if wishlist:
        with st.sidebar.expander("View saved flights", expanded=False):
            for i, destination in enumerate(wishlist):
                col1, col2 = st.columns([0.85, 0.15])
                with col1:
                    st.text(destination)
                with col2:
                    if st.button("✕", key=f"remove_wishlist_{i}", help="Remove from wishlist"):
                        wishlist.pop(i)
                        save_wishlist(wishlist)
                        st.rerun()
    else:
        st.sidebar.info(
            "No flights saved yet. Click on any flight to view details and save!")

    # Info section
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ About")
    st.sidebar.markdown(
        """
        This dashboard shows flight deals from **Singapore (SIN)** 
        to destinations worldwide.
        
        - 🟢 Green = Price dropped
        - 🔴 Red = Price increased
        - ⚪ Gray = No change / New
        
        Data is updated every 6 hours via GitHub Actions.
        """
    )

    return max_budget, show_drops_only, selected_month


def render_kpi_metrics(df: pd.DataFrame) -> None:
    """
    Render KPI metrics row.

    Args:
        df: Filtered flight data DataFrame
    """
    col1, col2, col3, col4 = st.columns(4)

    total_destinations = len(df)

    # Count price drops (negative price_diff)
    if "price_diff" in df.columns:
        deals_count = int((df["price_diff"] < 0).sum())
        price_increases = int((df["price_diff"] > 0).sum())
        avg_savings = df[df["price_diff"] <
                         0]["price_diff"].mean() if deals_count > 0 else 0
    else:
        deals_count = 0
        price_increases = 0
        avg_savings = 0

    # Get cheapest destination
    if not df.empty and "price" in df.columns:
        cheapest_price = df["price"].min()
    else:
        cheapest_price = 0

    with col1:
        st.metric(
            label="🌍 Total Destinations",
            value=total_destinations,
        )

    with col2:
        st.metric(
            label="🔥 Price Drops",
            value=deals_count,
            delta=f"{deals_count} deals!" if deals_count > 0 else None,
            delta_color="normal",
        )

    with col3:
        st.metric(
            label="📈 Price Increases",
            value=price_increases,
        )

    with col4:
        st.metric(
            label="💸 Cheapest Flight",
            value=f"${cheapest_price:,.0f}" if cheapest_price > 0 else "N/A",
        )


def get_price_badge(price_diff: float) -> str:
    """
    Generate HTML badge for price difference.

    Args:
        price_diff: Price difference value

    Returns:
        HTML string for the badge
    """
    if price_diff < 0:
        color = "#28a745"  # Green
        icon = "↓"
        text = f"{icon} ${abs(price_diff):,.0f}"
    elif price_diff > 0:
        color = "#dc3545"  # Red
        icon = "↑"
        text = f"{icon} ${abs(price_diff):,.0f}"
    else:
        color = "#6c757d"  # Gray
        text = "No change"

    return f'<span style="background-color: {color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600;">{text}</span>'


@st.dialog("Flight Details", width="large")
def show_flight_modal(flight: pd.Series) -> None:
    """
    Display flight details in a modal dialog popup.

    Args:
        flight: Series containing flight data
    """
    destination = flight.get("destination", "Unknown")
    airport_code = flight.get("airport_code", "")
    price = flight.get("price", 0)
    previous_price = flight.get("previous_price", price)
    price_diff = flight.get("price_diff", 0)
    airline = flight.get("airline", "")
    stops = flight.get("stops", 0)
    duration_mins = flight.get("duration_mins", 0)
    start_date = flight.get("start_date", "")
    end_date = flight.get("end_date", "")
    fetched_at = flight.get("fetched_at", "")
    thumbnail = flight.get("thumbnail", "")
    travel_duration = flight.get("travel_duration", "")

    # Handle NaN values
    if pd.isna(airport_code):
        airport_code = ""
    if pd.isna(duration_mins):
        duration_mins = 0
    if pd.isna(stops):
        stops = 0
    if pd.isna(price_diff):
        price_diff = 0
    if pd.isna(airline):
        airline = ""

    # Format flight duration (convert minutes to hours:minutes)
    if duration_mins > 0:
        hours = int(duration_mins // 60)
        minutes = int(duration_mins % 60)
        duration_str = f"{hours}h {minutes}m"
    else:
        duration_str = "N/A"

    # Parse last updated time
    last_updated = "Unknown"
    if fetched_at and not pd.isna(fetched_at):
        try:
            fetch_time = datetime.fromisoformat(
                str(fetched_at).replace('Z', '+00:00'))
            now = datetime.utcnow()
            delta = (now - fetch_time.replace(tzinfo=None)).total_seconds()
            if delta < 3600:
                last_updated = f"{int(delta / 60)} minutes ago"
            elif delta < 86400:
                last_updated = f"{int(delta / 3600)} hours ago"
            else:
                last_updated = f"{int(delta / 86400)} days ago"
        except Exception:
            last_updated = "Recently"

    # Check if in wishlist
    is_in_wishlist = destination in st.session_state.wishlist
    wishlist_button_text = "❤️ Saved to Wishlist" if is_in_wishlist else "🤍 Save to Wishlist"
    wishlist_button_color = "secondary" if is_in_wishlist else "primary"

    # Price badge color
    if price_diff < 0:
        price_badge_color = "#28a745"
        price_badge_text = f"↓ Save ${abs(price_diff):,.0f}"
    elif price_diff > 0:
        price_badge_color = "#dc3545"
        price_badge_text = f"↑ Increase ${abs(price_diff):,.0f}"
    else:
        price_badge_color = "#6c757d"
        price_badge_text = "No change"

    # Google Flights URL (use airport code if available, otherwise destination name)
    search_param = airport_code if airport_code else destination.split(",")[
        0].strip()
    google_flights_url = f"https://www.google.com/travel/explore?q={quote(search_param)}"

    # Flight details text for copying
    copy_text = f"{destination}\nPrice: ${price:,.0f}\nAirline: {airline if airline else 'N/A'}\nDates: {start_date} → {end_date}\nStops: {stops}\nDuration: {duration_str}"

    # Default placeholder image if no thumbnail
    if not thumbnail or pd.isna(thumbnail):
        thumbnail = "https://via.placeholder.com/500x200/1a1a2e/ffffff?text=✈️"

    # Flight image
    st.image(thumbnail, use_container_width=True)

    # Flight title and price
    st.markdown(f"## {destination}")
    col_price, col_badge = st.columns([1, 1])
    with col_price:
        st.markdown(
            f"<h1 style='color: #1a1a2e; margin: 0;'>${float(price):,.0f}</h1>", unsafe_allow_html=True)
    with col_badge:
        st.markdown(
            f'<div style="padding-top: 20px;"><span style="background-color: {price_badge_color}; color: white; padding: 8px 16px; border-radius: 20px; font-size: 1rem; font-weight: 600;">{price_badge_text}</span></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Details section
    st.markdown("### 📋 Flight Details")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"**Airport Code:** {airport_code if airport_code else 'N/A'}")
        st.markdown(f"**Airline:** {airline if airline else 'N/A'}")
        st.markdown(
            f"**Stops:** {'Direct' if stops == 0 else f'{int(stops)} stop(s)'}")
    with col2:
        st.markdown(f"**Duration:** {duration_str}")
        st.markdown(
            f"**Trip Length:** {travel_duration if travel_duration else 'N/A'}")

    st.markdown("---")

    # Pricing section
    st.markdown("### 💰 Pricing")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current Price", f"${float(price):,.0f}")
    with col2:
        st.metric("Previous Price", f"${float(previous_price):,.0f}",
                  delta=f"${float(price_diff):,.0f}" if price_diff != 0 else None)

    st.markdown("---")

    # Price History Chart section
    st.markdown("### 📈 Price History")
    try:
        if PRICE_HISTORY_CSV.exists():
            history_df = pd.read_csv(PRICE_HISTORY_CSV)
            # Filter by composite key: destination + travel_duration + start_date
            flight_history = history_df[
                (history_df["destination"] == destination) &
                (history_df["travel_duration"] == travel_duration) &
                (history_df["start_date"] == start_date)
            ].copy()

            if not flight_history.empty and len(flight_history) > 0:
                # Sort by fetched_at timestamp
                flight_history["fetched_at"] = pd.to_datetime(
                    flight_history["fetched_at"])
                flight_history = flight_history.sort_values("fetched_at")

                # Calculate price changes for coloring markers
                flight_history["price_change"] = flight_history["price"].diff().fillna(
                    0)

                # Create color list: green for drops, red for increases, blue for no change/first
                colors = []
                for i, change in enumerate(flight_history["price_change"]):
                    if i == 0:
                        colors.append("#007bff")  # Blue for first point
                    elif change < 0:
                        colors.append("#28a745")  # Green for price drop
                    elif change > 0:
                        colors.append("#dc3545")  # Red for price increase
                    else:
                        colors.append("#6c757d")  # Gray for no change

                # Create plotly figure
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=flight_history["fetched_at"],
                    y=flight_history["price"],
                    mode="lines+markers",
                    line=dict(color="#1a1a2e", width=2),
                    marker=dict(size=10, color=colors,
                                line=dict(width=2, color="white")),
                    hovertemplate="<b>%{x|%b %d, %Y %H:%M}</b><br>Price: $%{y:,.0f}<extra></extra>",
                    name="Price"
                ))

                # Add min/max annotations if multiple data points
                if len(flight_history) > 1:
                    min_price = flight_history["price"].min()
                    max_price = flight_history["price"].max()
                    min_row = flight_history[flight_history["price"]
                                             == min_price].iloc[0]
                    max_row = flight_history[flight_history["price"]
                                             == max_price].iloc[0]

                    fig.add_annotation(
                        x=min_row["fetched_at"], y=min_price,
                        text=f"Low: ${min_price:,.0f}",
                        showarrow=True, arrowhead=2, arrowcolor="#28a745",
                        font=dict(color="#28a745", size=10),
                        ax=0, ay=-30
                    )
                    if max_price != min_price:
                        fig.add_annotation(
                            x=max_row["fetched_at"], y=max_price,
                            text=f"High: ${max_price:,.0f}",
                            showarrow=True, arrowhead=2, arrowcolor="#dc3545",
                            font=dict(color="#dc3545", size=10),
                            ax=0, ay=30
                        )

                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Price (SGD)",
                    height=280,
                    margin=dict(l=0, r=0, t=10, b=0),
                    hovermode="x unified",
                    showlegend=False,
                    xaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
                    yaxis=dict(showgrid=True, gridcolor="#f0f0f0",
                               tickprefix="$")
                )

                st.plotly_chart(fig, use_container_width=True)

                # Show summary stats
                if len(flight_history) > 1:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"🟢 Lowest: ${min_price:,.0f}")
                    with col2:
                        st.caption(f"🔴 Highest: ${max_price:,.0f}")
                    with col3:
                        st.caption(f"📊 Data points: {len(flight_history)}")
            else:
                st.info(
                    "📭 No price history available yet. Check back after the next data refresh!")
        else:
            st.info(
                "📭 No price history available yet. Check back after the next data refresh!")
    except Exception as e:
        st.warning(f"Could not load price history: {e}")

    st.markdown("---")

    # Timing section
    st.markdown("### 📅 Travel Dates")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"**Departure:** {start_date if start_date and not pd.isna(start_date) else 'N/A'}")
    with col2:
        st.markdown(
            f"**Return:** {end_date if end_date and not pd.isna(end_date) else 'N/A'}")
    st.markdown(f"**Last Updated:** {last_updated}")

    st.markdown("---")

    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button(wishlist_button_text, key="modal_wishlist_btn", use_container_width=True, type=wishlist_button_color):
            if is_in_wishlist:
                st.session_state.wishlist.remove(destination)
            else:
                st.session_state.wishlist.append(destination)
            save_wishlist(st.session_state.wishlist)
            st.rerun()

    with col2:
        if st.button("📋 Copy Details", key="modal_copy_btn", use_container_width=True):
            st.code(copy_text, language=None)

    # Google Flights button
    st.markdown(f'<a href="{google_flights_url}" target="_blank" style="display: block; text-align: center; background-color: #007bff; color: white; padding: 12px 16px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 12px;">🌐 View on Google Flights</a>', unsafe_allow_html=True)


def render_flight_card(flight: pd.Series, flight_unique_id: str) -> None:
    """
    Render a single flight card (clickable).

    Args:
        flight: Series containing flight data
        flight_unique_id: Unique ID for this flight card
    """
    destination = flight.get("destination", "Unknown")
    price = flight.get("price", 0)
    price_diff = flight.get("price_diff", 0)
    previous_price = flight.get("previous_price", price)
    thumbnail = flight.get("thumbnail", "")
    start_date = flight.get("start_date", "")
    end_date = flight.get("end_date", "")
    airline = flight.get("airline", "")
    stops = flight.get("stops", 0)

    # Handle NaN values
    if pd.isna(price_diff):
        price_diff = 0
    if pd.isna(previous_price):
        previous_price = price
    if pd.isna(stops):
        stops = 0

    # Price badge HTML
    price_badge = get_price_badge(float(price_diff))

    # Date display
    date_text = ""
    if start_date and not pd.isna(start_date) and end_date and not pd.isna(end_date):
        date_text = f"📅 {start_date} → {end_date}"
    elif start_date and not pd.isna(start_date):
        date_text = f"📅 {start_date}"

    # Airline and stops info
    flight_info = ""
    if airline and not pd.isna(airline):
        stops_text = "Direct" if stops == 0 else f"{int(stops)} stop{'s' if stops > 1 else ''}"
        flight_info = f"✈️ {airline} • {stops_text}"

    # Default placeholder image if no thumbnail
    if not thumbnail or pd.isna(thumbnail):
        thumbnail = "https://via.placeholder.com/400x200/1a1a2e/ffffff?text=✈️"

    # Card HTML - using single line styles to avoid Streamlit rendering issues
    card_html = f'''<div style="background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;" onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 8px 16px rgba(0,0,0,0.15)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)';">
<div style="height: 140px; background-image: url('{thumbnail}'); background-size: cover; background-position: center;"></div>
<div style="padding: 16px;">
<h3 style="margin: 0 0 8px 0; font-size: 1.1rem; color: #1a1a2e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{destination}</h3>
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
<span style="font-size: 1.5rem; font-weight: 700; color: #1a1a2e;">${float(price):,.0f}</span>
{price_badge}
</div>
<p style="color: #666; font-size: 0.8rem; margin: 0 0 4px 0;">{flight_info}</p>
<p style="color: #888; font-size: 0.8rem; margin: 0 0 8px 0;">{date_text}</p>
</div>
</div>'''

    st.markdown(card_html, unsafe_allow_html=True)

    # Use button below card to make it clickable with unique key
    if st.button("View Details →", key=f"btn_{flight_unique_id}", use_container_width=True, type="secondary"):
        show_flight_modal(flight)


def render_flight_grid(df: pd.DataFrame) -> None:
    """
    Render flight cards in a responsive grid.

    Args:
        df: Filtered flight data DataFrame
    """
    if df.empty:
        st.info(
            "No flights match your current filters. Try adjusting the budget or removing filters.")
        return

    # Sort by price (cheapest first)
    df_sorted = df.sort_values("price", ascending=True).reset_index(drop=True)

    # Create grid layout (4 columns)
    cols_per_row = 4
    rows = [df_sorted.iloc[i:i + cols_per_row]
            for i in range(0, len(df_sorted), cols_per_row)]

    for row_idx, row_data in enumerate(rows):
        cols = st.columns(cols_per_row)
        for idx, (flight_idx, flight) in enumerate(row_data.iterrows()):
            with cols[idx]:
                # Create unique ID using destination + travel_duration + month + start_date
                destination = flight.get("destination", "Unknown")
                travel_duration = flight.get("travel_duration", "")
                month = flight.get("month", "")
                start_date = flight.get("start_date", "")
                unique_string = f"{destination}_{travel_duration}_{month}_{start_date}_{flight_idx}"
                unique_id = hashlib.md5(unique_string.encode()).hexdigest()[:8]

                render_flight_card(flight, unique_id)
        st.markdown("<div style='height: 20px;'></div>",
                    unsafe_allow_html=True)


def main() -> None:
    """Main entry point for the Streamlit dashboard."""
    require_password()

    # Initialize session state
    if "wishlist" not in st.session_state:
        st.session_state.wishlist = load_wishlist()

    # Header
    st.title("✈️ Flight Explorer")
    st.markdown("Discover the best flight deals from Singapore to anywhere!")
    st.markdown("---")

    # Load data
    df = load_flight_data()

    # Handle empty state
    if df.empty:
        render_empty_state()
        return

    # Render sidebar and get filter values
    max_budget, show_drops_only, selected_month = render_sidebar(
        df, st.session_state.wishlist)

    # Apply filters
    filtered_df = df.copy()

    # Month filter
    if selected_month and "month" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["month"] == selected_month]

    # Budget filter
    if "price" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["price"] <= max_budget]

    # Price drops filter
    if show_drops_only and "price_diff" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["price_diff"] < 0]

    # Create tabs for each travel duration
    if "travel_duration" in filtered_df.columns:
        unique_durations = sorted(filtered_df["travel_duration"].unique())
        tabs = st.tabs(unique_durations)

        for tab, duration in zip(tabs, unique_durations):
            with tab:
                duration_df = filtered_df[filtered_df["travel_duration"] == duration]
                render_kpi_metrics(duration_df)
                st.markdown("---")
                render_flight_grid(duration_df)
    else:
        # Fallback if travel_duration column doesn't exist
        render_kpi_metrics(filtered_df)
        st.markdown("---")
        render_flight_grid(filtered_df)

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <p style="text-align: center; color: #888; font-size: 0.8rem;">
            Data sourced from Google Flights via SerpApi • 
            Last updated from CSV • 
            Built with Streamlit
        </p>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
