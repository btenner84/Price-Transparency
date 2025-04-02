# Project Omega - Hospital Price Transparency System

## System Overview

Project Omega is an integrated system for tracking and analyzing hospital price transparency information across the United States. The system consists of three primary components:

1. **Frontend** - Next.js web application with a cyberpunk-styled UI
2. **Backend** - FastAPI service that exposes hospital and price transparency data
3. **Price Finder** - A specialized module that searches for hospital price transparency files on the web

## System Architecture

```
╔════════════════════╗      ╔═══════════════════╗     ╔═══════════════════════╗
║                    ║      ║                   ║     ║                       ║
║  Frontend (Next.js)║◄────►║ Backend (FastAPI) ║◄───►║ Price Finder Module   ║
║                    ║      ║                   ║     ║                       ║
╚════════════════════╝      ╚═══════════════════╝     ╚═══════════════════════╝
         │                          │                           │
         │                          ▼                           │
         │                  ╔═══════════════════╗               │
         └─────────────────►║  SQLite Database  ║◄──────────────┘
                            ╚═══════════════════╝
```

### Components

#### Frontend (hospital-map-app/)

- Next.js application with React and TypeScript
- Interactive map visualization of hospitals across the US
- Hospital and health system search functionality
- Price transparency tracking and visualization
- Configuration in `app/config.ts` for API endpoints

#### Backend (backend/)

- FastAPI application
- Serves hospital and price transparency data from the database
- RESTful API endpoints for accessing data
- Integrates with the Price Finder module
- Custom status tracker implementation to manage price finder results

#### Price Finder (price-finder/)

- Python module for searching and validating hospital price transparency files
- Uses web search APIs (SerpAPI) to find potential transparency files
- Downloads and validates files using LLM-powered analysis (via Mistral or OpenAI)
- Customizable pipeline for hospital data processing

## Database Schema

The system uses a SQLite database with the following core models:

- `Hospital` - Information about hospitals (name, location, website, etc.)
- `HealthSystem` - Groups of hospitals under the same management
- `HospitalPriceFile` - Price transparency files found for hospitals
- `HospitalSearchLog` - Logs of price transparency search attempts

## Key Features

### Hospital Map and Filtering

- Interactive US map showing hospitals by state
- Filter hospitals by state, health system, and search status
- Detailed hospital information and transparency status

### Price Transparency Search

- Automated search for hospital price transparency files
- Integration with SerpAPI for web search capabilities
- File validation using LLMs to verify if files contain required pricing data
- Tracking of search progress and results

### Custom Database Integration

- The system uses a custom status tracker to integrate the Price Finder with the main application database
- This eliminates foreign key constraint issues by having all components use the same database

## Setup and Running

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm/yarn

### Installation

1. Clone the repository
2. Set up the Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. Install price-finder dependencies:
   ```bash
   cd price-finder
   pip install -r requirements.txt
   ```

5. Install frontend dependencies:
   ```bash
   cd hospital-map-app
   npm install
   ```

### Environment Configuration

1. Set up API keys in environment variables:
   - `SERPAPI_KEY` - For web search functionality
   - `MISTRAL_API_KEY` - For LLM content analysis
   - `OPENAI_API_KEY` - Alternative LLM provider

### Running the Application

1. Start the backend:
   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 5005 --reload
   ```

2. Start the frontend:
   ```bash
   cd hospital-map-app
   npm run dev
   ```

3. Access the application at `http://localhost:3000`

### Using the Price Finder

The price finder can be triggered via the API:

```bash
curl -X POST "http://localhost:5005/api/run-price-finder?state=DE&batch_size=3"
```

This will process the specified number of hospitals from the given state.

## Integration Details

### Custom Status Tracker

The Price Finder uses a custom status tracker (`MainDBStatusTracker`) to store results directly in the main application database. This custom tracker overrides the default SQLite tracker in the Price Finder module to:

1. Use the main application database instead of a separate price_finder.db
2. Map between Price Finder and application database models
3. Maintain search logs and file records

### Price Finder Pipeline

The price finder pipeline consists of several stages:

1. **Search** - Find potential price transparency pages using SerpAPI
2. **Crawl** - Extract links to data files from hospital websites
3. **Download** - Retrieve files for validation
4. **Validate** - Analyze file contents to confirm they contain proper pricing data
5. **Update** - Store results in the database

## Troubleshooting

### Common Issues

1. **Import Errors** - Ensure Python path includes all necessary directories
2. **Database Constraint Errors** - Check that foreign keys are properly maintained
3. **API Connection Issues** - Verify the backend port (5005) matches the frontend config
4. **LLM API Rate Limits** - Monitor usage of Mistral/OpenAI APIs to avoid hitting rate limits

## Development Notes

- The system is designed to be modular, allowing components to be updated independently
- The custom status tracker pattern can be used to integrate other systems with the main database
- Frontend and backend use different ports (3000 for frontend, 5005 for backend) 