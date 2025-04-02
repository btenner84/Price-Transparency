# Downloads Directory

This directory is used to store downloaded hospital price transparency files. 

The contents of this directory are not tracked in Git to avoid committing large files and potentially sensitive information.

## Purpose

- Stores downloaded hospital pricing data files in various formats (CSV, JSON, TXT, etc.)
- Used by the price finder pipeline when crawling hospital websites

## Notes

- Files in this directory are automatically excluded from Git via `.gitignore`
- The application will create this directory if it doesn't exist 