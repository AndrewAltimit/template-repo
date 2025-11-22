# Gaea2 MCP API Reference

Complete API reference for the Gaea2 Model Context Protocol system.

## Table of Contents

1. [MCP Tools API](#mcp-tools-api)
2. [Core Modules](#core-modules)
3. [Validation Modules](#validation-modules)
4. [Intelligence Modules](#intelligence-modules)
5. [Infrastructure Modules](#infrastructure-modules)
6. [Data Structures](#data-structures)
7. [Error Types](#error-types)

---

## MCP Tools API

The main interface for interacting with Gaea2 functionality through MCP.

### create_gaea2_project

Create a custom Gaea2 terrain project with **automatic validation and error correction**.

```python
async def create_gaea2_project(
    project_name: str,
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    output_path: Optional[str] = None,
    groups: Optional[List[Dict[str, Any]]] = None,
    modifiers: Optional[List[Dict[str, Any]]] = None,
    automation_variables: Optional[List[Dict[str, Any]]] = None,
    viewport_config: Optional[Dict[str, Any]] = None,
    build_config: Optional[Dict[str, Any]] = None,
    auto_validate: bool = True  # NEW: Automatic validation (default: True)
) -> Dict[str, Any]
```

**Parameters:**
- `project_name`: Name of the project
- `nodes`: List of node definitions
- `connections`: List of connection definitions
- `output_path`: Output file path (defaults to `{project_name}.terrain`)
- `groups`: Node grouping definitions
- `modifiers`: Global modifiers
- `automation_variables`: Automation variable definitions
- `viewport_config`: Viewport settings
- `build_config`: Build configuration
- `auto_validate`: **NEW** - Enable automatic validation and fixing (default: `True`)
  - Validates all nodes and properties
  - Fixes invalid property values
  - Adds missing Export/SatMap nodes
  - Repairs connections
  - Ensures Gaea2 compatibility

**Returns:**
```python
{
    "success": bool,
    "output_path": str,
    "project_id": str,        # Unique project ID
    "terrain_id": str,        # Unique terrain ID
    "node_count": int,
    "connection_count": int,
    "validation": {           # Only present if auto_validate=True
        "valid": bool,
        "errors": List[str],
        "warnings": List[str],
        "fixes_applied": List[str],
        "quality_score": float  # 0-100
    }
}
```

**Automatic Validation Features (when `auto_validate=True`):**
- ✅ All node types validated against complete schema
- ✅ Property values corrected to valid ranges
- ✅ Missing Export node automatically added
- ✅ Missing color node (SatMap/ColorMap) automatically added
- ✅ Duplicate connections removed
- ✅ Invalid connections repaired
- ✅ Orphaned nodes connected or removed
- ✅ Performance-heavy properties optimized
- ✅ File format guaranteed to be Gaea2-compatible

### validate_and_fix_workflow

Validate and optionally fix a Gaea2 workflow.

```python
async def validate_and_fix_workflow(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    auto_fix: bool = True,
    aggressive: bool = False
) -> Dict[str, Any]
```

**Parameters:**
- `nodes`: List of workflow nodes
- `connections`: List of connections
- `auto_fix`: Whether to apply automatic fixes
- `aggressive`: Use aggressive fix mode (more intrusive fixes)

**Returns:**
```python
{
    "success": bool,
    "validation": {
        "property_issues": List[Dict],
        "connection_errors": List[str],
        "connection_warnings": List[str],
        "structure_issues": List[str]
    },
    "fixes": {
        "applied": List[str],
        "suggested": List[Dict]
    },
    "fixed_workflow": {
        "nodes": List[Dict],
        "connections": List[Dict]
    },
    "quality_scores": {
        "original": float,  # 0-100
        "fixed": float,     # 0-100
        "improvement": float
    }
}
```

### analyze_workflow_patterns

Analyze workflow to get pattern-based recommendations.

```python
async def analyze_workflow_patterns(
    current_workflow: List[Dict[str, Any]]
) -> Dict[str, Any]
```

**Parameters:**
- `current_workflow`: Current workflow nodes

**Returns:**
```python
{
    "success": bool,
    "recommendations": {
        "next_nodes": List[{
            "node": str,
            "probability": float,
            "frequency": int,
            "reason": str
        }],
        "missing_common_nodes": List[str],
        "workflow_quality": float,  # 0-100
        "similar_workflows": List[Dict]
    },
    "statistics": {
        "total_analyzed": int,
        "pattern_matches": int
    }
}
```

### repair_gaea2_project

Repair a damaged or invalid Gaea2 project.

```python
async def repair_gaea2_project(
    project_path: Optional[str] = None,
    project_data: Optional[Dict[str, Any]] = None,
    auto_fix: bool = True,
    backup: bool = True
) -> Dict[str, Any]
```

**Parameters:**
- `project_path`: Path to project file
- `project_data`: Project data (if already loaded)
- `auto_fix`: Apply automatic fixes
- `backup`: Create backup before fixing

**Returns:**
```python
{
    "success": bool,
    "analysis": {
        "health_score": float,  # 0-100
        "node_count": int,
        "connection_count": int,
        "errors": {
            "total_errors": int,
            "critical": int,
            "errors": int,
            "warnings": int,
            "auto_fixable": int
        }
    },
    "repair_result": {
        "fixes_applied": List[str],
        "backup_path": str
    }
}
```

### create_gaea2_from_template

Create project from predefined template.

```python
async def create_gaea2_from_template(
    template_name: str,
    project_name: str,
    output_path: Optional[str] = None,
    customizations: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Parameters:**
- `template_name`: Name of template (`basic_terrain`, `detailed_mountain`, `volcanic_terrain`, `desert_canyon`)
- `project_name`: Name for the new project
- `output_path`: Output file path
- `customizations`: Template customization options

**Returns:**
```python
{
    "success": bool,
    "template_used": str,
    "output_path": str,
    "node_count": int,
    "connection_count": int
}
```

### optimize_gaea2_properties

Optimize node properties for performance or quality.

```python
async def optimize_gaea2_properties(
    node_type: str,
    properties: Dict[str, Any],
    mode: str = "balanced"  # "performance", "quality", "balanced"
) -> Dict[str, Any]
```

**Parameters:**
- `node_type`: Type of node
- `properties`: Current properties
- `mode`: Optimization mode

**Returns:**
```python
{
    "success": bool,
    "original_properties": Dict,
    "optimized_properties": Dict,
    "changes": List[{
        "property": str,
        "original": Any,
        "optimized": Any,
        "reason": str
    }]
}
```

### suggest_gaea2_nodes

Get intelligent node suggestions.

```python
async def suggest_gaea2_nodes(
    terrain_type: Optional[str] = None,
    existing_nodes: Optional[List[str]] = None,
    purpose: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters:**
- `terrain_type`: Type of terrain (`mountain`, `desert`, `volcanic`, etc.)
- `existing_nodes`: Currently used nodes
- `purpose`: Intended use (`game`, `film`, `visualization`)

**Returns:**
```python
{
    "success": bool,
    "suggestions": List[{
        "node": str,
        "category": str,
        "reason": str,
        "priority": str,  # "essential", "recommended", "optional"
        "properties": Dict
    }]
}
```

### validate_gaea2_file

Validate if a Gaea2 terrain file actually opens in Gaea2.

```python
async def validate_gaea2_file(
    file_path: str,
    timeout: int = 30
) -> Dict[str, Any]
```

**Parameters:**
- `file_path`: Path to the .terrain file to validate
- `timeout`: Maximum time to wait for validation in seconds

**Returns:**
```python
{
    "success": bool,              # Whether the file opens successfully
    "file_path": str,
    "return_code": int,           # Gaea2 CLI exit code
    "duration": float,            # Validation time in seconds
    "timestamp": str,             # ISO timestamp
    "success_detected": bool,     # v2: Whether success patterns found
    "error_detected": bool,       # v2: Whether error patterns found
    "error": str,                 # Error message if failed
    "stdout": str,                # v2: Complete stdout output
    "stderr": str,                # v2: Complete stderr output
    "error_info": {               # Present if validation failed
        "error_types": List[str],
        "error_messages": List[str],
        "problematic_node": Optional[str],
        "problematic_property": Optional[str]
    }
}
```

**v2 Improvements:**
- Real-time pattern detection for immediate results
- Success confirmation with 3-second wait period
- Process termination after determining result
- Correctly identifies files that open successfully

### validate_gaea2_batch

Validate multiple Gaea2 terrain files concurrently.

```python
async def validate_gaea2_batch(
    file_paths: List[str],
    concurrent: int = 4
) -> Dict[str, Any]
```

**Parameters:**
- `file_paths`: List of .terrain file paths to validate
- `concurrent`: Number of concurrent validations

**Returns:**
```python
{
    "total_files": int,
    "validated": int,
    "successful": int,
    "failed": int,
    "error_types": Dict[str, int],    # Error type frequency
    "common_errors": List[Tuple[str, int]],  # Most common errors
    "results": List[Dict]             # Individual file results
}
```

### test_gaea2_template

Test a template by generating and validating multiple variations.

```python
async def test_gaea2_template(
    template_name: str,
    variations: int = 5,
    server_url: str = "http://localhost:8007"
) -> Dict[str, Any]
```

**Parameters:**
- `template_name`: Name of the template to test
- `variations`: Number of variations to generate and test
- `server_url`: MCP server URL for generating variations

**Returns:**
```python
{
    "success": bool,
    "template_name": str,
    "variations_tested": int,
    "successful": int,
    "failed": int,
    "error_types": Dict[str, int],
    "common_errors": List[Tuple[str, int]],
    "results": List[Dict]             # Validation results per variation
}
```

---

## Core Modules

### gaea2_schema

Core schema definitions and validation.

#### Functions

**validate_node_type(node_type: str) -> bool**
- Validates if a node type exists in schema

**get_node_info(node_type: str) -> Dict[str, Any]**
- Returns detailed information about a node type

**get_valid_properties(node_type: str) -> Dict[str, Any]**
- Returns valid properties and their constraints for a node

**apply_default_properties(node: Dict[str, Any]) -> Dict[str, Any]**
- Applies default properties to a node based on its type

### gaea2_validation

Basic validation functionality.

#### Classes

**Gaea2Validator**
```python
class Gaea2Validator:
    def validate_project(self, project_data: Dict) -> Tuple[bool, List[str]]
    def validate_node(self, node: Dict) -> Tuple[bool, List[str]]
    def validate_connection(self, connection: Dict, nodes: List[Dict]) -> Tuple[bool, List[str]]
```

---

## Validation Modules

### gaea2_structure_validator

Project structure validation.

#### Classes

**Gaea2StructureValidator**
```python
class Gaea2StructureValidator:
    def validate_structure(self, project_data: Dict) -> Tuple[bool, List[str], List[str]]
    def fix_structure(self, project_data: Dict, project_name: str = None) -> Dict
    def get_structure_report(self, project_data: Dict) -> Dict[str, Any]
```

### gaea2_property_validator

Property validation with pattern matching.

#### Classes

**Gaea2PropertyValidator**
```python
class Gaea2PropertyValidator:
    def validate_properties(
        self,
        node_type: str,
        properties: Dict[str, Any],
        strict: bool = False
    ) -> Tuple[bool, List[str], Dict[str, Any]]

    def suggest_missing_properties(
        self,
        node_type: str,
        existing_properties: Dict[str, Any]
    ) -> Dict[str, Any]

    def get_performance_optimized_properties(
        self,
        node_type: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]

    def get_quality_optimized_properties(
        self,
        node_type: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]
```

### gaea2_connection_validator

Connection compatibility validation.

#### Classes

**Gaea2ConnectionValidator**
```python
class Gaea2ConnectionValidator:
    def validate_connections(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], List[str]]

    def suggest_connections(
        self,
        nodes: List[Dict[str, Any]],
        existing_connections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]

    def get_connection_quality_score(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]]
    ) -> float
```

---

## Intelligence Modules

### gaea2_knowledge_graph

Node relationships and intelligent suggestions.

#### Classes

**NodeRelationship**
```python
class NodeRelationship:
    source: str
    target: str
    relationship_type: str  # "requires", "enhances", "commonly_follows", "conflicts_with"
    strength: float  # 0.0 - 1.0
    metadata: Dict[str, Any]
```

**Gaea2KnowledgeGraph**
```python
class Gaea2KnowledgeGraph:
    def add_relationship(self, relationship: NodeRelationship)
    def get_related_nodes(self, node_type: str, relationship_type: str = None) -> List[str]
    def get_workflow_suggestions(self, current_nodes: List[str]) -> List[Dict]
    def get_node_constraints(self, node_type: str) -> Dict[str, Any]
```

### gaea2_pattern_knowledge

Pattern database from real projects.

#### Constants

```python
COMMON_NODE_SEQUENCES: Dict[str, List[str]]  # Common node sequences
NODE_CONNECTION_FREQUENCY: Dict[str, Dict[str, float]]  # Connection probabilities
PROPERTY_RECOMMENDATIONS: Dict[str, Dict[str, Any]]  # Recommended properties
WORKFLOW_TEMPLATES: Dict[str, Dict[str, Any]]  # Complete workflow templates
```

#### Functions

**get_next_node_suggestions(current_node: str) -> List[Dict[str, Any]]**
- Get likely next nodes based on patterns

**get_workflow_for_terrain_type(terrain_type: str) -> Dict[str, Any]**
- Get recommended workflow for terrain type

**suggest_properties_for_node(node_type: str, context: Dict = None) -> Dict[str, Any]**
- Get recommended properties based on patterns

### gaea2_workflow_analyzer

Workflow analysis and optimization.

#### Classes

**Gaea2WorkflowAnalyzer**
```python
class Gaea2WorkflowAnalyzer:
    def analyze_workflow(self, nodes: List[Dict], connections: List[Dict]) -> Dict
    def get_workflow_complexity(self, nodes: List[Dict], connections: List[Dict]) -> Dict
    def find_bottlenecks(self, nodes: List[Dict]) -> List[Dict]
    def suggest_optimizations(self, workflow: Dict) -> List[Dict]
```

---

## Infrastructure Modules

### gaea2_cache

Performance caching system.

#### Classes

**Gaea2Cache**
```python
class Gaea2Cache:
    def __init__(self, cache_dir: Optional[str] = None, ttl: int = 3600)
    def get(self, operation: str, params: Dict[str, Any]) -> Optional[Any]
    def set(self, operation: str, params: Dict[str, Any], data: Any)
    def clear(self, operation: Optional[str] = None)
```

**CachedValidator**
```python
class CachedValidator:
    def cached_validate_node(
        self,
        node_type: str,
        properties: Dict[str, Any]
    ) -> Tuple[bool, List[str], Dict[str, Any]]

    def cached_suggest_connections(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]
```

### gaea2_logging

Structured logging with colors.

#### Classes

**Gaea2Logger**
```python
class Gaea2Logger:
    def log_operation(self, operation: str, params: Dict[str, Any])
    def log_validation_error(self, error_type: str, node_type: str, message: str, node_id: int = None)
    def log_node_operation(self, operation: str, node_type: str, node_id: int, message: str)
    def log_performance(self, operation: str, duration: float, item_count: int = None)
```

### gaea2_error_handler

Error classification and handling.

#### Enums

```python
class ErrorSeverity(Enum):
    CRITICAL = "critical"  # Project cannot be used
    ERROR = "error"        # Major issue that needs fixing
    WARNING = "warning"    # Minor issue, project still usable
    INFO = "info"          # Informational, no action needed

class ErrorCategory(Enum):
    VALIDATION = "validation"
    CONNECTION = "connection"
    PROPERTY = "property"
    STRUCTURE = "structure"
    COMPATIBILITY = "compatibility"
    PERFORMANCE = "performance"
```

#### Classes

**Gaea2Error**
```python
class Gaea2Error:
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    node_id: Optional[int]
    property_name: Optional[str]
    suggestion: Optional[str]
    auto_fixable: bool
```

**Gaea2ErrorHandler**
```python
class Gaea2ErrorHandler:
    def add_error(self, error: Gaea2Error)
    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[Gaea2Error]
    def get_auto_fixable_errors(self) -> List[Gaea2Error]
    def get_summary(self) -> Dict[str, Any]
```

---

## Data Structures

### Node Definition

```python
{
    "id": int,                    # Unique node ID (typically 100+)
    "type": str,                  # Node type (e.g., "Mountain", "Erosion2")
    "name": str,                  # Display name
    "position": {                 # Optional position
        "x": float,
        "y": float
    },
    "properties": {               # Node-specific properties
        "property_name": Any
    },
    "bypass": bool,               # Optional: bypass node
    "solo": bool,                 # Optional: solo node
    "automation": {               # Optional: automation data
        "variable": str,
        "expression": str
    }
}
```

### Connection Definition

**API Format** (used when creating projects):
```python
{
    "from_node": int,             # Source node ID
    "to_node": int,               # Target node ID
    "from_port": str,             # Source port (default: "Out")
    "to_port": str,               # Target port (default: "In")
    "order": int                  # Optional: connection order
}
```

**Important**: Connections in the actual .terrain file are stored differently:
- Connections are embedded within port definitions as `Record` objects
- Each port that receives a connection contains the connection information
- Connection IDs are handled as strings internally to prevent type mismatches

**Terrain File Format** (how connections are actually stored):
```json
{
    "Ports": {
        "$values": [
            {
                "Name": "In",
                "Type": "PrimaryIn",
                "Record": {
                    "$id": "123",
                    "From": 490,
                    "To": 174,
                    "FromPort": "Out",
                    "ToPort": "In",
                    "IsValid": true
                }
            }
        ]
    }
}
```

**Common Port Names by Node Type:**
- **Standard nodes**: "In", "Out"
- **Combine**: "In", "Input2", "Mask", "Out"
- **Rivers**: "In", "Out", "Rivers", "Depth", "Surface", "Direction", "Headwaters", "Mask"
- **Sea**: "In", "Out", "Water", "Depth", "Shore", "Surface"
- **TextureBase**: "In", "Out"
- **Height**: "In", "Out"
- **SatMap**: "In", "Out"

### Group Definition

```python
{
    "name": str,                  # Group name
    "node_ids": List[int],        # List of node IDs in group
    "color": str,                 # Hex color (e.g., "#FF5733")
    "collapsed": bool             # Optional: collapsed state
}
```

### Automation Variable

```python
{
    "name": str,                  # Variable name
    "value": float,               # Current value
    "min": float,                 # Minimum value
    "max": float,                 # Maximum value
    "step": float,                # Optional: step size
    "exposed": bool               # Optional: exposed to user
}
```

### Build Configuration

```python
{
    "resolution": int,            # Build resolution (512, 1024, 2048, 4096, 8192)
    "format": str,                # Output format ("EXR", "PNG", "TIF", "RAW")
    "bit_depth": int,             # Bit depth (8, 16, 32)
    "range": [float, float],      # Height range [min, max]
    "method": str,                # Build method ("Normal", "Tiled", "Streaming")
    "tile_size": int              # Optional: tile size for tiled builds
}
```

---

## Error Types

### Common Validation Errors

1. **Invalid Node Type**: Node type not in schema
2. **Missing Required Properties**: Required properties not provided
3. **Invalid Property Type**: Property value has wrong type
4. **Out of Range**: Numeric property outside valid range
5. **Invalid Enum Value**: Enum property has invalid value

### Common Connection Errors

1. **Invalid Node Reference**: Connection references non-existent node
2. **Incompatible Ports**: Source and target ports incompatible
3. **Circular Dependency**: Connection creates circular reference
4. **Duplicate Connection**: Same connection defined multiple times
5. **Orphaned Node**: Node has no connections

### Common Structure Errors

1. **Missing Metadata**: Required metadata fields missing
2. **Invalid Version**: Unsupported Gaea version
3. **Corrupt Structure**: JSON structure doesn't match schema
4. **Missing Assets**: Required assets section missing
5. **Invalid ID Format**: Node IDs not properly formatted

---

## Examples

### Basic Workflow Creation

```python
# Create a simple erosion workflow
nodes = [
    {
        "id": 100,
        "type": "Mountain",
        "name": "Base Terrain",
        "properties": {
            "Scale": 1.5,
            "Seed": 12345
        }
    },
    {
        "id": 101,
        "type": "Erosion2",
        "name": "Primary Erosion",
        "properties": {
            "Duration": 0.07,
            "Scale": 10000
        }
    },
    {
        "id": 102,
        "type": "SatMap",
        "name": "Colorization",
        "properties": {
            "Preset": "Rocky"
        }
    }
]

connections = [
    {"from_node": 100, "to_node": 101},
    {"from_node": 101, "to_node": 102}
]

result = await create_gaea2_project(
    project_name="Eroded Mountain",
    nodes=nodes,
    connections=connections
)
```

### Advanced Validation and Repair

```python
# Load a project and perform comprehensive validation
with open("complex_terrain.terrain") as f:
    project = json.load(f)

# Analyze the project
analysis = await repair_gaea2_project(
    project_data=project,
    auto_fix=False  # Just analyze, don't fix
)

print(f"Health Score: {analysis['analysis']['health_score']}/100")

# If issues found, fix them
if analysis['analysis']['errors']['total_errors'] > 0:
    fixed = await repair_gaea2_project(
        project_data=project,
        auto_fix=True,
        backup=True
    )

    print(f"Fixed {len(fixed['repair_result']['fixes_applied'])} issues")
```

### Pattern-Based Workflow Building

```python
# Build workflow using patterns
current_nodes = [
    {"type": "Mountain", "id": 100}
]

# Get next node suggestions
suggestions = await analyze_workflow_patterns(
    current_workflow=current_nodes
)

# Add suggested nodes
for suggestion in suggestions['recommendations']['next_nodes'][:3]:
    node_type = suggestion['node']

    # Get optimized properties
    props = await optimize_gaea2_properties(
        node_type=node_type,
        properties={},
        mode="balanced"
    )

    current_nodes.append({
        "type": node_type,
        "id": 100 + len(current_nodes),
        "properties": props['optimized_properties']
    })

# Create project with pattern-based workflow
result = await create_gaea2_project(
    project_name="Pattern-Based Terrain",
    nodes=current_nodes
)
```

---

*This API reference covers the complete Gaea2 MCP system. For usage examples and tutorials, see [GAEA2_EXAMPLES.md](GAEA2_EXAMPLES.md).*
