# Documentation Index

Navigate to the right documentation based on your role.

---

## By Role

### Developer

New to the codebase? Start here:

1. [README.md](README.md) - Project overview and quick start
2. [setup.md](setup.md) - Environment setup and IDE configuration
3. [developer-guidelines.md](developer-guidelines.md) - Code style and contribution workflow
4. [architecture/system-overview.md](architecture/system-overview.md) - Tech stack and design patterns

### AI Assistant

Working with AI coding tools? Start here:

1. [AI_CONTEXT.md](AI_CONTEXT.md) - Entry point with essential commands and references
2. [AGENTS.md](AGENTS.md) - Code patterns and prompt templates
3. [architecture/system-overview.md](architecture/system-overview.md) - Architecture context

### Code Reviewer

Reviewing PRs or auditing code? Start here:

1. [architecture/code-analysis.md](architecture/code-analysis.md) - Code quality and security analysis
2. [developer-guidelines.md](developer-guidelines.md) - Coding standards
3. [architecture/system-overview.md](architecture/system-overview.md) - Design patterns

### Operator

Deploying or troubleshooting? Start here:

1. [README.md](README.md) - Command reference
2. [troubleshooting.md](troubleshooting.md) - Common issues and solutions
3. [setup.md](setup.md) - Docker and environment setup

---

## By Topic

### Getting Started
- [README.md](README.md) - Quick start guide
- [setup.md](setup.md) - Full environment setup

### CLI Commands
- [README.md](README.md) - Command reference
- [troubleshooting.md](troubleshooting.md) - Command-specific issues

### Architecture
- [architecture/system-overview.md](architecture/system-overview.md) - High-level design
- [diagrams/plantuml/](diagrams/plantuml/) - Visual diagrams

### Code Quality
- [architecture/code-analysis.md](architecture/code-analysis.md) - Test coverage, issues
- [developer-guidelines.md](developer-guidelines.md) - Standards

### AI Development
- [AI_CONTEXT.md](AI_CONTEXT.md) - AI assistant entry point
- [AGENTS.md](AGENTS.md) - Patterns and prompts

---

## Quick Links

| I want to... | Go to... |
|--------------|----------|
| Run the CLI | [README.md](README.md) |
| Set up dev environment | [setup.md](setup.md) |
| Understand the architecture | [architecture/system-overview.md](architecture/system-overview.md) |
| Fix a problem | [troubleshooting.md](troubleshooting.md) |
| Contribute code | [developer-guidelines.md](developer-guidelines.md) |
| Use AI assistance | [AI_CONTEXT.md](AI_CONTEXT.md) |
| Review code quality | [architecture/code-analysis.md](architecture/code-analysis.md) |

---

## File Structure

```
docs/
├── INDEX.md                          # This file
├── README.md                         # Quick start, API overview
├── AI_CONTEXT.md                     # AI assistant entry point
├── AGENTS.md                         # AI pair programming guide
├── setup.md                          # Environment setup
├── developer-guidelines.md           # Code style, git workflow
├── troubleshooting.md                # Common issues
├── architecture/
│   ├── system-overview.md            # Tech stack, design
│   └── code-analysis.md              # Quality analysis
└── diagrams/
    └── plantuml/
        ├── architecture.puml         # System components
        ├── sync-db-sequence.puml     # Import flow
        └── key-retrieval.puml        # Retrieval flow
```
