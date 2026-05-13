#!/bin/bash

# rebuild-podman.sh
# Comprehensive Podman cleanup and rebuild script for tax-buddy
# This script will remove ALL containers, images, and cache, then rebuild from scratch

set -e  # Exit on error

echo "=========================================="
echo "Tax-Buddy Podman Complete Rebuild Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Stop ALL running containers
echo -e "${YELLOW}Step 1: Stopping all running containers...${NC}"
if [ "$(podman ps -q)" ]; then
    podman stop $(podman ps -q)
    echo -e "${GREEN}✓ All running containers stopped${NC}"
else
    echo "No running containers found"
fi
echo ""

# Step 2: Remove ALL containers (running and stopped)
echo -e "${YELLOW}Step 2: Removing all containers...${NC}"
if [ "$(podman ps -aq)" ]; then
    # First attempt: Force remove all containers
    echo "Attempting to force remove all containers..."
    podman rm -f $(podman ps -aq) 2>/dev/null || true
    
    # Second attempt: Use container prune to handle dependencies
    echo "Running container prune to handle any remaining containers..."
    podman container prune -f
    
    # Third attempt: Remove any remaining containers one by one
    if [ "$(podman ps -aq)" ]; then
        echo "Removing remaining containers individually..."
        for container in $(podman ps -aq); do
            podman rm -f "$container" 2>/dev/null || true
        done
    fi
    
    # Final verification
    if [ "$(podman ps -aq)" ]; then
        echo -e "${RED}⚠ Warning: Some containers could not be removed${NC}"
        echo "Remaining containers:"
        podman ps -a
    else
        echo -e "${GREEN}✓ All containers removed${NC}"
    fi
else
    echo "No containers found"
fi
echo ""

# Step 3: Remove ALL images related to tax-buddy
echo -e "${YELLOW}Step 3: Removing tax-buddy images...${NC}"
# Remove images by name pattern
if [ "$(podman images -q 'tax-buddy*')" ]; then
    podman rmi -f $(podman images -q 'tax-buddy*')
    echo -e "${GREEN}✓ Tax-buddy images removed${NC}"
else
    echo "No tax-buddy images found"
fi

# Also remove images from docker-compose (localhost prefix)
if [ "$(podman images -q 'localhost/tax-buddy*')" ]; then
    podman rmi -f $(podman images -q 'localhost/tax-buddy*')
    echo -e "${GREEN}✓ Localhost tax-buddy images removed${NC}"
fi
echo ""

# Step 4: Remove dangling images
echo -e "${YELLOW}Step 4: Removing dangling images...${NC}"
if [ "$(podman images -f 'dangling=true' -q)" ]; then
    podman rmi $(podman images -f 'dangling=true' -q)
    echo -e "${GREEN}✓ Dangling images removed${NC}"
else
    echo "No dangling images found"
fi
echo ""

# Step 5: Clean up all Podman cache and unused data
echo -e "${YELLOW}Step 5: Cleaning up Podman cache and unused data...${NC}"
podman system prune -af --volumes
echo -e "${GREEN}✓ Podman cache cleaned${NC}"
echo ""

# Step 6: Verify cleanup
echo -e "${YELLOW}Step 6: Verifying cleanup...${NC}"
echo "Remaining containers:"
podman ps -a
echo ""
echo "Remaining images:"
podman images
echo ""

# Step 7: Rebuild from scratch
echo -e "${YELLOW}Step 7: Building fresh images...${NC}"
podman-compose build --no-cache
echo -e "${GREEN}✓ Fresh images built${NC}"
echo ""

# Step 8: Start fresh containers
echo -e "${YELLOW}Step 8: Starting fresh containers...${NC}"
podman-compose up -d
echo -e "${GREEN}✓ Fresh containers started${NC}"
echo ""

# Step 9: Show running containers
echo -e "${YELLOW}Step 9: Verifying running containers...${NC}"
podman-compose ps
echo ""

# Step 10: Show logs
echo -e "${YELLOW}Step 10: Showing container logs (last 20 lines)...${NC}"
echo "Backend logs:"
podman-compose logs --tail=20 backend
echo ""
echo "Frontend logs:"
podman-compose logs --tail=20 frontend
echo ""

echo -e "${GREEN}=========================================="
echo "Rebuild Complete!"
echo "==========================================${NC}"
echo ""
echo "Your containers are now running with fresh images."
echo ""
echo "Useful commands:"
echo "  - View logs: podman-compose logs -f"
echo "  - Stop containers: podman-compose down"
echo "  - Restart: podman-compose restart"
echo "  - Check status: podman-compose ps"
echo ""

# Made with Bob
