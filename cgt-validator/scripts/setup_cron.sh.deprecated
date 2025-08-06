#!/bin/bash
# Setup script for automated CGT scraping via cron

set -e

echo "CGT Validator - Automated Scraping Setup"
echo "========================================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "Please do not run this script as root"
   exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if CGT validator is installed
if ! python3 -c "import src" &> /dev/null; then
    echo "Installing CGT validator..."
    cd "$PROJECT_DIR"
    pip install -e .
fi

# Create log directory
LOG_DIR="$HOME/.cgt-validator/logs"
mkdir -p "$LOG_DIR"

# Create scraping script
SCRAPE_SCRIPT="$HOME/.cgt-validator/run_scraping.sh"
cat > "$SCRAPE_SCRIPT" << EOF
#!/bin/bash
# CGT Scraping Script

export PATH="\$HOME/.local/bin:\$PATH"
cd "$PROJECT_DIR"

# Log file with timestamp
LOG_FILE="$LOG_DIR/scraping_\$(date +%Y%m%d_%H%M%S).log"

echo "Starting CGT scraping at \$(date)" >> "\$LOG_FILE"

# Run the scheduler
python3 -m src.scrapers.scheduler run >> "\$LOG_FILE" 2>&1

# Keep only last 30 days of logs
find "$LOG_DIR" -name "scraping_*.log" -mtime +30 -delete

echo "Scraping completed at \$(date)" >> "\$LOG_FILE"
EOF

chmod +x "$SCRAPE_SCRIPT"

# Setup cron job
echo ""
echo "Setting up cron job..."
echo ""
echo "Choose scraping frequency:"
echo "1) Daily at 2 AM"
echo "2) Weekly on Mondays at 2 AM"
echo "3) Monthly on the 1st at 2 AM"
echo "4) Custom schedule"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        CRON_SCHEDULE="0 2 * * *"
        ;;
    2)
        CRON_SCHEDULE="0 2 * * 1"
        ;;
    3)
        CRON_SCHEDULE="0 2 1 * *"
        ;;
    4)
        echo "Enter custom cron schedule (e.g., '0 2 * * 1' for weekly on Mondays at 2 AM):"
        read CRON_SCHEDULE
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Add to crontab
CRON_JOB="$CRON_SCHEDULE $SCRAPE_SCRIPT"

# Check if job already exists
if crontab -l 2>/dev/null | grep -q "$SCRAPE_SCRIPT"; then
    echo "Updating existing cron job..."
    (crontab -l 2>/dev/null | grep -v "$SCRAPE_SCRIPT"; echo "$CRON_JOB") | crontab -
else
    echo "Adding new cron job..."
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
fi

echo ""
echo "✓ Cron job installed successfully!"
echo ""
echo "Schedule: $CRON_SCHEDULE"
echo "Script: $SCRAPE_SCRIPT"
echo "Logs: $LOG_DIR"
echo ""
echo "To view current cron jobs: crontab -l"
echo "To remove the cron job: crontab -e (and delete the line)"
echo ""

# Configure email notifications
read -p "Would you like to configure email notifications? (y/n): " configure_email

if [ "$configure_email" = "y" ]; then
    echo ""
    echo "Email Configuration"
    echo "==================="
    read -p "SMTP Server (e.g., smtp.gmail.com): " smtp_server
    read -p "SMTP Port (e.g., 587): " smtp_port
    read -p "From Email: " from_email
    read -p "To Email(s) (comma-separated): " to_emails

    # Update configuration
    python3 << EOF
from src.scrapers.scheduler import ScrapingScheduler
scheduler = ScrapingScheduler()
scheduler.config['email_notifications']['enabled'] = True
scheduler.config['email_notifications']['smtp_server'] = "$smtp_server"
scheduler.config['email_notifications']['smtp_port'] = int("$smtp_port")
scheduler.config['email_notifications']['from_email'] = "$from_email"
scheduler.config['email_notifications']['to_emails'] = "$to_emails".split(',')
scheduler.save_config()
print("Email notifications configured successfully!")
EOF
fi

echo ""
echo "Setup complete! The scraper will run automatically according to the schedule."
echo "You can manually run it with: $SCRAPE_SCRIPT"
