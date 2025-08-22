#!/usr/bin/env python3
"""
Models.dev API Interceptor
Intercepts requests to models.dev and returns only our proxy models
"""

from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Our limited model list
PROXY_MODELS = {
    "openrouter": {
        "id": "openrouter",
        "name": "Company Proxy",
        "api": "https://openrouter.ai/api",
        "env": ["OPENROUTER_API_KEY"],
        "models": {
            "openrouter/anthropic/claude-3.5-sonnet": {
                "id": "openrouter/anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet (Company Proxy)",
                "release_date": "2024-10-22",
                "attachment": True,
                "reasoning": False,
                "temperature": True,
                "tool_call": True,
                "cost": {"input": 3, "output": 15, "cache_read": 0.3, "cache_write": 3.75},
                "limit": {"context": 200000, "output": 8192},
                "options": {},
            },
            "openrouter/anthropic/claude-3-opus": {
                "id": "openrouter/anthropic/claude-3-opus",
                "name": "Claude 3 Opus (Company Proxy)",
                "release_date": "2024-02-29",
                "attachment": True,
                "reasoning": False,
                "temperature": True,
                "tool_call": True,
                "cost": {"input": 15, "output": 75, "cache_read": 1.5, "cache_write": 18.75},
                "limit": {"context": 200000, "output": 4096},
                "options": {},
            },
            "openrouter/openai/gpt-4": {
                "id": "openrouter/openai/gpt-4",
                "name": "GPT-4 (Company Proxy)",
                "release_date": "2023-03-14",
                "attachment": False,
                "reasoning": False,
                "temperature": True,
                "tool_call": True,
                "cost": {"input": 30, "output": 60},
                "limit": {"context": 8192, "output": 4096},
                "options": {},
            },
        },
    }
}


@app.route("/api.json")
@app.route("/api")
def get_models():
    """Return our limited model list instead of the full models.dev list"""
    return jsonify(PROXY_MODELS)


if __name__ == "__main__":
    print("Starting Models.dev Interceptor on port 8053")
    print("This will return only the 3 proxy models")
    app.run(host="0.0.0.0", port=8053, debug=True)
