# Restaurant Platform - Sync Service

## Overview
Microservice responsible for synchronizing restaurant menu data to external delivery platforms. This service consumes menu changes from the menu service and publishes formatted data to DoorDash, Uber Eats, Grubhub, and other third-party APIs.

## Purpose
- Transform internal menu format to platform-specific formats
- Publish menu data to external delivery platforms
- Track synchronization status across platforms
- Handle sync failures with retry logic and error queuing
- Provide admin APIs for manual sync operations and error resolution

## Tech Stack
- **Python 3.11+** - Core language
- **FastAPI** - REST API framework for admin endpoints
- **DynamoDB** - Sync status and error queue storage
- **EventBridge** - Event-driven menu change processing
- **AWS Lambda** - Serverless compute
- **OpenTelemetry** - Observability and tracing
- **pytest** - Testing framework

## Quick Start

### Prerequisites
- Python 3.11 or higher
- Git
- Access to menu service (for model imports)

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd restaurant-platform-sync-service

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your actual configuration values

# Install pre-commit hooks
pre-commit install

# Verify setup (optional)
./scripts/verify_setup.sh
```

### Running Locally

```bash
# Install uvicorn if not already installed
pip install uvicorn

# Option 1: Run with uvicorn directly (recommended for development)
uvicorn src.main:app --reload --port 8001

# Option 2: Run with Python
python -m src.main

# The API will be available at:
# - API Documentation: http://localhost:8001/docs
# - Health Check: http://localhost:8001/health
# - Admin APIs: http://localhost:8001/admin/*
```

#### Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key environment variables:
- `API_KEYS` - Comma-separated list of valid API keys for admin endpoints
- `MENU_SERVICE_URL` - URL of the menu service API
- `MENU_SERVICE_API_KEY` - API key for calling menu service
- `PLATFORM_CONFIGS` - JSON configuration for delivery platform APIs
- `DYNAMODB_ENDPOINT` - For local DynamoDB (leave unset for AWS)
- `AWS_REGION` - AWS region (default: `us-east-1`)

**Platform Configuration Example:**
```bash
PLATFORM_CONFIGS='{
  "doordash": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "environment": "sandbox",
    "base_url": "https://api.doordash.com"
  },
  "ubereats": {
    "client_id": "your_client_id",
    "private_key": "your_private_key",
    "environment": "sandbox"
  }
}'
```

### Development Commands

```bash
# Run tests
pytest -v

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run specific test markers
pytest -m unit          # Unit tests only
pytest -m component     # Component tests only
pytest -m integration   # Integration tests only
pytest -m e2e           # E2E tests only

# Run linting and formatting
pre-commit run --all-files

# Format code
black .

# Lint code
ruff check . --fix

# Type checking
mypy src/
```

## Project Structure
```
src/
├── models/          # Sync status, error queue, and imported menu models
├── adapters/        # Platform-specific API adapters
├── services/        # Business logic for sync orchestration
├── repositories/    # DynamoDB data access layer
├── handlers/        # EventBridge and API request handlers
└── observability/   # OpenTelemetry instrumentation

tests/
├── unit/           # Pure logic, no dependencies
├── component/      # Components with mocked deps
├── integration/    # Real AWS services and platform APIs
└── e2e/            # Full sync workflows
```

## API Examples

### Authentication

Admin API endpoints require authentication via the `X-API-Key` header:

```bash
curl http://localhost:8001/admin/sync-status/rest_001 \
  -H "X-API-Key: admin-key-123"
```

### Get Sync Status for Restaurant

```bash
curl http://localhost:8001/admin/sync-status/rest_001 \
  -H "X-API-Key: admin-key-123"
```

Response:
```json
{
  "restaurant_id": "rest_001",
  "platforms": {
    "doordash": {
      "status": "SYNCED",
      "last_sync": "2025-01-15T10:30:00Z",
      "item_count": 25,
      "external_menu_id": "dd_menu_789"
    },
    "ubereats": {
      "status": "FAILED",
      "last_sync": "2025-01-15T09:45:00Z",
      "error": "API timeout",
      "retry_count": 2
    }
  }
}
```

### Manual Full Menu Sync

```bash
curl -X POST http://localhost:8001/admin/sync/rest_001/full-refresh \
  -H "X-API-Key: admin-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "platforms": ["doordash", "ubereats"],
    "force": true
  }'
```

### List Sync Errors

```bash
curl http://localhost:8001/admin/errors?restaurant_id=rest_001 \
  -H "X-API-Key: admin-key-123"
```

### Retry Failed Sync

```bash
curl -X POST http://localhost:8001/admin/errors/err_rest001_dd_20250115_001/retry \
  -H "X-API-Key: admin-key-123"
```

## Event Processing

### EventBridge Integration

The service listens for menu change events from the menu service:

```json
{
  "source": "menu-service",
  "detail-type": "Menu Item Changed",
  "detail": {
    "eventType": "CREATED",
    "restaurantId": "rest_001",
    "itemId": "item_456",
    "timestamp": "2025-01-15T10:30:00Z",
    "item": {
      "restaurant_id": "rest_001",
      "item_id": "item_456",
      "name": "Margherita Pizza",
      "price": "12.99"
    }
  }
}
```

### Sync Process Flow

1. **Event Received** - Menu change event triggers Lambda
2. **Menu Fetch** - Call menu service API to get current menu state
3. **Platform Sync** - Format and publish to each configured platform
4. **Status Update** - Record sync results in DynamoDB
5. **Error Handling** - Failed syncs go to error queue after 1 retry

## Platform Integration

### Supported Platforms

- **DoorDash** - Drive API integration
- **Uber Eats** - Eats Manager API integration
- **Grubhub** - Partner API integration (planned)

### Adding New Platforms

1. Create adapter class extending `PlatformAdapter`
2. Implement `format_menu()` and `publish_menu()` methods
3. Add platform configuration to environment
4. Register adapter in `PlatformAdapterFactory`

Example:
```python
class NewPlatformAdapter(PlatformAdapter):
    def format_menu(self, items: list[MenuItem], categories: list[Category]) -> dict | None:
        # Transform to platform format
        return formatted_menu

    async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
        # Call platform API
        return success
```

## Error Handling

### Retry Strategy
- **1 automatic retry** with exponential backoff
- **Failed retries** go to error queue for manual intervention
- **Dashboard integration** for error visibility and manual retry

### Error Queue
Failed sync operations are stored with full context:
- Original menu data snapshot
- Error details and platform response
- Retry history
- Manual resolution tracking

## Monitoring and Observability

### OpenTelemetry Tracing
All operations are traced with relevant attributes:
- `restaurant_id` - Restaurant being synced
- `platform` - Target delivery platform
- `operation` - Sync operation type
- `item_count` - Number of items processed

### Key Metrics
- Sync success rate by platform
- Menu sync latency
- Error queue depth
- Platform API response times

### Alerting
- High error rates by platform
- Sync failures exceeding threshold
- Platform API downtime detection

## Development Workflow
1. **Test-Driven Development** - Write tests first
2. **Event-First Integration** - EventBridge as primary trigger
3. **Platform Adapter Pattern** - Consistent interface for all platforms
4. **Simple Error Handling** - Return values over exceptions
5. **Dependency Injection** - Platform credentials and config

For detailed development instructions, see [claude_instructions.md](claude_instructions.md)
