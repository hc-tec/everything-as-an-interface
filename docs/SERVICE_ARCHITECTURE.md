# Service-Based Architecture Guide

## Overview

The project now supports a service-based architecture that separates site-specific capabilities from plugin logic. This approach provides better code reusability, maintainability, and modularity.

## Architecture Layers

### 1. Plugin Layer (Orchestration)
- **Purpose**: Configuration, coordination, and output formatting
- **Responsibilities**: 
  - Parse user configuration
  - Coordinate calls to multiple services
  - Format and return results
  - Handle error aggregation
- **Examples**: `XiaohongshuV2Plugin`, future `WeiboPlugin`, etc.

### 2. Site Services Layer (Site-Specific Logic)
- **Purpose**: Implement site-specific data collection and interaction
- **Responsibilities**:
  - Bind to network rules and DOM events
  - Parse site-specific data formats
  - Handle site-specific navigation and interaction
  - Manage caching and optimization
- **Examples**: `XiaohongshuFeedService`, `XiaohongshuDetailService`, etc.

### 3. Utility Layer (Shared Components)
- **Purpose**: Provide reusable collection patterns and tools
- **Responsibilities**:
  - Generic collection loops (network-driven, DOM-driven)
  - Network rule management and event dispatching
  - Common data structures and configurations
- **Examples**: `FeedCollectionConfig`, `NetRuleBus`, `DomCollection`

## Available Services

### Xiaohongshu Services

#### 1. Feed Service (`XiaohongshuFeedService`)
- **Purpose**: Collect lists of items (favorites, feeds, etc.)
- **Features**:
  - Network-driven collection with configurable stop conditions
  - Custom stop deciders for content-based filtering
  - Automatic scrolling and pagination
  - Deduplication by item ID

```python
# Initialize and configure
note_service = XiaohongshuNoteService()
await note_service.attach(page)

config = NoteCollectionConfig(
    max_items=100,
    max_seconds=60,
    auto_scroll=True
)
note_service.configure(config)

# Collect items
items = await note_service.collect(NoteCollectArgs(
    goto_first=lambda: page.goto("https://www.xiaohongshu.com/favorites"),
    extra_config={"custom_param": "value"}
))
```

#### 2. Detail Service (`XiaohongshuDetailService`)
- **Purpose**: Fetch detailed information about specific notes
- **Features**:
  - Single and batch detail fetching
  - Automatic caching to avoid duplicate requests
  - Configurable timeouts and retry logic

```python
# Get single detail
detail_service = XiaohongshuDetailService()
await detail_service.attach(page)

detail = await detail_service.get_detail(DetailArgs(
    item_id="note_123",
    extra_config={"timeout": 15.0}
))

# Get multiple details
details = await detail_service.get_details_batch(
    ["note_1", "note_2", "note_3"],
    extra_config={"delay_ms": 1000}
)
```

#### 3. Comment Service (`XiaohongshuCommentService`)
- **Purpose**: Collect comments for specific notes
- **Features**:
  - Paginated comment collection
  - Configurable page limits and delays
  - Network-driven collection

```python
comment_service = XiaohongshuCommentService()
await comment_service.attach(page)

comments = await comment_service.collect_for_note(
    "note_123",
    max_pages=5,
    delay_ms=500
)
```

#### 4. Search Service (`XiaohongshuSearchService`)
- **Purpose**: Search for content using keywords
- **Features**:
  - Keyword-based search
  - Multiple result batches
  - Configurable delays between requests

```python
search_service = XiaohongshuSearchService()
await search_service.attach(page)

results = await search_service.search(
    "旅行攻略",
    max_batches=3,
    delay_ms=800
)
```

#### 5. Publish Service (`XiaohongshuPublishService`)
- **Purpose**: Publish content to the platform
- **Features**:
  - Content publishing with media upload
  - Draft saving
  - Configurable publish settings
  - Status checking

```python
publish_service = XiaohongshuPublishService()
await publish_service.attach(page)

content = PublishContent(
    title="My Post",
    content="Post content here",
    images=["path/to/image1.jpg", "path/to/image2.jpg"],
    tags=["tag1", "tag2"],
    visibility="public"
)

result = await publish_service.publish(content)
if result.success:
    print(f"Published successfully: {result.url}")
```

## Using the Service-Based Plugin

The new `XiaohongshuV2Plugin` demonstrates how to create a thin orchestration layer:

```python
# Configure the plugin
config = TaskConfig(
    extra={
        "task_type": "favorites",  # or "search", "details", "comments"
        "max_items": 50,
        "max_seconds": 120,
        "stop_on_tags": ["旅行", "美食"],  # Stop when finding these tags
        "stop_on_author": "specific_user",  # Stop when finding this author
    }
)

# Use the plugin
plugin = XiaohongshuV2Plugin()
plugin.configure(config)
await plugin.setup()

# Collect data
result = await plugin.fetch()
print(f"Collected {result['count']} items")

# Cleanup
await plugin.cleanup()
```

## Benefits of Service Architecture

### 1. **Code Reusability**
- Services can be used by multiple plugins
- Common patterns are extracted to utility modules
- Reduces duplication across different site integrations

### 2. **Better Testing**
- Services can be tested independently
- Mock services can be created for plugin testing
- Clear separation of concerns

### 3. **Easier Maintenance**
- Site-specific changes only affect corresponding services
- Plugin logic is simplified and more stable
- Easier to add new sites and capabilities

### 4. **Flexible Configuration**
- Services expose clean configuration interfaces
- Plugins can combine services in different ways
- Users can configure collection behavior precisely

## Adding New Services

To add a new service capability:

1. **Define the service interface** in `src/sites/base.py`:
```python
class NewCapabilityService(BaseSiteService):
    @abstractmethod
    async def do_something(self, args: SomeArgs) -> SomeResult:
        ...
```

2. **Implement for specific sites** in `src/sites/sitename/`:
```python
class SiteNewCapabilityService(NewCapabilityService):
    async def do_something(self, args: SomeArgs) -> SomeResult:
        # Site-specific implementation
        pass
```

3. **Use in plugins**:
```python
self._new_service = SiteNewCapabilityService()
await self._new_service.attach(self.page)
result = await self._new_service.do_something(args)
```

## Migration Guide

### From Legacy Plugin to Service-Based

1. **Identify distinct capabilities** in your plugin (feed, detail, search, etc.)
2. **Extract each capability** to a separate service class
3. **Move site-specific logic** to services
4. **Keep orchestration logic** in the plugin
5. **Update configuration** to use service-specific configs

### Example Migration

**Before (monolithic plugin)**:
```python
class MyPlugin(BasePlugin):
    async def fetch(self):
        # 200 lines of mixed orchestration and site logic
        await self._navigate_to_page()
        items = await self._scrape_items()
        details = await self._get_details_for_items(items)
        return self._format_results(details)
```

**After (service-based)**:
```python
class MyPlugin(BasePlugin):
    async def fetch(self):
        # Clean orchestration
        items = await self._note_service.collect(args)
        details = await self._detail_service.get_details_batch([item.id for item in items])
        return self._format_results(details)
```

## Best Practices

1. **Keep plugins thin** - delegate to services
2. **Use dependency injection** - pass services to plugins
3. **Configure services explicitly** - don't hide configuration
4. **Handle errors gracefully** - services may fail independently
5. **Cache when appropriate** - but be mindful of memory usage
6. **Log at service boundaries** - for debugging and monitoring

## Future Enhancements

- **Service registry** for automatic discovery
- **Service health checks** and monitoring
- **Service composition patterns** for complex workflows
- **Configuration validation** at service level
- **Retry and circuit breaker patterns** for resilience
