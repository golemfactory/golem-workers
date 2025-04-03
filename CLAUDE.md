# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Lint/Test Commands

- Install dependencies: `poetry install`
- Run all code checks: `poetry run poe checks`
- Run code style checks: `poetry run poe checks_codestyle`
- Run only linting: `poetry run poe _checks_lint`
- Run only format check: `poetry run poe _checks_format`
- Format code: `poetry run poe format`
- Extract OpenAPI: `poetry run poe extract_openapi`

## Code Style Guidelines

- Line length: max 100 characters
- Quotes: double quotes for strings
- Imports: absolute imports only (ban-relative-imports)
- Types: Use type hints and modern Python typing features
- Formatting: Use Ruff for auto-formatting
- Error handling: Validate inputs and raise descriptive exceptions
- Models: Use Pydantic for data validation with model_config = ConfigDict
- Naming: Use snake_case for variables/functions, PascalCase for classes
- Dependency Injection: Use dependency-injector with Container/providers
- Comments: Include docstrings for classes explaining their purpose