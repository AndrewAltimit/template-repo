# Corporate Proxy Maintenance Guide

This document contains critical maintenance information for the corporate proxy system components.

## Text Tool Parser - Parameter Order Assumption

### Critical Requirement

The `TextToolParser` class in `shared/services/text_tool_parser.py` relies on **positional parameter order** when parsing Python-style function calls from AI responses.

#### Why This Matters

When AI models generate tool calls in Python format (e.g., `Write("file.txt", "content")`), the parser maps positional arguments to parameter names based on their order. This mapping is now generated programmatically from tool definitions, but **the order must be preserved**.

#### Implementation Details

The parser generates parameter mappings in `_generate_param_mappings()` method from:

1. **OpenAPI/JSON Schema format**: Extracts keys from `parameters.properties` dict
2. **List format**: Uses the order of parameter objects in the list
3. **Simple args format**: Uses the provided argument order

#### Maintenance Requirements

When modifying tool definitions or adding new tools:

1. **PRESERVE PARAMETER ORDER**: The order in which parameters are defined in tool definitions MUST match the expected positional argument order for Python-style calls.

2. **Tool Definition Formats**: Ensure tool definitions maintain consistent parameter order:
   ```python
   # OpenAPI/JSON Schema format
   {
       "write": {
           "parameters": {
               "properties": {
                   "file_path": {...},  # Position 0
                   "content": {...}     # Position 1
               }
           }
       }
   }

   # List format
   {
       "write": {
           "parameters": [
               {"name": "file_path"},  # Position 0
               {"name": "content"}     # Position 1
           ]
       }
   }
   ```

3. **Testing**: When adding new tools, verify that:
   - Parameter order in definitions matches expected positional order
   - Python-style parsing correctly maps arguments
   - Test with actual AI model outputs if possible

4. **Documentation**: Update this document when:
   - Adding new tool definition formats
   - Changing the parameter extraction logic
   - Modifying existing tool signatures

#### Common Pitfalls

- **Dict iteration order**: Python 3.7+ preserves dict insertion order, but be explicit about order requirements
- **Optional parameters**: Should come after required parameters in positional calls
- **Refactoring tools**: Changing parameter order breaks existing Python-style calls in AI responses

#### Current Capabilities

The parser supports both positional and keyword arguments:
- **Positional arguments**: `Write("file.txt", "content")`
- **Keyword arguments**: `Write(file_path="file.txt", content="content")`
- **Mixed**: `Write("file.txt", content="content")`

For maximum robustness, AI models should be encouraged to use keyword arguments in their system prompts.

#### Future Improvements

Consider these enhancements to reduce order dependency:
- Add validation to ensure definition order matches expected order
- Create automated tests that verify parameter ordering
- Update AI model prompts to prefer keyword arguments over positional

## Related Components

### Unified Tool API (`shared/services/unified_tool_api.py`)

Defines tool schemas used by mock services. When modifying:
- Ensure parameter order consistency across all tool definitions
- Update corresponding parser mappings if needed

### Tool Injector (`shared/services/text_tool_parser.py::ToolInjector`)

Injects tool instructions into AI prompts. Modifications should:
- Maintain clear parameter documentation
- Show correct usage examples with proper parameter order

## Version History

- **2024-08-31**: Initial documentation of parameter order assumption (per Gemini's review)
- **2024-08-31**: Implemented programmatic parameter mapping generation
