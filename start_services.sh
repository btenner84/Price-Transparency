#!/bin/bash
# Script to start both backend and frontend servers

# Define port numbers
BACKEND_PORT=5001
FRONTEND_PORT=3000

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo -e "${GREEN}Activated virtual environment${NC}"
else
    echo -e "${YELLOW}Warning: No virtual environment found at .venv${NC}"
fi

# Create logs directory in backend if it doesn't exist
mkdir -p backend/logs

# Check for existing processes
echo "Checking for existing processes..."
pkill -f "uvicorn.*$BACKEND_PORT" || echo "No backend processes killed"
pkill -f "node.*next" || echo "No frontend processes killed"
pkill -f "python.*scheduler.py" || echo "No scheduler processes killed"

# Starting from the right directory
cd "$(dirname "$0")"
BASEDIR=$(pwd)

# Start the backend server
echo -e "${GREEN}Starting backend server on port $BACKEND_PORT...${NC}"
cd "$BASEDIR/backend" && python -m uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!
echo "Backend running with PID: $BACKEND_PID"

# Wait for backend to start
echo "Waiting for backend to be ready..."
sleep 2

# Start the price finder scheduler
echo -e "${GREEN}Starting price finder scheduler...${NC}"
cd "$BASEDIR/backend" && python -m scripts.scheduler &
SCHEDULER_PID=$!
echo "Scheduler running with PID: $SCHEDULER_PID"

# Start the frontend server
echo -e "${GREEN}Starting frontend server...${NC}"
cd "$BASEDIR/hospital-map-app" && npm run dev &
FRONTEND_PID=$!
echo "Frontend running with PID: $FRONTEND_PID"

# Trap SIGINT (Ctrl+C) to cleanly stop all services
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID $SCHEDULER_PID 2>/dev/null; exit" INT

echo -e "${GREEN}All services running. Press Ctrl+C to stop.${NC}"
echo -e "${YELLOW}The price finder scheduler is running in the background and will automatically update the database.${NC}"

# Wait for background processes to finish (or for Ctrl+C)
wait 