#!/bin/bash
# Port Conflict Checker and Handler
# Checks for port conflicts and suggests solutions

set -e

# Default ports
DEFAULT_AFTIS_PORT=8080
DEFAULT_POSTGRES_PORT=5432

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if port is in use
check_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i ":$port" >/dev/null 2>&1
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tlnp 2>/dev/null | grep ":$port " >/dev/null
    elif command -v ss >/dev/null 2>&1; then
        ss -tlnp | grep ":$port " >/dev/null
    else
        # Fallback: try to bind to the port
        timeout 1 bash -c "</dev/tcp/localhost/$port" >/dev/null 2>&1
    fi
}

# Function to get process using port
get_port_process() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i ":$port" 2>/dev/null | tail -n +2 | awk '{print $1, $2}' | head -1
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f2 | head -1
    else
        echo "Unknown process"
    fi
}

# Function to find available port
find_available_port() {
    local start_port=$1
    local port=$start_port
    while [ $port -lt 65535 ]; do
        if ! check_port $port; then
            echo $port
            return 0
        fi
        port=$((port + 1))
    done
    echo "No available port found"
    return 1
}

# Load environment variables
if [ -f .env ]; then
    source .env
fi

AFTIS_PORT=${AFTIS_PORT:-$DEFAULT_AFTIS_PORT}
POSTGRES_PORT=${POSTGRES_PORT:-$DEFAULT_POSTGRES_PORT}

echo -e "${BLUE}🔍 Checking port availability...${NC}"

# Check AFTIS port
if check_port $AFTIS_PORT; then
    process=$(get_port_process $AFTIS_PORT)
    echo -e "${RED}❌ Port $AFTIS_PORT is already in use by: $process${NC}"
    
    # Suggest alternative port
    alternative_port=$(find_available_port $((AFTIS_PORT + 1)))
    if [ "$alternative_port" != "No available port found" ]; then
        echo -e "${YELLOW}💡 Suggested alternative port: $alternative_port${NC}"
        echo -e "${YELLOW}   To use this port, set: AFTIS_PORT=$alternative_port${NC}"
        echo -e "${YELLOW}   Add to .env file: echo 'AFTIS_PORT=$alternative_port' >> .env${NC}"
    fi
    PORT_CONFLICT=true
else
    echo -e "${GREEN}✅ Port $AFTIS_PORT is available${NC}"
fi

# Check PostgreSQL port
if check_port $POSTGRES_PORT; then
    process=$(get_port_process $POSTGRES_PORT)
    echo -e "${RED}❌ Port $POSTGRES_PORT is already in use by: $process${NC}"
    
    # Suggest alternative port
    alternative_port=$(find_available_port $((POSTGRES_PORT + 1)))
    if [ "$alternative_port" != "No available port found" ]; then
        echo -e "${YELLOW}💡 Suggested alternative port: $alternative_port${NC}"
        echo -e "${YELLOW}   To use this port, set: POSTGRES_PORT=$alternative_port${NC}"
        echo -e "${YELLOW}   Add to .env file: echo 'POSTGRES_PORT=$alternative_port' >> .env${NC}"
    fi
    PORT_CONFLICT=true
else
    echo -e "${GREEN}✅ Port $POSTGRES_PORT is available${NC}"
fi

if [ "${PORT_CONFLICT}" = "true" ]; then
    echo -e "\n${YELLOW}🛠️  Port Conflict Resolution Options:${NC}"
    echo -e "1. ${BLUE}Change ports:${NC} Modify .env file with suggested ports above"
    echo -e "2. ${BLUE}Stop conflicting services:${NC} Stop services using the conflicting ports"
    echo -e "3. ${BLUE}Use different environment:${NC} Use docker-compose with custom env file"
    echo ""
    echo -e "${YELLOW}Example .env configuration:${NC}"
    echo "AFTIS_PORT=$(find_available_port 8081)"
    echo "POSTGRES_PORT=$(find_available_port 5433)"
    echo ""
    exit 1
else
    echo -e "\n${GREEN}🎉 All ports are available! You can start the services.${NC}"
    exit 0
fi