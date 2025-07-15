# Changelog

All notable changes to **medagent-core** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.4.9] — 2025-07-15

### Added
- Extended safety module with improved error handling
- Added structured logging for drug operations
- New unit tests covering edge cases in audit pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async safety handler
- Fixed incorrect drug timeout calculation

## [v0.1.0] — 2025-06-24

### Added
- Initial project scaffold with biomedical AI core
- Basic medagent implementation
- README and setup documentation
