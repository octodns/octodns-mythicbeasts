# Developer Agent Guide for octoDNS Mythic Beasts Provider

This repository is an octoDNS provider module for Mythic Beasts DNS. It follows the same general workflow and repository conventions as other octoDNS provider repositories while implementing provider-side synchronization against the Mythic Beasts DNS API v2.

> [!IMPORTANT]
> **Core Workflow and Guidelines**
>
> All agents working in this repository must read and follow the general instructions in the core octoDNS AGENTS guide before making changes.
> - **Local check**: look for the file at `../octodns/AGENTS.md`.
> - **Remote check**: if the local file is not available, fetch it from GitHub: [octoDNS Core AGENTS.md](https://github.com/octodns/octodns/raw/refs/heads/main/AGENTS.md).
>
> This repository should align its structure, style, pull request guidance, and contributor workflow with the conventions used across the octoDNS organization.

## General Workflow & Guidelines

### 1. Create a Branch

Always start work by creating a new feature or bugfix branch:

```bash
git checkout -b <branch-name>
```

### 2. Verify

Before committing, verify that your changes satisfy the repository standards by running the relevant checks from the repository root:

```bash
./script/test
./script/coverage
./script/lint
./script/format
```

If you are changing provider behavior, add or update tests in [tests/test_octodns_provider_mythicbeasts.py](tests/test_octodns_provider_mythicbeasts.py) so the new logic is exercised without network access.

### 3. Create a Changelog Entry (First Commit)

The first commit on a branch should include a changelog entry. Use the helper script:

```bash
./script/changelog create --type <patch|minor|major> "brief description"
```

### 4. Subsequent Commits and Pull Requests

For subsequent commits, use normal git commits. When the work is ready, push the branch and open a pull request with a clear summary of the change.

## Repository and Module Overview

### Repository Structure

- [octodns_mythicbeasts/__init__.py](octodns_mythicbeasts/__init__.py): the provider implementation, including authentication, request helpers, record normalization, and apply logic.
- [tests/test_octodns_provider_mythicbeasts.py](tests/test_octodns_provider_mythicbeasts.py): the main unit test suite for provider behavior.
- [script/](script/): helper scripts for bootstrap, formatting, linting, testing, coverage, and changelog management.
- [README.md](README.md): user-facing installation and configuration guidance.

### Key Components

- **Provider class**: [MythicBeastsProvider](octodns_mythicbeasts/__init__.py) is the main octoDNS provider. It authenticates with the Mythic Beasts auth service, manages a persistent session, lists zones, fetches zone records, populates octoDNS zones, and applies create, update, and delete changes.
- **Exception**: [MythicBeastsZoneNotFoundException](octodns_mythicbeasts/__init__.py) is raised when a target zone does not exist in Mythic Beasts and cannot be created through the API.
- **Normalization helpers**: `_normalise_zone_name`, `_normalise_record_name`, and `_normalise_content` keep octoDNS naming conventions and Mythic Beasts naming conventions aligned.
- **Record translators**: the `_data_for_*` and `_contents_for_*` helpers convert between octoDNS record objects and Mythic Beasts API payload formats.

### Current Capabilities

- **Supported record types**: `A`, `AAAA`, `ALIAS`, `CNAME`, `MX`, `NS`, `SRV`, `SSHFP`, `CAA`, `TXT`, `TLSA`.
- **Dynamic records**: not supported. The provider sets `SUPPORTS_DYNAMIC = False` and `SUPPORTS_GEO = False`.
- **Zone creation**: not supported through the API. Applying changes to a zone requires that the zone already exists in Mythic Beasts.
- **TXT handling**: values are escaped when read from the API and unescaped before being sent back so literal semicolons are preserved.

### Authentication and Requests

- Authentication uses the API key/secret pair by posting to the Mythic Beasts auth endpoint and storing a Bearer token on the session.
- The provider uses direct HTTP requests to the DNS API v2 base URL and exposes wrapper helpers for `GET`, `POST`, `PUT`, `PATCH`, and `DELETE` operations.

## Development and Testing

- **Setup**: run `./script/bootstrap` to create the virtual environment and install runtime and development dependencies.
- **Formatting**: run `./script/format` to apply `isort` and `black`.
- **Linting**: run `./script/lint` to run `pyflakes`.
- **Tests**: run `./script/test` or `pytest --disable-network`.
- **Full CI check**: run `./script/cibuild`.
- **Coverage**: run `./script/coverage` to confirm the provider remains well covered by tests.

## Tips & Hints for AI

- Keep the normalization helpers and record translation layers consistent whenever record shape or naming behavior changes.
- Preserve the current semantics around TXT escaping, ALIAS/ANAME translation, and zone existence checks.
- Prefer small, test-driven changes and use the existing `requests_mock`-based tests rather than introducing network-dependent coverage.
- Follow the repository’s Python style conventions: `black`, `isort`, and `pyflakes` are part of the normal workflow.
- Mythic Beasts DNSv2 API docs are here: `https://www.mythic-beasts.com/support/api/dnsv2`
- Mythic Beasts auth API docs are here: `https://www.mythic-beasts.com/support/api/auth`