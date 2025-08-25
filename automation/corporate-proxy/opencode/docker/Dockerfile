# Simple OpenCode Corporate Proxy Container
# Without patches - uses environment variables for configuration

FROM node:20-alpine

# Install Python for proxy services
RUN apk add --no-cache python3 py3-pip bash curl

# Install OpenCode CLI via npm
RUN npm install -g @sst/opencode

# Install Python dependencies for proxy
RUN pip3 install --break-system-packages flask flask-cors requests

# Copy shared services
COPY shared/services/mock_api.py /app/mock_api.py
COPY shared/services/translation_wrapper.py /app/translation_wrapper.py

# Create startup script
RUN echo '#!/bin/bash' > /app/start-services.sh && \
    echo 'python3 /app/mock_api.py &' >> /app/start-services.sh && \
    echo 'python3 /app/translation_wrapper.py &' >> /app/start-services.sh && \
    echo 'sleep 3' >> /app/start-services.sh && \
    echo 'exec "$@"' >> /app/start-services.sh && \
    chmod +x /app/start-services.sh

WORKDIR /workspace

# Environment variables for OpenCode to use our proxy
ENV OPENROUTER_API_KEY="test-secret-token-123"
ENV OPENROUTER_BASE_URL="http://localhost:8052/v1"

# Environment for proxy services
ENV COMPANY_API_BASE="http://localhost:8050"
ENV COMPANY_API_TOKEN="test-secret-token-123"
ENV WRAPPER_PORT="8052"
ENV MOCK_API_PORT="8050"

EXPOSE 8050 8052

ENTRYPOINT ["/app/start-services.sh"]
CMD ["bash"]
