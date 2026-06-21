# Developer Agent Guide for octoDNS Mythic Beasts Provider

This repository contains the Mythic Beasts DNS provider for octoDNS. It enables planning, syncing, and applying DNS record states directly to Mythic Beasts DNS services.

> [!IMPORTANT]
> **Core Workflow and Guidelines**
>
> All agents working on this repository must read and follow the general instructions and workflow guidelines defined in the core octoDNS `AGENTS.md` file.
> - **Local check**: Look for the file at `../octodns/AGENTS.md`.
> - **Remote check**: If the local file is not available, fetch it from GitHub: [octoDNS Core AGENTS.md](https://github.com/octodns/octodns/raw/refs/heads/main/AGENTS.md).
>
> You must align your code structure, style, pull request guidelines, and overall development workflows with the instructions specified there.

## Repository & Module Information

### Key Components

- **Provider Class**: [MythicBeastsProvider](file:///home/ross/octodns/octodns-mythicbeasts/octodns_mythicbeasts/__init__.py#L58-L478) (defined in [octodns_mythicbeasts/__init__.py](file:///home/ross/octodns/octodns-mythicbeasts/octodns_mythicbeasts/__init__.py)). This is the core provider implementing dynamic command-line updates and zone downloads.
- **Exceptions**:
  - `MythicBeastsUnauthorizedException`: Triggered when API credentials lack access to the requested zone.
  - `MythicBeastsRecordException`: Triggered when the API fails to execute specific record addition/modification actions.

### Key Workflows & Features

1. **Supported Record Types**: `A`, `AAAA`, `ALIAS`, `CNAME`, `MX`, `NS`, `SRV`, `SSHFP`, `CAA`, `TXT`.
2. **Authentication**: Authenticates using the API key credential pair (`api_key` and `api_secret`).
3. **Response Regex Parsing**: Mythic Beasts API returns flat zone formats. The provider parses DNS records dynamically using a suite of internal compiled regular expressions:
   - `RE_MX`: Parses priority and exchange target hostnames.
   - `RE_SRV`: Parses priority, weight, port, and target variables.
   - `RE_SSHFP`: Parses algorithm numbers, fingerprint types, and hex strings.
   - `RE_CAA`: Parses flags, tags (issue, issuewild, iodef), and value strings.
   - `RE_POPLINE`: Parses standard response name/ttl/type lines.
4. **Dynamic Routing**: Not supported (`SUPPORTS_DYNAMIC=False`, `SUPPORTS_GEO=False`).
5. **Dynamic Subnets**: Not supported (`SUPPORTS_DYNAMIC_SUBNETS=False`).
6. **Pool Value Status**: Not supported (`SUPPORTS_POOL_VALUE_STATUS=False`).

## Development & Testing

- **Setup Script**: Run `./script/bootstrap` to create a virtual environment, install dependencies (including `black`, `isort`, `pyflakes`, and `pytest`), and configure pre-commit hooks.
- **Test Suite**: Run unit tests using `pytest` via `./script/test` (or `pytest tests/`). Test files are located in [tests/](file:///home/ross/octodns/octodns-mythicbeasts/tests).
- **Code Coverage**: Verify code coverage using `./script/coverage`.

## Key Constraints & Behaviors

- **Python Version**: Targets Python `>=3.9`.
- **Formatting**: Code formatting is enforced via `black` (version `>=26.0.0,<27.0.0`) and `isort`.
