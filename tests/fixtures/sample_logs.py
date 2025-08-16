"""Sample log data fixtures for testing."""

from datetime import datetime, timedelta
from typing import Dict, List, Any
import json


def generate_timestamp(base_time: datetime, offset_seconds: int = 0) -> str:
    """Generate a Loki-compatible timestamp."""
    timestamp = base_time + timedelta(seconds=offset_seconds)
    # Loki uses nanosecond precision Unix timestamps
    return str(int(timestamp.timestamp() * 1_000_000_000))


def generate_rfc3339_timestamp(base_time: datetime, offset_seconds: int = 0) -> str:
    """Generate an RFC3339 timestamp."""
    timestamp = base_time + timedelta(seconds=offset_seconds)
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


# Base time for consistent test data
BASE_TIME = datetime(2024, 1, 1, 12, 0, 0)

# Time range constants for testing
TIME_RANGES = {
    "last_hour": {
        "start": generate_rfc3339_timestamp(BASE_TIME, -3600),
        "end": generate_rfc3339_timestamp(BASE_TIME, 0)
    },
    "last_day": {
        "start": generate_rfc3339_timestamp(BASE_TIME, -86400),
        "end": generate_rfc3339_timestamp(BASE_TIME, 0)
    },
    "custom_range": {
        "start": generate_rfc3339_timestamp(BASE_TIME, -1800),
        "end": generate_rfc3339_timestamp(BASE_TIME, -900)
    }
}

# Sample log entries with various levels and services
SAMPLE_LOG_ENTRIES = [
    {
        "timestamp": generate_timestamp(BASE_TIME, 0),
        "line": "Starting application server on port 8080",
        "labels": {"job": "web-server", "level": "info", "instance": "server-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 10),
        "line": "Database connection established successfully",
        "labels": {"job": "web-server", "level": "info", "instance": "server-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 20),
        "line": "User authentication failed for user: admin",
        "labels": {"job": "web-server", "level": "warn", "instance": "server-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 30),
        "line": "Failed to connect to external API: timeout after 30s",
        "labels": {"job": "web-server", "level": "error", "instance": "server-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 40),
        "line": "Processing user request: GET /api/users",
        "labels": {"job": "web-server", "level": "debug", "instance": "server-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 50),
        "line": "Background job started: data-sync",
        "labels": {"job": "background-worker", "level": "info", "instance": "worker-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 60),
        "line": "Syncing 1000 records from external source",
        "labels": {"job": "background-worker", "level": "info", "instance": "worker-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 70),
        "line": "Memory usage high: 85% of available memory",
        "labels": {"job": "background-worker", "level": "warn", "instance": "worker-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 80),
        "line": "Critical error: Out of memory exception",
        "labels": {"job": "background-worker", "level": "error", "instance": "worker-1"}
    },
    {
        "timestamp": generate_timestamp(BASE_TIME, 90),
        "line": "Application shutting down gracefully",
        "labels": {"job": "background-worker", "level": "info", "instance": "worker-1"}
    }
]

# Sample Loki API responses
SAMPLE_QUERY_RANGE_RESPONSE = {
    "status": "success",
    "data": {
        "resultType": "streams",
        "result": [
            {
                "stream": {"job": "web-server", "level": "info", "instance": "server-1"},
                "values": [
                    [SAMPLE_LOG_ENTRIES[0]["timestamp"], SAMPLE_LOG_ENTRIES[0]["line"]],
                    [SAMPLE_LOG_ENTRIES[1]["timestamp"], SAMPLE_LOG_ENTRIES[1]["line"]]
                ]
            },
            {
                "stream": {"job": "web-server", "level": "warn", "instance": "server-1"},
                "values": [
                    [SAMPLE_LOG_ENTRIES[2]["timestamp"], SAMPLE_LOG_ENTRIES[2]["line"]]
                ]
            }
        ]
    }
}

SAMPLE_QUERY_INSTANT_RESPONSE = {
    "status": "success",
    "data": {
        "resultType": "streams",
        "result": [
            {
                "stream": {"job": "web-server", "level": "error", "instance": "server-1"},
                "values": [
                    [SAMPLE_LOG_ENTRIES[3]["timestamp"], SAMPLE_LOG_ENTRIES[3]["line"]]
                ]
            }
        ]
    }
}

SAMPLE_LABELS_RESPONSE = {
    "status": "success",
    "data": ["job", "level", "instance", "__name__"]
}

SAMPLE_LABEL_VALUES_RESPONSE = {
    "status": "success",
    "data": ["info", "warn", "error", "debug"]
}

SAMPLE_SERIES_RESPONSE = {
    "status": "success",
    "data": [
        {"job": "web-server", "level": "info", "instance": "server-1"},
        {"job": "web-server", "level": "warn", "instance": "server-1"},
        {"job": "web-server", "level": "error", "instance": "server-1"},
        {"job": "background-worker", "level": "info", "instance": "worker-1"},
        {"job": "background-worker", "level": "warn", "instance": "worker-1"},
        {"job": "background-worker", "level": "error", "instance": "worker-1"}
    ]
}

# Error response samples
SAMPLE_ERROR_RESPONSES = {
    "invalid_query": {
        "status": "error",
        "error": "parse error at line 1, col 1: syntax error: unexpected character inside braces: '!'",
        "errorType": "bad_data"
    },
    "authentication_error": {
        "status": "error",
        "error": "unauthorized",
        "errorType": "unauthorized"
    },
    "rate_limit_error": {
        "status": "error",
        "error": "rate limit exceeded",
        "errorType": "rate_limited"
    }
}

# Large dataset for performance testing
def generate_large_log_dataset(num_entries: int = 1000) -> Dict[str, Any]:
    """Generate a large dataset for performance testing."""
    entries = []
    services = ["web-server", "api-gateway", "database", "cache", "worker"]
    levels = ["debug", "info", "warn", "error"]
    instances = [f"server-{i}" for i in range(1, 6)]
    
    for i in range(num_entries):
        service = services[i % len(services)]
        level = levels[i % len(levels)]
        instance = instances[i % len(instances)]
        
        entry = {
            "timestamp": generate_timestamp(BASE_TIME, i * 10),
            "line": f"Log message {i}: Processing request in {service}",
            "labels": {"job": service, "level": level, "instance": instance}
        }
        entries.append(entry)
    
    # Group by stream (unique label combinations)
    streams = {}
    for entry in entries:
        stream_key = json.dumps(entry["labels"], sort_keys=True)
        if stream_key not in streams:
            streams[stream_key] = {
                "stream": entry["labels"],
                "values": []
            }
        streams[stream_key]["values"].append([entry["timestamp"], entry["line"]])
    
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": list(streams.values())
        }
    }

# Common LogQL queries for testing
SAMPLE_QUERIES = {
    "basic_query": '{job="web-server"}',
    "level_filter": '{job="web-server"} |= "error"',
    "regex_filter": '{job="web-server"} |~ "user.*failed"',
    "json_filter": '{job="api-gateway"} | json | status_code="500"',
    "rate_query": 'rate({job="web-server"}[5m])',
    "count_query": 'count_over_time({job="web-server"}[1h])',
    "invalid_query": '{job="web-server"!}',  # Invalid syntax
    "empty_result_query": '{job="nonexistent-service"}'
}

# MCP tool call examples
SAMPLE_MCP_CALLS = {
    "query_logs": {
        "name": "query_logs",
        "arguments": {
            "query": '{job="web-server"}',
            "start": TIME_RANGES["last_hour"]["start"],
            "end": TIME_RANGES["last_hour"]["end"],
            "limit": 100
        }
    },
    "search_logs": {
        "name": "search_logs",
        "arguments": {
            "keywords": ["error", "failed"],
            "start": TIME_RANGES["last_hour"]["start"],
            "end": TIME_RANGES["last_hour"]["end"],
            "limit": 50
        }
    },
    "get_labels": {
        "name": "get_labels",
        "arguments": {}
    },
    "get_label_values": {
        "name": "get_labels",
        "arguments": {
            "label_name": "level"
        }
    }
}