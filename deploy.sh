#!/bin/bash

# Production Deployment Script for Helpdesk Application
set -e

echo "🚀 Starting production deployment..."

# Configuration
APP_NAME="helpdesk"
APP_DIR="/var/www/helpdesk"
BACKUP_DIR="/var/backups/helpdesk"
VENV_DIR="$APP_DIR/venv"
REPO_URL="https://github.com/yourusername/helpdesk.git"  # Update this
BRANCH="main"  # or your production branch

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root for security reasons"
   exit 1
fi

# Create backup
create_backup() {
    log_info "Creating backup..."
    sudo mkdir -p $BACKUP_DIR
    BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    if [ -d "$APP_DIR" ]; then
        sudo tar -czf $BACKUP_FILE -C $APP_DIR .
        log_info "Backup created: $BACKUP_FILE"
    fi
}

# Update application code
update_code() {
    log_info "Updating application code..."
    
    if [ ! -d "$APP_DIR" ]; then
        log_info "Cloning repository..."
        sudo git clone $REPO_URL $APP_DIR
        sudo chown -R $USER:$USER $APP_DIR
    else
        log_info "Pulling latest changes..."
        cd $APP_DIR
        git fetch origin
        git reset --hard origin/$BRANCH
    fi
}

# Setup virtual environment
setup_venv() {
    log_info "Setting up virtual environment..."
    
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv $VENV_DIR
    fi
    
    source $VENV_DIR/bin/activate
    pip install --upgrade pip
    pip install -r requirements-prod.txt
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    source $VENV_DIR/bin/activate
    cd $APP_DIR
    
    export FLASK_APP=wsgi.py
    flask db upgrade
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    
    # Restart gunicorn (adjust service name as needed)
    sudo systemctl restart helpdesk
    sudo systemctl restart nginx
    
    # Check if services are running
    if sudo systemctl is-active --quiet helpdesk; then
        log_info "Helpdesk service is running"
    else
        log_error "Helpdesk service failed to start"
        exit 1
    fi
    
    if sudo systemctl is-active --quiet nginx; then
        log_info "Nginx service is running"
    else
        log_error "Nginx service failed to start"
        exit 1
    fi
}

# Main deployment process
main() {
    log_info "Starting deployment process..."
    
    create_backup
    update_code
    setup_venv
    run_migrations
    restart_services
    
    log_info "✅ Deployment completed successfully!"
    log_info "Application should be available at your configured domain"
}

# Run main function
main "$@"
