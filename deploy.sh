#!/bin/bash

# Simple deployment script for personal-notebook
# 1. Update current branch to match main (preserve unversioned files)
# 2. Build and run Docker containers

set -e  # Exit on any error

echo "🚀 Starting deployment..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}[INFO]${NC} Fetching latest changes..."
git fetch origin

echo -e "${BLUE}[INFO]${NC} Updating to latest main branch..."
git checkout main
git reset --hard origin/main

echo -e "${GREEN}[SUCCESS]${NC} Updated to latest main"
git log --oneline -1

echo -e "${BLUE}[INFO]${NC} Stopping containers..."
sudo docker compose down

echo -e "${BLUE}[INFO]${NC} Building containers..."
sudo docker compose build

echo -e "${BLUE}[INFO]${NC} Starting containers..."
sudo docker compose up -d

echo -e "${GREEN}[SUCCESS]${NC} Deployment complete!"
echo -e "${BLUE}[INFO]${NC} Containers:"
sudo docker compose ps