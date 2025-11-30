# Claude Code Development Instructions

## Project: Restaurant Platform Sync Service

### Development Philosophy
1. **Test-Driven Development (TDD)**: Always write tests FIRST to explain what the system is doing
2. **Incremental Development**: Build very small, focused pieces at a time
3. **Observability First**: Bake in OpenTelemetry from the start - every function should have tracing
4. **Event-First Architecture**: EventBridge events as primary integration trigger
5. **Simple Error Handling**: Follow menu service patterns - return None/False for expected failures
6. **Consistent Patterns**: Match menu service approach for authentication, error handling, and testing

### Technology Stack & Architecture
- **Language**: Python 3.11+
- **Testing**: pytest as test harness with >80% coverage
- **Cloud**: AWS Serverless Architecture
  - **Events**: EventBridge for menu change notifications
  - **Compute**: Lambda functions for event processing
  - **API**: API Gateway for admin endpoints
  - **Storage**: DynamoDB (sync status, error queue)
  - **External**: REST APIs to delivery platforms (DoorDash, Uber Eats, Grubhub)
- **Monitoring**: OpenTelemetry + AWS X-Ray + CloudWatch
- **CI/CD**: GitHub Actions with trunk-based workflow

### Repository Convention
- **Name**: `restaurant-platform-sync-service`
- **Service ID**: `sync-svc` (for logging/tracing)
- **Package Name**: `restaurant_sync_service`
- **Branch Strategy**:
  - `main` - single source of truth, always deployable
  - `feature/{ticket-id}-{brief-description}` - short-lived only
  - No long-running branches (no develop, staging branches)

### Development Workflow
1. **Write Test First**: Explain the behavior you want
2. **Implement Minimum**: Just enough code to make test pass
3. **Add Observability**: Include OpenTelemetry spans and metrics
4. **Refactor**: Clean up while keeping tests green
5. **Commit Small**: Frequent commits with conventional commit messages

### Service Responsibilities
This sync service is responsible for:
- **Event Processing**: Consume menu change events from EventBridge
- **Menu Data Fetching**: Call menu service API to get current menu state
- **Platform Integration**: Transform and publish menu data to external delivery platforms
- **Sync Status Tracking**: Record successful/failed sync operations in DynamoDB
- **Error Queue Management**: Handle sync failures with retry logic and manual intervention
- **Admin API**: REST endpoints for dashboard integration and manual operations

### Integration Architecture
```
Menu Service Events → EventBridge → Sync Service → Platform APIs
                                          ↓
                                    DynamoDB (sync status)
                                          ↓
                                    Admin Dashboard
```

### Key Data Models (DynamoDB Design)
- **Sync Status Table**:
  - Partition Key: `restaurant_id`
  - Sort Key: `platform`
  - Attributes: last_sync_time, status, item_count, external_menu_id
- **Sync Errors Table**:
  - Partition Key: `error_id`
  - Sort Key: `created_at`
  - Attributes: restaurant_id, platform, error_details, menu_snapshot, retry_count
- **Sync Operations Table** (for tracking in-progress operations):
  - Partition Key: `operation_id`
  - Attributes: restaurant_id, platform, status, items_processed, total_items

### Platform Adapter Pattern
Follow the Abstract Base Class pattern for consistent platform integration:

```python
class PlatformAdapter(ABC):
    @abstractmethod
    def format_menu(self, items: list[MenuItem], categories: list[Category]) -> dict | None:
        """Transform menu data to platform-specific format. Return None on failure."""
        pass
    
    @abstractmethod
    async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
        """Publish menu to platform API. Return False on failure."""
        pass
```

### Error Handling Strategy (Consistent with Menu Service)
- **Simple Return Values**: Use None/False for expected failures (like menu service)
- **No Custom Exception Hierarchy**: Keep exceptions simple
- **Dependency Injection**: Inject platform credentials like APIKeyValidator pattern
- **Orchestration Layer Decides**: Let service layer handle retry logic

```python
# Adapter layer - simple return values
async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
    try:
        response = await self.api_client.post(...)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Platform API failed: {e}")
        return False

# Service layer - handle retry logic
if not await adapter.publish_menu(restaurant_id, menu_data):
    # Retry once
    await asyncio.sleep(2)
    if not await adapter.publish_menu(restaurant_id, menu_data):
        # Send to error queue
        await error_service.queue_failed_sync(...)
```

### Event Processing Flow
1. **EventBridge Event** → `event_handler.py`
2. **Fetch Menu Data** → Menu Service API call
3. **Platform Sync** → Format + Publish to each configured platform
4. **Status Update** → Record results in DynamoDB
5. **Error Handling** → Failed syncs to error queue

### Admin API Endpoints to Build
```
GET    /health                                    # Health check
GET    /admin/sync-status/{restaurant_id}         # Current sync status
POST   /admin/sync/{restaurant_id}/full-refresh   # Manual full menu sync
POST   /admin/sync/{restaurant_id}/platform/{platform} # Sync to specific platform
GET    /admin/errors                              # List sync errors
GET    /admin/errors/{restaurant_id}              # Errors for restaurant
POST   /admin/errors/{error_id}/retry             # Manual retry
POST   /admin/errors/{error_id}/resolve           # Mark as resolved
```

### Menu Service Integration
- **Model Consistency**: Import MenuItem and Category directly from menu service
- **API Calls**: Use same APIKeyValidator pattern for service-to-service auth
- **Event Schema**: Match menu service EventBridge event format exactly

```python
# Import models for consistency
from restaurant_sync_service.models.menu_item_model import MenuItem
from restaurant_sync_service.models.category_model import Category

# Service-to-service API calls
class MenuServiceClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
    
    async def get_menu_items(self, restaurant_id: str) -> list[MenuItem]:
        # Call menu service API
```

### Platform Configurations
Store platform-specific configs in environment/secrets:

```python
# Platform adapter factory pattern
class PlatformAdapterFactory:
    def __init__(self, platform_configs: dict):
        self.configs = platform_configs
    
    def create_adapter(self, platform: str) -> PlatformAdapter:
        config = self.configs[platform]
        if platform == "doordash":
            return DoorDashAdapter(
                client_id=config["client_id"],
                client_secret=config["client_secret"],
                environment=config["environment"]
            )
        # Add more platforms...
```

### Quality Standards & Gates (Same as Menu Service)
- **Test Coverage**: Minimum 80% coverage with pytest
- **Code Quality**: Black formatting, Ruff linting, MyPy type checking
- **Security**: Dependency vulnerability scanning
- **Performance**: OpenTelemetry metrics for sync times and success rates
- **Branch Protection**: Require PR approval + all checks passing

### Observability Requirements
- **Service Identification**: All logs/traces tagged with `service=sync-svc`
- **Custom Metrics**:
  - Menu sync success rate by platform
  - Menu sync duration by platform
  - Error queue depth
  - Platform API response times
- **Tracing**: Every EventBridge event, platform API call, and DynamoDB operation traced
- **Alerting**: CloudWatch alarms for sync failure rates, error queue buildup

### Testing Strategy (Match Menu Service Patterns)
```
tests/
├── unit/                    # Pure logic, no dependencies
│   ├── test_base_adapter.py      # Platform adapter interface
│   ├── test_sync_models.py       # Pydantic model validation
│   └── test_menu_formatting.py   # Menu transformation logic
├── component/               # Components with mocked dependencies
│   ├── test_doordash_adapter.py  # Platform adapter with mocked API
│   ├── test_sync_service.py      # Orchestration with mocked adapters
│   ├── test_event_handler.py     # EventBridge processing
│   └── test_admin_api.py         # REST API endpoints
├── integration/             # Real AWS services
│   ├── test_dynamodb_sync.py     # Real DynamoDB operations
│   └── test_eventbridge_flow.py  # Real EventBridge integration
└── e2e/                     # Full workflows
    └── test_menu_sync_flow.py    # End-to-end sync process
```

### Development Priorities (Build Order)
1. **Platform Adapter Base Class**: Abstract interface and DoorDash implementation
2. **Sync Models**: Pydantic models for sync status and error tracking
3. **DynamoDB Repositories**: Data access layer for sync status and error queue
4. **Event Handler**: EventBridge event processing with menu service calls
5. **Sync Service**: Orchestration logic with retry and error handling
6. **Admin API**: REST endpoints for manual operations
7. **Infrastructure**: CDK for Lambda, EventBridge, DynamoDB

### Implementation Patterns (Consistent with Menu Service)

#### OpenTelemetry Tracing Pattern
```python
from src.observability.tracing import traced

@traced("sync_restaurant_menu", service_name="sync-svc")
async def sync_restaurant_menu(restaurant_id: str, platform: str):
    # Automatically extracts restaurant_id for tracing
    return result
```

#### API Security Pattern (Same as Menu Service)
```python
from src.security.api_key_validator import APIKeyValidator

async def verify_api_key(x_api_key: str | None = Header()) -> None:
    if not api_key_validator.is_valid(x_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")

@app.get("/admin/sync-status/{restaurant_id}", dependencies=[Depends(verify_api_key)])
async def get_sync_status(restaurant_id: str):
    # Business logic
```

#### Repository Pattern (Same as Menu Service)
```python
class SyncStatusRepository:
    @traced("update_sync_status")
    def update_status(self, restaurant_id: str, platform: str, status: SyncStatus) -> SyncStatus:
        # DynamoDB operations with OpenTelemetry tracing
        return status
```

### File Structure
```
src/
├── models/                  # Data models and imported menu models
│   ├── __init__.py
│   ├── sync_models.py      # SyncStatus, SyncOperation, SyncError
│   └── menu_models.py      # Re-export from menu service
├── adapters/               # Platform-specific integrations
│   ├── __init__.py
│   ├── base_adapter.py     # Abstract base class
│   ├── doordash_adapter.py # DoorDash implementation
│   ├── ubereats_adapter.py # Uber Eats implementation
│   └── adapter_factory.py  # Factory for creating adapters
├── services/               # Business logic
│   ├── __init__.py
│   ├── sync_service.py     # Main sync orchestration
│   ├── menu_service_client.py # Menu service API calls
│   └── error_service.py    # Error queue management
├── repositories/           # DynamoDB data access
│   ├── __init__.py
│   ├── sync_repository.py  # Sync status operations
│   └── error_repository.py # Error queue operations
├── handlers/               # Event and API handlers
│   ├── __init__.py
│   ├── event_handler.py    # EventBridge event processing
│   └── api_handler.py      # Admin API endpoints
├── security/               # Authentication (import from menu service)
│   ├── __init__.py
│   └── api_key_validator.py # Same pattern as menu service
└── observability/          # OpenTelemetry utilities
    ├── __init__.py
    └── tracing.py          # Same @traced decorator pattern
```

### Getting Started Checklist
- [ ] Set up Python project structure with pyproject.toml
- [ ] Configure pytest with coverage and testing markers (copy from menu service)
- [ ] Set up pre-commit hooks for code quality
- [ ] Create platform adapter base class with tests (TDD)
- [ ] Implement DoorDash adapter with mocked API tests
- [ ] Add sync status DynamoDB repository with moto mocking
- [ ] Create EventBridge event handler with menu service integration
- [ ] Add OpenTelemetry instrumentation from first function
- [ ] Create GitHub Actions CI pipeline (copy from menu service)

**Remember**: Start with the smallest possible piece (platform adapter interface) and build incrementally. Write tests first to explain what you're building, then implement just enough to make them pass. Keep patterns consistent with the menu service.

### Key Integration Points
- **Menu Service**: Import models directly, call REST API for menu data
- **EventBridge**: Listen for menu change events, publish sync status events
- **Platform APIs**: DoorDash Drive, Uber Eats Manager, Grubhub Partner APIs
- **DynamoDB**: Store sync status and error queue data
- **Admin Dashboard**: Provide REST API for manual operations and error resolution
