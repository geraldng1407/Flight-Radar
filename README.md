# ✈️ Flight Explorer Dashboard

A stateless flight deal explorer that fetches "Anywhere" flight deals from Singapore, tracks price changes over time, and displays them in a beautiful Streamlit dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- 🔍 **Flight Discovery**: Automatically fetches flight deals from Singapore (SIN) to destinations worldwide
- 📊 **Price Tracking**: Tracks price changes between updates with historical diff retention
- 📉 **Deal Detection**: Highlights price drops and increases with color-coded badges
- 🎛️ **Smart Filtering**: Filter by budget and show only price drops
- 🤖 **Automated Updates**: GitHub Actions workflow runs every 6 hours
- 📱 **Responsive UI**: Clean card-based layout that works on any screen size

## Project Structure

```
flight-explorer/
├── .github/
│   └── workflows/
│       └── update-flights.yml    # GitHub Actions automation
├── data/
│   └── flights.csv               # Flight data storage
├── src/
│   ├── fetch_flights.py          # Data ingestion script
│   └── app.py                    # Streamlit dashboard
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── .gitignore
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10 or higher
- [SerpApi](https://serpapi.com/) account and API key

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/flight-explorer.git
   cd flight-explorer
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your SERPAPI_KEY
   ```

5. **Fetch initial flight data**
   ```bash
   python src/fetch_flights.py
   ```

6. **Run the dashboard**
   ```bash
   streamlit run src/app.py
   ```

   The dashboard will be available at `http://localhost:8501`

## GitHub Actions Setup

The project includes an automated workflow that fetches flight data every 6 hours.

### Enable Automation

1. **Add your API key as a secret**
   - Go to your repository on GitHub
   - Navigate to **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `SERPAPI_KEY`
   - Value: Your SerpApi API key

2. **Enable GitHub Actions**
   - Go to the **Actions** tab in your repository
   - Enable workflows if prompted

3. **Manual trigger** (optional)
   - Go to **Actions** → **Update Flight Data**
   - Click **Run workflow** → **Run workflow**

### Workflow Features

- **Schedule**: Runs at 0:00, 6:00, 12:00, and 18:00 UTC
- **Concurrency Control**: Cancels in-progress runs if a new one starts
- **Automatic Commits**: Pushes updated `flights.csv` back to the repository

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SERPAPI_KEY` | Your SerpApi API key | Yes |

### API Parameters

You can modify these in `src/fetch_flights.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEPARTURE_ID` | `"SIN"` | Departure airport code (Singapore Changi) |
| `TRAVEL_DURATION` | `"1"` | Trip duration in weeks |
| `CURRENCY` | `"SGD"` | Currency for prices |

## Data Schema

The `flights.csv` file contains:

| Column | Type | Description |
|--------|------|-------------|
| `destination` | string | Destination name |
| `price` | float | Current price in SGD |
| `previous_price` | float | Price from last update |
| `price_diff` | float | Price change (current - previous) |
| `thumbnail` | string | Destination image URL |
| `start_date` | string | Departure date |
| `end_date` | string | Return date |
| `fetched_at` | string | Timestamp of data fetch (ISO format) |

## Deployment

### Streamlit Community Cloud

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository
4. Set the main file path to `src/app.py`
5. Deploy!

Note: For Streamlit Cloud, the dashboard reads from the `flights.csv` in your repository, which is updated by GitHub Actions.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgments

- Flight data powered by [SerpApi](https://serpapi.com/)
- Dashboard built with [Streamlit](https://streamlit.io/)
- Automated with [GitHub Actions](https://github.com/features/actions)