#!/bin/bash
# Enhanced startup script with port conflict handling

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting AFTIS BCA Statement Processor...${NC}"

# Run port conflict checker
if ! ./check-ports.sh; then
    echo -e "\n${YELLOW}🔧 Attempting automatic port conflict resolution...${NC}"
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        echo -e "${BLUE}📝 Creating .env file from example...${NC}"
        cp .env.example .env
    fi
    
    # Find available ports and update .env
    echo -e "${BLUE}🔍 Finding available ports...${NC}"
    
    # Find available AFTIS port
    AVAILABLE_AFTIS_PORT=8081
    while [ $AVAILABLE_AFTIS_PORT -lt 8100 ]; do
        if ! timeout 1 bash -c "</dev/tcp/localhost/$AVAILABLE_AFTIS_PORT" >/dev/null 2>&1; then
            break
        fi
        AVAILABLE_AFTIS_PORT=$((AVAILABLE_AFTIS_PORT + 1))
    done
    
    # Find available Postgres port
    AVAILABLE_POSTGRES_PORT=5433
    while [ $AVAILABLE_POSTGRES_PORT -lt 5450 ]; do
        if ! timeout 1 bash -c "</dev/tcp/localhost/$AVAILABLE_POSTGRES_PORT" >/dev/null 2>&1; then
            break
        fi
        AVAILABLE_POSTGRES_PORT=$((AVAILABLE_POSTGRES_PORT + 1))
    done
    
    # Update .env file
    echo -e "${YELLOW}📝 Updating .env with available ports...${NC}"
    sed -i "s/^AFTIS_PORT=.*/AFTIS_PORT=$AVAILABLE_AFTIS_PORT/" .env
    sed -i "s/^POSTGRES_PORT=.*/POSTGRES_PORT=$AVAILABLE_POSTGRES_PORT/" .env
    
    echo -e "${GREEN}✅ Updated ports: AFTIS=$AVAILABLE_AFTIS_PORT, Postgres=$AVAILABLE_POSTGRES_PORT${NC}"
fi

# Start services
echo -e "\n${BLUE}🐳 Starting Docker services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "\n${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 5

# Check service status
echo -e "\n${BLUE}📊 Service Status:${NC}"
docker-compose ps

# Get the actual port being used
ACTUAL_PORT=$(docker-compose port parser 8080 2>/dev/null | cut -d: -f2 || echo "N/A")

echo -e "\n${GREEN}🎉 AFTIS is ready!${NC}"
if [ "$ACTUAL_PORT" != "N/A" ]; then
    echo -e "${GREEN}📱 Web interface: http://localhost:$ACTUAL_PORT${NC}"
fi
echo -e "${GREEN}📁 Drop PDF files in: ./inbox/${NC}"
echo -e "\n${BLUE}📝 To stop services: docker-compose down${NC}"
echo -e "${BLUE}📊 To view logs: docker-compose logs -f${NC}"