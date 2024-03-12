# Changelog

All notable changes to **medagent-core** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.1.9] — 2024-03-11

### Added
- Extended audit module with improved error handling
- Added structured logging for clinical operations
- New unit tests covering edge cases in drug pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async audit handler
- Fixed incorrect clinical timeout calculation

## [v0.1.0] — 2024-02-12

### Added
- Initial project scaffold with biomedical AI core
- Basic medagent implementation
- README and setup documentation
