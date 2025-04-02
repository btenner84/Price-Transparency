import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

def setup_logging(
    log_dir: str = "logs",
    log_file: str = "price_finder.log",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    max_size: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 5
) -> logging.Logger:
    """Set up logging configuration for the price finder system.
    
    Args:
        log_dir: Directory to store log files
        log_file: Name of the log file
        console_level: Logging level for console output
        file_level: Logging level for file output
        max_size: Maximum size of log file before rotation (bytes)
        backup_count: Number of backup log files to keep
        
    Returns:
        Configured logger
    """
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Create and configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Create and configure file handler
    log_path = os.path.join(log_dir, log_file)
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=max_size, 
        backupCount=backup_count
    )
    file_handler.setLevel(file_level)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Add a separate file handler for errors
    error_log_path = os.path.join(log_dir, f"errors_{log_file}")
    error_file_handler = RotatingFileHandler(
        error_log_path, 
        maxBytes=max_size, 
        backupCount=backup_count
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(file_format)
    logger.addHandler(error_file_handler)
    
    logger.info(f"Logging initialized. Log files: {log_path}, {error_log_path}")
    
    return logger

def log_execution_time(logger: logging.Logger, start_time: datetime, operation: str):
    """Log the execution time of an operation.
    
    Args:
        logger: Logger instance
        start_time: Start time of the operation
        operation: Name of the operation
    """
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    if duration < 60:
        time_str = f"{duration:.2f} seconds"
    elif duration < 3600:
        time_str = f"{duration/60:.2f} minutes"
    else:
        time_str = f"{duration/3600:.2f} hours"
    
    logger.info(f"{operation} completed in {time_str}")

def log_exception(logger: logging.Logger, e: Exception, context: str = ""):
    """Log an exception with context.
    
    Args:
        logger: Logger instance
        e: Exception to log
        context: Context description for the exception
    """
    import traceback
    
    if context:
        logger.error(f"Exception in {context}: {str(e)}")
    else:
        logger.error(f"Exception: {str(e)}")
    
    logger.error(traceback.format_exc())

class StatsTracker:
    """Utility to track statistics during price file search operations."""
    
    def __init__(self, logger: logging.Logger):
        """Initialize the stats tracker.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
        self.reset()
    
    def reset(self):
        """Reset all statistics."""
        self.total_hospitals = 0
        self.hospitals_processed = 0
        self.hospitals_with_price_files = 0
        self.hospitals_without_price_files = 0
        self.search_errors = 0
        self.validation_errors = 0
        self.start_time = datetime.now()
    
    def record_hospital_processed(self, found_price_file: bool, had_error: bool = False):
        """Record processing of a hospital.
        
        Args:
            found_price_file: Whether a price file was found
            had_error: Whether an error occurred during processing
        """
        self.hospitals_processed += 1
        
        if had_error:
            self.search_errors += 1
        elif found_price_file:
            self.hospitals_with_price_files += 1
        else:
            self.hospitals_without_price_files += 1
    
    def record_validation_error(self):
        """Record a validation error."""
        self.validation_errors += 1
    
    def log_progress(self, force: bool = False):
        """Log current progress stats.
        
        Args:
            force: Whether to log stats regardless of percentage
        """
        if self.total_hospitals == 0:
            return
            
        pct_complete = (self.hospitals_processed / self.total_hospitals) * 100
        
        # Log stats every 5% progress or when forced
        if force or pct_complete % 5 < 0.1 or self.hospitals_processed == self.total_hospitals:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            
            rate = self.hospitals_processed / elapsed if elapsed > 0 else 0
            
            remaining_hospitals = self.total_hospitals - self.hospitals_processed
            est_remaining_seconds = remaining_hospitals / rate if rate > 0 else 0
            
            if est_remaining_seconds < 60:
                time_remaining = f"{est_remaining_seconds:.0f} seconds"
            elif est_remaining_seconds < 3600:
                time_remaining = f"{est_remaining_seconds/60:.1f} minutes"
            else:
                time_remaining = f"{est_remaining_seconds/3600:.1f} hours"
                
            self.logger.info(
                f"Progress: {self.hospitals_processed}/{self.total_hospitals} "
                f"({pct_complete:.1f}%) hospitals processed. "
                f"Found price files: {self.hospitals_with_price_files} "
                f"({self.hospitals_with_price_files/self.hospitals_processed*100:.1f}%). "
                f"Errors: {self.search_errors}. "
                f"Estimated time remaining: {time_remaining}"
            )
    
    def log_final_stats(self):
        """Log final statistics after processing is complete."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if elapsed < 60:
            time_str = f"{elapsed:.2f} seconds"
        elif elapsed < 3600:
            time_str = f"{elapsed/60:.2f} minutes"
        else:
            time_str = f"{elapsed/3600:.2f} hours"
        
        self.logger.info(
            f"Finished processing {self.hospitals_processed} hospitals in {time_str}. "
            f"Found price files: {self.hospitals_with_price_files} "
            f"({self.hospitals_with_price_files/self.hospitals_processed*100:.1f}% success rate). "
            f"Search errors: {self.search_errors}. "
            f"Validation errors: {self.validation_errors}."
        ) 