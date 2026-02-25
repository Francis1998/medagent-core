# Changelog

All notable changes to **medagent-core** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.1.2] — 2026-02-25

### Added
- Extended audit module with improved error handling
- Added structured logging for reasoning operations
- New unit tests covering edge cases in drug pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async audit handler
- Fixed incorrect reasoning timeout calculation

## [v0.1.0] — 2026-01-14

### Added
- Initial project scaffold with biomedical AI core
- Basic medagent implementation
- README and setup documentation
