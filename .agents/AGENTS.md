# Workspace Rules for AI Simulation Monitor

## GLOBAL PROJECT RULE — NO IMSR2 DEPENDENCY

The current project (`D:\cms\AI-Simulation-Monitor-main`) MUST be completely independent of the old IMSR project (`D:\cms\imsr2`).

- `D:\cms\imsr2` is NOT part of the current application.
- DO NOT use `D:\cms\imsr2` as a source of code, runtime values, patient data, scenario data, simulation parameters, monitor parameters, waveform data, configuration, environment variables, API endpoints, WebSocket state, database data, authentication data, user data, session data, stores, utilities, assets, backend logic, frontend logic, fallback values, or default values.
- DO NOT import, read, reference, create paths, or fall back to `D:\cms\imsr2`.
- The application must continue to work correctly if `D:\cms\imsr2` is completely deleted or unavailable.
- Current project (`D:\cms\AI-Simulation-Monitor-main`) is the single source of truth.
