#!/bin/bash
{
  echo "PostToolUse hook triggered!"
  date
  cat
  echo "---"
} >> ./claude-hook-test.log
