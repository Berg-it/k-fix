# 🚀 K-Fix API Examples

This file contains all HTTP requests examples for testing and using the K-Fix project.

## 📋 Table of Contents

- [Environment Setup](#environment-setup)
- [Available Endpoints](#available-endpoints)
- [POST Examples](#post-examples)
- [Response Examples](#response-examples)
- [Testing with Different Tools](#testing-with-different-tools)

---

## 🔧 Environment Setup

### Local Development
```bash
# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Server will be available at:
# http://localhost:8000
# http://127.0.0.1:8000
```

### Environment Variables Required
```bash
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key
DD_SITE=datadoghq.eu  # or datadoghq.com
ENVIRONMENT=local     # for development
```

---

## 📡 Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/datadog-webhook` | Receive Datadog alerts and process them |
| GET | `/` | Health check endpoint |
| GET | `/docs` | FastAPI auto-generated documentation |

---

## 📨 POST Examples

### 1. Datadog Webhook - CPU Alert

```bash
curl -X POST http://127.0.0.1:8000/datadog-webhook \
     -H "Content-Type: application/json" \
     -d '{
       "event_id": "8301471716550744338",
       "alert_id": "90031991",
       "event_type": "query_alert_monitor",
       "title": "[Triggered] [TEST] High CPU usage detected on pod echo-77b7b5c4b-pmccz (deployment echo)",
       "body": "%%%\n🚨 CPU usage exceeded threshold\n\n- Namespace: \n\n- Deployment: echo\n\n- Pod: echo-77b7b5c4b-pmccz\n\n- Metric: \n\n- Value: 0.0 (Threshold: 4.0)\n\n[Monitor Status]() · [Related Logs]()\n\n@webhook-kfix-webhook\n\nTest notification triggered by m.a.berguiga.info@gmail.com.\n\n[![Metric Graph](https://p.datadoghq.eu/snapshot/view/dd-snapshots-eu1-prod/org_1000621888/2025-09-28/0aa0d36da0e06f3cc16fb6cbe26fa15d178e08cf.png)](https://app.datadoghq.eu/monitors/90031991?group=pod_name%3Aecho-77b7b5c4b-pmccz&from_ts=1759068238000&to_ts=1759069438000&event_id=8301471716550744338&link_source=monitor_notif)\n\n**kubernetes.cpu.usage.total** over **kube_deployment:echo,pod_name:echo-77b7b5c4b-pmccz** was **> 4.0** on average during the **last 5m**.\n\nThe monitor was last triggered at Sun Sep 28 2025 14:18:58 UTC.\n\n- - -\n\n[[Monitor Status](https://app.datadoghq.eu/monitors/90031991?group=pod_name%3Aecho-77b7b5c4b-pmccz&from_ts=1759068238000&to_ts=1759069438000&event_id=8301471716550744338&link_source=monitor_notif)] · [[Edit Monitor](https://app.datadoghq.eu/monitors/90031991/edit?link_source=monitor_notif)] · [[Related Logs](https://app.datadoghq.eu/logs?query=%28kube_deployment%3Aecho%29+AND+pod_name%3Aecho-77b7b5c4b-pmccz&from_ts=1759068838000&to_ts=1759069138000&live=false&link_source=monitor_notif)]\n%%%",
       "date": "1759069138000"
     }'
```

### 2. Datadog Webhook - Memory Alert

```bash
curl -X POST http://127.0.0.1:8000/datadog-webhook \
     -H "Content-Type: application/json" \
     -d '{
       "event_id": "8301471716550744339",
       "alert_id": "90031992",
       "event_type": "query_alert_monitor",
       "title": "[Triggered] High Memory usage detected on pod",
       "body": "%%%\n🚨 Memory usage exceeded threshold\n\n- Namespace: production\n\n- Deployment: web-app\n\n- Pod: web-app-5f7b8c9d-xyz123\n\n- Metric: kubernetes.memory.usage\n\n- Value: 85.5 (Threshold: 80.0)\n\n@webhook-kfix-webhook\n\n**kubernetes.memory.usage** over **kube_deployment:web-app** was **> 80.0** on average during the **last 5m**.\n%%%",
       "date": "1759069200000"
     }'
```

### 3. Datadog Webhook - Minimal Payload

```bash
curl -X POST http://127.0.0.1:8000/datadog-webhook \
     -H "Content-Type: application/json" \
     -d '{
       "alert_id": "90031991",
       "event_type": "query_alert_monitor",
       "title": "Test Alert",
       "body": "Simple test alert"
     }'
```

### 4. Health Check

```bash
curl -X GET http://127.0.0.1:8000/
```

---

## 📋 Response Examples

### Successful Response
```json
{
  "status": "success",
  "message": "Alert processed successfully",
  "enriched_alert": {
    "event_id": "8301471716550744338",
    "alert_id": "90031991",
    "monitor_info": {
      "id": 90031991,
      "name": "High CPU usage detected",
      "type": "query alert",
      "query": "avg(last_5m):avg:kubernetes.cpu.usage.total{kube_deployment:echo} > 4.0",
      "thresholds": {
        "critical": 4.0
      },
      "tags": ["env:production", "team:platform"]
    },
    "parsed_context": {
      "namespace": "default",
      "deployment": "echo",
      "pod": "echo-77b7b5c4b-pmccz",
      "metric": "",
      "value": 0.0,
      "threshold": 4.0
    }
  }
}
```

### Error Response - Missing alert_id
```json
{
  "detail": "alert_id not provided in payload"
}
```

### Error Response - Invalid alert_id
```json
{
  "detail": "alert_id is not a valid integer"
}
```

### Error Response - Monitor Not Found
```json
{
  "detail": "Monitor with ID 90031991 not found in Datadog"
}
```

---

## 🛠 Testing with Different Tools

### Using HTTPie
```bash
# Install HTTPie
pip install httpie

# Test the webhook
http POST localhost:8000/datadog-webhook \
  alert_id:=90031991 \
  event_type=query_alert_monitor \
  title="Test Alert" \
  body="Test alert body"
```

### Using Postman
1. **Method**: POST
2. **URL**: `http://localhost:8000/datadog-webhook`
3. **Headers**: 
   - `Content-Type: application/json`
4. **Body** (raw JSON):
```json
{
  "alert_id": "90031991",
  "event_type": "query_alert_monitor",
  "title": "Test Alert",
  "body": "Test alert body"
}
```

### Using Python requests
```python
import requests
import json

url = "http://localhost:8000/datadog-webhook"
payload = {
    "alert_id": "90031991",
    "event_type": "query_alert_monitor",
    "title": "Test Alert",
    "body": "Test alert body"
}

response = requests.post(url, json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

### Using JavaScript/Node.js
```javascript
const fetch = require('node-fetch');

const payload = {
  alert_id: "90031991",
  event_type: "query_alert_monitor",
  title: "Test Alert",
  body: "Test alert body"
};

fetch('http://localhost:8000/datadog-webhook', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(payload)
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

---

## 🔍 Debugging Tips

### Check Server Logs
```bash
# The server will output logs like:
# 🚨 Alerte reçue de Datadog : {'alert_id': '90031991', ...}
# 📡 Monitor details: Monitor(id=90031991, ...)
```

### Validate JSON Payload
```bash
# Use jq to validate JSON syntax
echo '{"alert_id": "90031991"}' | jq .
```

### Test with Different Environments
```bash
# Production
curl -X POST https://your-production-domain.com/datadog-webhook \
     -H "Content-Type: application/json" \
     -d '{"alert_id": "90031991"}'

# Staging
curl -X POST https://your-staging-domain.com/datadog-webhook \
     -H "Content-Type: application/json" \
     -d '{"alert_id": "90031991"}'
```

---

## 📝 Notes

- Replace `90031991` with actual monitor IDs from your Datadog account
- Ensure your `.env.dev` file contains valid Datadog API credentials
- The server must be running before testing these endpoints
- Check the FastAPI docs at `http://localhost:8000/docs` for interactive testing