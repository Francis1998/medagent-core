# Changelog

All notable changes to **medagent-core** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.6.4] — 2024-04-09

### Added
- Extended drug module with improved error handling
- Added structured logging for health operations
- New unit tests covering edge cases in safety pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async drug handler
- Fixed incorrect health timeout calculation

## [v0.1.0] — 2024-03-05

### Added
- Initial project scaffold with biomedical AI core
- Basic medagent implementation
- README and setup documentation
