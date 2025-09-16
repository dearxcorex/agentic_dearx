# FM Station Inspection Planner - Folder Structure Plan

## Proposed Structure
```
fm_station_planner/
├── README.md                           # Main documentation
├── requirements.txt                    # Dependencies
├── .env                               # Environment variables
├── .gitignore                         # Git ignore file
├── setup.py                           # Package setup (future)
│
├── src/                               # Source code
│   ├── __init__.py
│   ├── main.py                        # Main entry point
│   │
│   ├── core/                          # Core business logic
│   │   ├── __init__.py
│   │   ├── planner.py                 # Main orchestrator
│   │   ├── agents.py                  # LangGraph workflow nodes
│   │   └── multi_day_planner.py       # Multi-day planning logic
│   │
│   ├── database/                      # Database operations
│   │   ├── __init__.py
│   │   └── database.py                # Station database operations
│   │
│   ├── services/                      # External services
│   │   ├── __init__.py
│   │   ├── openrouter_client.py       # LLM service
│   │   └── plan_evaluator.py          # Route evaluation service
│   │
│   ├── utils/                         # Utility modules
│   │   ├── __init__.py
│   │   ├── location_tool.py           # Location utilities
│   │   ├── location_province_mapper.py # GPS to province mapping
│   │   └── auto_location.py           # Auto location detection
│   │
│   └── config/                        # Configuration
│       ├── __init__.py
│       └── config.py                  # System configuration
│
├── docs/                              # Documentation
│   ├── SYSTEM_COMPLETE.md             # System overview
│   ├── DEPLOYMENT.md                  # Deployment guide
│   ├── CLAUDE.md                      # Claude development log
│   └── system_prompt.md               # System prompt documentation
│
├── tests/                             # Tests (future)
│   ├── __init__.py
│   ├── test_core/
│   ├── test_database/
│   └── test_services/
│
└── examples/                          # Usage examples
    ├── __init__.py
    └── basic_usage.py                 # Basic usage example
```

## Benefits of This Structure

1. **Separation of Concerns**: Each folder has a specific purpose
2. **Scalability**: Easy to add new features without clutter
3. **Maintainability**: Clear organization makes code easier to find and update
4. **Testing**: Dedicated test structure for future test implementation
5. **Documentation**: All docs in one place
6. **Package Structure**: Ready for pip installation if needed

## Migration Steps

1. Create directory structure
2. Move files to appropriate locations
3. Update all import statements
4. Create __init__.py files for proper Python package structure
5. Test the reorganized system
6. Update documentation with new structure