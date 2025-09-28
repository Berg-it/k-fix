import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api import monitors_api
from datadog_api_client.exceptions import NotFoundException

# Charger .env.dev uniquement en local
if os.getenv("ENVIRONMENT", "local") == "local":
    print("⚙️  Loading .env.dev for local development")
    load_dotenv(dotenv_path=".env.dev")

app = FastAPI()


def get_datadog_config():
    return Configuration(
        api_key={
            "apiKeyAuth": os.getenv("DD_API_KEY"),
            "appKeyAuth": os.getenv("DD_APP_KEY"),
        },
        server_variables={
            "site": os.getenv("DD_SITE", "datadoghq.eu"),
        },
    )


@app.post("/datadog-webhook")
async def datadog_webhook(request: Request):
    payload = await request.json()
    #print("🚨 Alerte reçue de Datadog :", payload)

    alert_id = payload.get("alert_id")
    if not alert_id:
        raise HTTPException(status_code=400, detail="alert_id not provided in payload")

    try:
        monitor_id = int(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="alert_id is not a valid integer")

    config = get_datadog_config()
    with ApiClient(config) as api_client:
        api = monitors_api.MonitorsApi(api_client)
        try:
            monitor = api.get_monitor(monitor_id=monitor_id)
            monitor_dict = monitor.to_dict()

            # Monitor light
            monitor_light = {
                "id": monitor_dict.get("id"),
                "name": monitor_dict.get("name"),
                "type": monitor_dict.get("type"),
                "query": monitor_dict.get("query"),
                "thresholds": monitor_dict.get("options", {}).get("thresholds"),
                "tags": monitor_dict.get("tags"),
            }

            # Parsing body
            body = payload.get("body", "")

            namespace_match = re.search(r"^- Namespace:\s*(.*)$", body, re.MULTILINE)
            deployment_match = re.search(r"^- Deployment:\s*(.*)$", body, re.MULTILINE)
            pod_match = re.search(r"^- Pod:\s*(.*)$", body, re.MULTILINE)
            metric_match = re.search(r"^- Metric:\s*(.*)$", body, re.MULTILINE)
            value_match = re.search(r"^- Value:\s*([0-9.]+)", body, re.MULTILINE)
            threshold_match = re.search(r"Threshold:\s*([0-9.]+)", body)

            namespace = namespace_match.group(1).strip() if namespace_match else None
            if (namespace and namespace.startswith("- ") or not namespace):
                namespace = "default"

            deployment = deployment_match.group(1).strip() if deployment_match else None
            pod = pod_match.group(1).strip() if pod_match else None
            metric = metric_match.group(1).strip() if metric_match else None
            value = float(value_match.group(1)) if value_match else None
            threshold = float(threshold_match.group(1)) if threshold_match else None

            enriched_alert = {
                "event_id": payload.get("event_id"),
                "alert_id": alert_id,
                "event_type": payload.get("event_type"),
                "date": payload.get("date"),
                "title": payload.get("title"),
                "body": body,
                "namespace": namespace,
                "deployment": deployment,
                "pod": pod,
                "metric": metric,
                "value": value,
                "threshold": threshold,
                "monitor": monitor_light
            }

            return JSONResponse(content={"status": "ok", "alert": enriched_alert}, status_code=200)

        except NotFoundException:
            return JSONResponse(
                content={"status": "monitor_not_found", "monitor_id": monitor_id},
                status_code=404
            )