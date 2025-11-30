# Architectural Decision Records

This document captures key architectural and design decisions made during the development of the restaurant platform sync service.

## Format

Each decision includes:
- **Date**: When the decision was made
- **Status**: Accepted, Deprecated, Superseded
- **Context**: What problem we're solving
- **Decision**: What we decided to do
- **Consequences**: Trade-offs and implications

---

## ADR-001: Event-first integration architecture

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need to choose primary integration pattern between menu service and sync service. Options included: direct API polling, webhooks, or event-driven architecture via EventBridge.

**Decision**: Use EventBridge events as the primary trigger for menu synchronization, with direct API calls for data fetching.

**Consequences**:
- **Pros**:
  - Real-time responsiveness to menu changes
  - Decoupled services - menu service doesn't need to know about sync service
  - Built-in retry and dead letter queue capabilities
  - Scales automatically with event volume
  - Consistent with AWS serverless patterns
- **Cons**:
  - Additional complexity for local development
  - Event ordering considerations for rapid menu changes
  - Eventual consistency model

**Implementation Pattern**:
```
Menu Change → EventBridge Event → Sync Service → Platform APIs
```

---

## ADR-002: Abstract base class for platform adapters

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need consistent interface for integrating with multiple delivery platforms (DoorDash, Uber Eats, Grubhub). Each platform has different API formats, authentication methods, and data requirements.

**Decision**: Use Abstract Base Class pattern with consistent interface for all platform integrations.

**Consequences**:
- **Pros**:
  - Consistent interface reduces complexity in orchestration layer
  - Easy to add new platforms by implementing interface
  - Testable with mocked adapters
  - Clear separation of platform-specific logic
- **Cons**:
  - May not fit all platform paradigms perfectly
  - Abstracts away platform-specific optimizations

**Implementation Pattern**:
```python
class PlatformAdapter(ABC):
    @abstractmethod
    def format_menu(self, items: list[MenuItem], categories: list[Category]) -> dict | None

    @abstractmethod
    async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool
```

---

## ADR-003: Full menu replacement sync strategy

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need to choose between incremental menu updates vs full menu replacement when syncing to platforms. Incremental updates are more efficient but complex to implement correctly.

**Decision**: Use full menu replacement for all platform synchronizations.

**Consequences**:
- **Pros**:
  - Simpler to implement and reason about
  - Ensures consistency - no drift between internal and external menus
  - Easier error recovery - always know exact state after sync
  - Most platform APIs support full replacement
- **Cons**:
  - Less efficient for large menus with small changes
  - Higher API usage and potential rate limiting
  - Larger data transfer volumes
- **Future**: Can optimize to incremental updates per platform as needed

**Rationale**: Prioritize correctness and simplicity over optimization in initial implementation.

---

## ADR-004: Simple retry strategy with error queue

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need error handling strategy for platform API failures. Options included: multiple retries with exponential backoff, circuit breaker pattern, or simple retry with manual intervention.

**Decision**: One automatic retry followed by error queue for manual resolution via dashboard.

**Consequences**:
- **Pros**:
  - Simple to implement and understand
  - Provides escape hatch for persistent failures
  - Manual intervention allows for business logic decisions
  - Clear operational visibility into sync issues
- **Cons**:
  - Requires manual intervention for some failures
  - May not handle transient issues optimally
  - Dashboard dependency for full error resolution

**Implementation Pattern**:
```
Platform API Call → Failure → Retry Once → Failure → Error Queue → Dashboard
```

---

## ADR-005: Direct model import from menu service

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need to handle MenuItem and Category models used by both services. Options included: shared package, model duplication, or direct import from menu service.

**Decision**: Import MenuItem and Category models directly from menu service package.

**Consequences**:
- **Pros**:
  - Single source of truth for data models
  - DRY principle - no model duplication
  - Automatic consistency when menu service models change
  - Simple dependency management
- **Cons**:
  - Creates coupling between services
  - Sync service depends on menu service package
  - Requires menu service to be importable (shared deployment or package)
- **Alternative**: If coupling becomes problematic, can extract models to shared package

**Implementation Pattern**:
```python
from menu_service.models.menu_item_model import MenuItem
from menu_service.models.category_model import Category
```

---

## ADR-006: Consistent error handling patterns with menu service

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need error handling approach for platform adapters and service layers. Menu service uses simple return values (None/False) for expected failures rather than custom exceptions.

**Decision**: Follow same simple error handling pattern as menu service - use return values over exceptions.

**Consequences**:
- **Pros**:
  - Consistent patterns across services
  - Simple to understand and implement
  - No custom exception hierarchy complexity
  - Clear expected vs unexpected failure distinction
- **Cons**:
  - May lose some error context compared to exceptions
  - Requires discipline to check return values

**Implementation Pattern**:
```python
# Adapter returns False for expected failures
async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
    try:
        # Platform API call
        return success
    except Exception as e:
        logger.error(f"Platform API failed: {e}")
        return False  # Let service layer handle

# Service layer checks return value and decides action
if not await adapter.publish_menu(restaurant_id, menu_data):
    # Retry logic or error queue
```

---

## ADR-007: Dependency injection for platform credentials

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need to handle platform-specific credentials and configuration. Menu service uses dependency injection pattern for APIKeyValidator.

**Decision**: Use same dependency injection pattern for platform credentials and configuration.

**Consequences**:
- **Pros**:
  - Consistent with menu service authentication patterns
  - Easy to test with mocked configurations
  - Clean separation of concerns
  - Supports multiple environments (dev/staging/prod)
- **Cons**:
  - Slightly more complex setup compared to global configuration
  - Requires factory pattern for adapter creation

**Implementation Pattern**:
```python
class PlatformAdapterFactory:
    def __init__(self, platform_configs: dict):
        self.configs = platform_configs

    def create_adapter(self, platform: str) -> PlatformAdapter:
        config = self.configs[platform]
        return DoorDashAdapter(
            client_id=config["client_id"],
            client_secret=config["client_secret"]
        )
```

---

## ADR-008: DynamoDB tables for sync status and error queue

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need to store sync status and error information. Options included: single table design vs separate tables for different data types.

**Decision**: Use separate DynamoDB tables for sync status and error queue with dedicated access patterns.

**Consequences**:
- **Pros**:
  - Clear data model boundaries
  - Optimized access patterns for each use case
  - Easier to reason about and query
  - Simple table design and indexes
- **Cons**:
  - Multiple tables to manage
  - Potential for cross-table consistency issues
  - More infrastructure complexity

**Table Design**:
```
sync_status table:
  PK: restaurant_id
  SK: platform
  Attributes: last_sync_time, status, item_count

sync_errors table:
  PK: error_id
  SK: created_at
  GSI: restaurant_id, platform for filtering
```

---

## ADR-009: Admin API for dashboard integration

**Date**: 2025-01-15
**Status**: Accepted

**Context**: Need way for operations dashboard to view sync status and trigger manual operations. Building the dashboard UI is out of scope, but need API interface.

**Decision**: Provide REST API endpoints for all dashboard operations using same authentication pattern as menu service.

**Consequences**:
- **Pros**:
  - Clean separation between aggregation logic and UI concerns
  - RESTful interface familiar to dashboard developers
  - Reuses existing authentication patterns
  - Can be used by multiple dashboard implementations
- **Cons**:
  - Additional API surface area to maintain
  - Requires coordination with dashboard team on interface

**API Design**:
```
GET /admin/sync-status/{restaurant_id}
POST /admin/sync/{restaurant_id}/full-refresh
GET /admin/errors
POST /admin/errors/{error_id}/retry
```

---

## Future Decisions to Document

As development continues, document decisions about:
- Platform-specific optimizations and rate limiting
- Menu data caching strategies
- Cross-platform sync coordination (if restaurants are on multiple platforms)
- Webhook handling for platform status updates
- Event schema evolution strategies
- Monitoring and alerting thresholds
- Disaster recovery and data consistency approaches
