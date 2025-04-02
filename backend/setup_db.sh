#!/bin/bash
# Setup script for PostgreSQL database and data import

set -e  # Exit on error

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed. Please install it first."
    exit 1
fi

# Load variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Set default values if not in .env
DB_USER=${DB_USER:-bentenner}
DB_PASSWORD=${DB_PASSWORD:-}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-hospital_transparency}

echo "Setting up PostgreSQL database: $DB_NAME"

# Force drop and recreate the database
echo "Dropping database $DB_NAME if it exists..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "DROP DATABASE IF EXISTS $DB_NAME;" postgres

echo "Creating database $DB_NAME..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME;" postgres

# Setup virtual environment if it doesn't exist
if [ ! -d "../.venv" ]; then
    echo "Creating virtual environment..."
    cd .. && python -m venv .venv
    cd -
fi

# Activate virtual environment
source ../.venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Create tables and import data
echo "Creating database tables..."
python -c "from database import create_tables; create_tables()"

# Import hospital data
echo "Importing hospital data from Excel..."
python -m scripts.import_hospitals

echo "Database setup complete!" 