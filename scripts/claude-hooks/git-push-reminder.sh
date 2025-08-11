#!/bin/bash
# Simple script that checks for PR monitoring reminder after git operations

if [ -f ".git-push-reminder.txt" ]; then
    cat .git-push-reminder.txt
    rm .git-push-reminder.txt
fi
