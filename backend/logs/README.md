# Logs Directory

This directory contains application logs for the backend services.

The contents of this directory are not tracked in Git to avoid committing potentially sensitive information.

## Purpose

- Stores application logs
- Used for debugging and monitoring

## Log Files

Typical log files include:
- `price_finder_integration.log`: Logs from the price finder integration
- `scheduler.log`: Logs from the scheduler service
- `db_migrations.log`: Database migration logs

## Notes

- Files in this directory are automatically excluded from Git via `.gitignore`
- The application will create this directory if it doesn't exist 