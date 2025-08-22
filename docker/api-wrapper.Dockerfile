# Dockerfile for API Translation Wrapper and Mock Company API
FROM python:3.11-slim

WORKDIR /app

# Install required packages
RUN pip install --no-cache-dir \
    flask \
    flask-cors \
    requests

# Copy the services
COPY automation/proxy/mock_company_api.py /app/mock_company_api.py
COPY automation/proxy/api_translation_wrapper.py /app/api_translation_wrapper.py

# Make scripts executable
RUN chmod +x /app/*.py

# Default to running the translation wrapper
CMD ["python", "/app/api_translation_wrapper.py"]
