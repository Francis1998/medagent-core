# Changelog

All notable changes to **medagent-core** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.5.3] — 2024-06-12

### Added
- Extended clinical module with improved error handling
- Added structured logging for audit operations
- New unit tests covering edge cases in health pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async clinical handler
- Fixed incorrect audit timeout calculation

## [v0.1.0] — 2024-05-29

### Added
- Initial project scaffold with biomedical AI core
- Basic medagent implementation
- README and setup documentation
