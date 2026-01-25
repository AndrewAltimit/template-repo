# Dashboard API Reference

The Economic Agents Dashboard provides a REST API and WebSocket endpoint for monitoring and controlling autonomous agents.

## Base URL

```
http://localhost:8080
```

Default port is 8080, configurable via `--port` flag or `DashboardConfig`.

## Authentication

Currently no authentication is required. For production deployments, consider adding authentication middleware.

## Endpoints

### Health & Status

#### GET /health

Health check endpoint.

**Response**
```json
{
  "status": "healthy",
  "service": "dashboard",
  "uptime_seconds": 3600
}
```

#### GET /status

Dashboard status with agent statistics.

**Response**
```json
{
  "health": {
    "status": "healthy",
    "service": "dashboard",
    "uptime_seconds": 3600
  },
  "agent_count": 5,
  "active_agent_count": 2,
  "websocket_clients": 3,
  "events_processed": 1250
}
```

---

### Agent Management

#### GET /agents

List all registered agents.

**Response**
```json
{
  "agents": [
    {
      "id": "agent-abc123",
      "name": "Agent 1",
      "status": "running",
      "mode": "Company",
      "personality": "Balanced",
      "balance": 150.50,
      "compute_hours": 18.5,
      "tasks_completed": 12,
      "current_cycle": 45,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

#### POST /agents

Create a new agent.

**Request Body**
```json
{
  "name": "My Agent",
  "engine_type": "Llm",
  "mode": "Company",
  "personality": "Balanced",
  "task_selection_strategy": "SkillMatch",
  "initial_balance": 100.0,
  "initial_compute_hours": 24.0,
  "survival_buffer_hours": 24.0,
  "company_threshold": 100.0,
  "max_cycles": 100
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | No | Auto-generated | Agent display name |
| `engine_type` | string | No | `"RuleBased"` | `"RuleBased"` or `"Llm"` |
| `mode` | string | No | `"Survival"` | `"Survival"` or `"Company"` |
| `personality` | string | No | `"Balanced"` | `"RiskAverse"`, `"Balanced"`, `"Aggressive"` |
| `task_selection_strategy` | string | No | `"BestRatio"` | See strategies below |
| `initial_balance` | number | No | 50.0 | Starting balance |
| `initial_compute_hours` | number | No | 24.0 | Starting compute hours |
| `survival_buffer_hours` | number | No | 24.0 | Minimum hours to maintain |
| `company_threshold` | number | No | 100.0 | Balance needed to form company |
| `max_cycles` | number | No | null | Maximum cycles (null = unlimited) |

**Task Selection Strategies:**
- `FirstAvailable` - Take first available task
- `HighestReward` - Maximize immediate reward
- `BestRatio` - Optimize reward/time ratio
- `Balanced` - Consider reward, difficulty, and time
- `SkillMatch` - Match agent skills to task requirements

**Response** (201 Created)
```json
{
  "id": "agent-xyz789",
  "name": "My Agent",
  "status": "stopped",
  "mode": "Company",
  "personality": "Balanced",
  "balance": 100.0,
  "compute_hours": 24.0,
  "tasks_completed": 0,
  "current_cycle": 0,
  "created_at": "2024-01-15T12:00:00Z"
}
```

#### GET /agents/:agent_id

Get detailed information about a specific agent.

**Response**
```json
{
  "agent": {
    "id": "agent-abc123",
    "name": "Agent 1",
    "status": "running",
    "mode": "Company",
    "personality": "Balanced",
    "balance": 150.50,
    "compute_hours": 18.5,
    "tasks_completed": 12,
    "current_cycle": 45,
    "created_at": "2024-01-15T10:30:00Z"
  },
  "recent_cycles": [
    {
      "cycle_number": 45,
      "decision_type": "WorkOnTasks",
      "task_completed": true,
      "reward_earned": 25.0,
      "duration_ms": 1250
    }
  ],
  "stats": {
    "total_earnings": 350.0,
    "total_expenses": 50.0,
    "success_rate": 0.92,
    "average_cycle_time_ms": 1100
  }
}
```

**Error Response** (404 Not Found)
```json
{
  "error": "Agent agent-xyz not found",
  "code": "AGENT_NOT_FOUND"
}
```

#### DELETE /agents/:agent_id

Delete an agent. Agent must be stopped first.

**Response**
```json
{
  "agent_id": "agent-abc123",
  "action": "deleted",
  "success": true,
  "message": "Agent deleted successfully"
}
```

**Error Response** (409 Conflict)
```json
{
  "error": "Cannot delete running agent. Stop it first.",
  "code": "AGENT_RUNNING"
}
```

#### POST /agents/:agent_id/start

Start an agent's execution loop.

**Request Body** (optional)
```json
{
  "max_cycles": 50
}
```

**Response**
```json
{
  "agent_id": "agent-abc123",
  "action": "started",
  "success": true,
  "message": "Agent started successfully"
}
```

**Error Response** (409 Conflict)
```json
{
  "error": "Agent is already running",
  "code": "AGENT_ALREADY_RUNNING"
}
```

#### POST /agents/:agent_id/stop

Stop a running agent.

**Response**
```json
{
  "agent_id": "agent-abc123",
  "action": "stopped",
  "success": true,
  "message": "Agent stopped successfully"
}
```

**Error Response** (409 Conflict)
```json
{
  "error": "Agent is not running",
  "code": "AGENT_NOT_RUNNING"
}
```

#### GET /agents/:agent_id/cycles

Get cycle history for an agent.

**Query Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | number | 100 | Maximum cycles to return |

**Response**
```json
{
  "agent_id": "agent-abc123",
  "cycles": [
    {
      "cycle_number": 45,
      "decision_type": "WorkOnTasks",
      "task_completed": true,
      "reward_earned": 25.0,
      "duration_ms": 1250
    },
    {
      "cycle_number": 44,
      "decision_type": "WorkOnCompany",
      "task_completed": false,
      "reward_earned": 0.0,
      "duration_ms": 800
    }
  ],
  "count": 2
}
```

---

### Metrics

#### GET /metrics

Get current metrics as JSON.

**Response**
```json
{
  "counters": {
    "tasks_completed": 150,
    "decisions_made": 500,
    "api_requests": 2500
  },
  "gauges": {
    "active_agents": 3,
    "total_balance": 450.75,
    "websocket_clients": 2
  },
  "timestamp": "2024-01-15T12:30:00Z"
}
```

#### GET /metrics/prometheus

Get metrics in Prometheus format.

**Response** (text/plain)
```
# TYPE tasks_completed counter
tasks_completed 150
# TYPE decisions_made counter
decisions_made 500
# TYPE active_agents gauge
active_agents 3
# TYPE total_balance gauge
total_balance 450.75
```

---

### Events

#### GET /events

Query the event log.

**Query Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | number | 100 | Maximum events to return |
| `event_type` | string | null | Filter by event type |
| `source` | string | null | Filter by source (agent ID) |

**Event Types:**
- `AgentStarted`
- `AgentStopped`
- `TaskClaimed`
- `TaskCompleted`
- `TaskFailed`
- `CompanyFormed`
- `InvestmentReceived`
- `DecisionMade`

**Response**
```json
{
  "events": [
    {
      "id": "evt-123",
      "event_type": "TaskCompleted",
      "source": "agent-abc123",
      "payload": {
        "task_id": "task-456",
        "reward": 25.0,
        "quality_score": 0.95
      },
      "timestamp": "2024-01-15T12:25:00Z"
    }
  ],
  "count": 1
}
```

---

### Decisions

#### GET /decisions

Query the decision log.

**Query Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | number | 100 | Maximum decisions to return |
| `agent_id` | string | null | Filter by agent ID |

**Response**
```json
{
  "decisions": [
    {
      "id": "dec-789",
      "agent_id": "agent-abc123",
      "decision_type": "WorkOnTasks",
      "reasoning": "Balance is low, need to complete tasks for income",
      "confidence": 0.85,
      "outcome": "success",
      "timestamp": "2024-01-15T12:20:00Z"
    }
  ],
  "count": 1
}
```

---

### WebSocket

#### GET /ws

WebSocket endpoint for real-time updates.

**Connection**
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message);
};
```

**Message Types**

**Agent Update**
```json
{
  "type": "AgentUpdate",
  "data": {
    "id": "agent-abc123",
    "name": "Agent 1",
    "status": "running",
    "balance": 175.50,
    "compute_hours": 16.0,
    "tasks_completed": 15,
    "current_cycle": 48
  }
}
```

**Event**
```json
{
  "type": "Event",
  "data": {
    "id": "evt-456",
    "event_type": "TaskCompleted",
    "source": "agent-abc123",
    "payload": { ... },
    "timestamp": "2024-01-15T12:30:00Z"
  }
}
```

**Error**
```json
{
  "type": "Error",
  "data": {
    "code": "INTERNAL_ERROR",
    "message": "Something went wrong"
  }
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": { }  // Optional additional information
}
```

**Common Error Codes:**
| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AGENT_NOT_FOUND` | 404 | Agent ID does not exist |
| `AGENT_RUNNING` | 409 | Operation not allowed while running |
| `AGENT_NOT_RUNNING` | 409 | Operation requires running agent |
| `AGENT_ALREADY_RUNNING` | 409 | Agent is already running |
| `INVALID_REQUEST` | 400 | Malformed request body |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Usage Examples

### cURL

**Create an agent:**
```bash
curl -X POST http://localhost:8080/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Agent",
    "mode": "Company",
    "personality": "Aggressive",
    "initial_balance": 200.0
  }'
```

**Start the agent:**
```bash
curl -X POST http://localhost:8080/agents/agent-abc123/start \
  -H "Content-Type: application/json" \
  -d '{"max_cycles": 50}'
```

**Watch events:**
```bash
curl "http://localhost:8080/events?limit=10&event_type=TaskCompleted"
```

### JavaScript

```javascript
// Create and start an agent
async function runAgent() {
  // Create
  const createRes = await fetch('http://localhost:8080/agents', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'JS Agent',
      mode: 'Company',
      initial_balance: 100.0
    })
  });
  const agent = await createRes.json();

  // Start
  await fetch(`http://localhost:8080/agents/${agent.id}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ max_cycles: 100 })
  });

  // Subscribe to updates
  const ws = new WebSocket('ws://localhost:8080/ws');
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'AgentUpdate' && msg.data.id === agent.id) {
      console.log('Agent update:', msg.data);
    }
  };
}
```

### Python

```python
import requests
import websocket
import json

BASE_URL = "http://localhost:8080"

# Create agent
agent = requests.post(f"{BASE_URL}/agents", json={
    "name": "Python Agent",
    "mode": "Survival",
    "personality": "RiskAverse"
}).json()

# Start agent
requests.post(f"{BASE_URL}/agents/{agent['id']}/start", json={
    "max_cycles": 50
})

# Poll for status
status = requests.get(f"{BASE_URL}/agents/{agent['id']}").json()
print(f"Balance: {status['agent']['balance']}")

# WebSocket for real-time updates
def on_message(ws, message):
    data = json.loads(message)
    print(f"Received: {data['type']}")

ws = websocket.WebSocketApp(
    "ws://localhost:8080/ws",
    on_message=on_message
)
ws.run_forever()
```

---

## Configuration

### Server Configuration

```rust
use economic_agents_dashboard::{DashboardConfig, DashboardService};

let config = DashboardConfig {
    port: 8080,
    host: "0.0.0.0".to_string(),
    enable_cors: true,
    enable_tracing: true,
};

let service = DashboardService::with_default_state(config);
service.run().await?;
```

### CLI Options

```bash
economic-agents dashboard --port 9000 --host 127.0.0.1
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8080 | Port to listen on |
| `--host` | 0.0.0.0 | Host to bind to |
