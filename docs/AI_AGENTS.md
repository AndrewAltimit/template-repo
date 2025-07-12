# AI Agents Documentation

This project utilizes three AI agents working in harmony to accelerate development while maintaining high code quality.

## The Three AI Agents

### 1. Claude Code (Primary Development Assistant)

**Role**: Main development partner for complex tasks

**Responsibilities**:

- Architecture design and implementation
- Complex refactoring and debugging
- Writing comprehensive documentation
- Creating and modifying CI/CD pipelines
- Test development and coverage improvement
- Following project-specific guidelines in CLAUDE.md

**Access**: claude.ai/code

**Key Features**:

- Deep understanding of entire codebase
- Can execute commands and modify multiple files
- Follows container-first philosophy
- Optimized for single-maintainer workflow

### 2. Gemini CLI (Automated PR Reviewer)

**Role**: Quality gatekeeper for all code changes

**Responsibilities**:

- Automatically reviews every pull request
- Focuses on security vulnerabilities
- Checks container configurations
- Validates adherence to project standards
- Provides actionable feedback

**Setup**: Runs on self-hosted runners via Node.js

**Key Features**:

- Conversation history cleared before each review
- Receives PROJECT_CONTEXT.md for targeted feedback
- Non-blocking (PR can proceed if review fails)
- Focuses on project-specific concerns

### 3. GitHub Copilot (Code Review)

**Role**: Additional code review perspective

**Responsibilities**:

- Reviews code changes in pull requests
- Suggests improvements and optimizations
- Identifies potential issues
- Provides alternative implementations

**Access**: GitHub pull request interface

**Key Features**:

- Complements Gemini's automated reviews
- Provides inline suggestions
- Focuses on code quality and best practices

## How They Work Together

### Development Flow

1. **Planning Phase**:
   - Claude Code helps design architecture
   - Creates implementation plan
   - Sets up project structure

2. **Implementation Phase**:
   - Claude Code handles complex logic
   - Focus on architecture and design
   - Test-driven development

3. **Review Phase**:
   - Gemini automatically reviews PR
   - Copilot provides additional review suggestions
   - Claude Code addresses review comments
   - Two-layer review ensures quality

### Division of Labor

| Task | Claude Code | Gemini CLI | Copilot |
|------|------------|------------|---------|
| Architecture Design | ✅ Primary | ❌ | ❌ |
| Implementation | ✅ Primary | ❌ | ❌ |
| Documentation | ✅ Primary | ❌ | ❌ |
| Code Review | ❌ | ✅ Primary | ✅ Secondary |
| Security Review | ❌ | ✅ Primary | ✅ Assists |
| Test Writing | ✅ Primary | ❌ | ❌ |
| CI/CD Changes | ✅ Primary | ✅ Reviews | ✅ Reviews |

## Best Practices

### For Claude Code

- Provide clear CLAUDE.md guidelines
- Use for complex, multi-file changes
- Leverage for documentation and tests
- Ask to follow container-first approach

### For Gemini Reviews

- Keep PROJECT_CONTEXT.md updated
- Clear history before reviews
- Focus feedback on security and standards
- Don't block PR on review failures

### For Copilot

- Enable for pull request reviews
- Consider all suggestions carefully
- Provides different perspective from Gemini
- Focuses on code optimization and patterns

## Configuration

### Claude Code Setup

- Follows CLAUDE.md guidelines
- Has access to all project commands
- Understands container-first philosophy

### Gemini CLI Setup

```bash
npm install -g @google/gemini-cli
gemini  # Authenticate on first use
```

### Copilot Setup

- Enable in repository settings
- Configure for pull request reviews
- Set review preferences

## Benefits of Multi-Agent Approach

1. **Complementary Strengths**: Each agent excels at different tasks
2. **Two-Layer Review**: Both Gemini and Copilot review PRs
3. **Quality Assurance**: Multiple perspectives on code quality
4. **Efficiency**: Automated reviews catch issues early
5. **Learning**: Agents provide different insights

## Future Possibilities

- Integration with more specialized agents
- Custom training on project patterns
- Automated issue resolution
- AI-driven test generation
- Performance optimization suggestions

---

This multi-agent approach enables a single developer to maintain professional-grade code quality and development velocity typically associated with larger teams.
