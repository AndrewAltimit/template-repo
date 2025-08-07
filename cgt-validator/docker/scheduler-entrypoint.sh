#!/bin/bash
# Entrypoint script for the scheduler container

set -e

# Function to run the scraper
run_scraper() {
    {
        echo "$(date): Starting scheduled scraping"
        python -m scrapers.scheduler run --all-states 2>&1
        echo "$(date): Scraping completed"
    } >> /app/logs/scheduler.log

    # Clean up old logs (keep last 30 days)
    find /app/logs -name "*.log" -mtime +30 -delete 2>/dev/null || true
}

# Export the function so it's available to cron
export -f run_scraper

# Create the cron job based on the SCHEDULE environment variable
SCHEDULE="${SCHEDULE:-0 2 * * *}"  # Default: daily at 2 AM

# Write the cron job to a temporary file
echo "Creating cron schedule: $SCHEDULE"
cat > /tmp/crontab << EOF
# CGT Validator Scheduled Scraping
$SCHEDULE /bin/bash -c 'cd /app && export PYTHONPATH=/app/src && python -m scrapers.scheduler run --all-states >> /app/logs/scheduler.log 2>&1'

# Keep an empty line at the end
EOF

# Install the cron job for the current user (cgtuser)
crontab /tmp/crontab
rm /tmp/crontab

# Create initial log file
touch /app/logs/scheduler.log

echo "CGT Validator Scheduler Container Started"
echo "Schedule: $SCHEDULE"
echo "Logs: /app/logs/scheduler.log"

# Configure email notifications if enabled
if [ "$EMAIL_ENABLED" = "true" ] && [ -n "$FROM_EMAIL" ] && [ -n "$TO_EMAILS" ]; then
    echo "Configuring email notifications..."
    python << EOF
import json
import os

config = {
    'email_notifications': {
        'enabled': True,
        'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
        'smtp_port': int(os.environ.get('SMTP_PORT', '587')),
        'from_email': os.environ.get('FROM_EMAIL', ''),
        'to_emails': os.environ.get('TO_EMAILS', '').split(',')
    }
}

config_dir = '/app/config'
os.makedirs(config_dir, exist_ok=True)

with open(f'{config_dir}/scheduler_config.json', 'w') as f:
    json.dump(config, f, indent=2)

print("Email notifications configured successfully!")
EOF
fi

# Run the scraper once on startup (optional, can be removed if not desired)
echo "Running initial scraping..."
run_scraper

# Start cron in the foreground and tail the log file
# This keeps the container running
echo "Starting cron daemon..."
cron -f &
tail -f /app/logs/scheduler.log
