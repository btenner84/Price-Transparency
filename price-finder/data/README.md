# Price Finder Data Directory

This directory contains data files used by the price finder service.

The contents of this directory are not tracked in Git to avoid committing potentially sensitive information.

## Purpose

- Stores the price finder database (`price_finder.db`)
- Temporary data files used during hospital price file searches
- Test data for the price finder service

## Notes

- Files in this directory are automatically excluded from Git via `.gitignore`
- The application will create this directory if it doesn't exist
- The database file may contain cached API responses with sensitive information 