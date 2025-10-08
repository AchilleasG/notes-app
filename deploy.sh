#!/bin/bash

# Deployment script for personal-notebook
# This script:
# 1. Forces checkout to remote main (dumps local changes, keeps unversioned files)
# 2. Rebuilds and runs Docker containers

set -e  # Exit on any error

echo "🚀 Starting deployment process..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    print_error "Not in a git repository!"
    exit 1
fi

# Check if docker and docker-compose are available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi


print_status "Fetching latest changes from remote..."
git fetch origin

# Check if there are any local changes
if ! git diff-index --quiet HEAD --; then
    print_warning "Found local changes. These will be discarded!"
    git status --porcelain
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Deployment cancelled by user"
        exit 1
    fi
fi

# Save list of unversioned files before checkout
print_status "Identifying unversioned files to preserve..."
UNVERSIONED_FILES=$(git ls-files --others --exclude-standard)
if [ -n "$UNVERSIONED_FILES" ]; then
    print_warning "Found unversioned files that will be preserved:"
    echo "$UNVERSIONED_FILES"
fi



print_status "Switching to main branch and updating to latest remote version..."
git checkout main
git reset --hard origin/main

print_success "Successfully updated to latest main branch"

# Show current commit info
print_status "Current commit:"
git log --oneline -1

print_status "Rebuilding Docker images..."
sudo docker compose build --no-cache

print_status "Starting Docker containers..."
sudo docker compose up -d

print_status "Waiting for containers to start..."
sleep 10

# Check if containers are running
if sudo docker compose ps | grep -q "Up"; then
    print_success "Docker containers are running!"
    
    print_status "Container status:"
    sudo docker compose ps
    
    print_status "Application should be available at http://localhost:8001"
    
    # Show logs for a few seconds
    print_status "Recent logs:"
    timeout 5 sudo docker compose logs --tail=20 || true
    
else
    print_error "Some containers failed to start!"
    sudo docker compose ps
    print_status "Container logs:"
    sudo docker compose logs
    exit 1
fi

print_success "🎉 Deployment completed successfully!"
print_status "To view logs: sudo docker compose logs -f"
print_status "To stop: sudo docker compose down"
