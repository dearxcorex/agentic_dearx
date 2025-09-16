# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an FM Station Inspection Planner that uses **LangGraph** and **OpenRouter API** for multi-agent route planning. The system plans optimal inspection routes for FM radio stations using Thai language processing and advanced route optimization algorithms.

## Architecture

### Multi-Agent System (LangGraph)
- **LanguageProcessingAgent**: Parses Thai user input and extracts requirements
- **LocationAgent**: Handles geocoding and location services
- **DatabaseAgent**: Queries Supabase for FM station data
- **RoutePlanningAgent**: Optimizes inspection routes using hybrid AI/algorithmic approach
- **PlanEvaluationAgent**: **NEW** - Analyzes route efficiency and suggests improvements
- **ResponseAgent**: Generates natural Thai language responses with route analysis

### Core Components
- `planner.py`: Main orchestrator using LangGraph StateGraph workflow
- `agents.py`: Individual agent node implementations
- `plan_evaluator.py`: **NEW** - AI-powered route analysis and optimization suggestions
- `openrouter_client.py`: OpenRouter API integration with cost tracking
- `database.py`: Supabase database interface for FM station data
- `route_optimizer.py`: Route optimization algorithms (TSP, 2-opt, Christofides)
- `auto_location.py`: **NEW** - Automatic GPS location detection
- `thai_processor.py`: Thai language processing utilities
- `config.py`: Model selection strategy and configuration

### Model Selection Strategy
- **All Tasks**: Google Gemini Flash 1.5 for optimal cost/performance
- **Thai Language**: Excellent Thai language support
- **Complex Reasoning**: Advanced route planning and optimization
- **Cost-Effective**: $0.075/$0.30 per 1M tokens (input/output)

## Development Commands

### Setup
```bash
pip install -r requirements.txt
```

### Environment Configuration
Create `.env` file with:
```env
GERMINI_FLASH=your_openrouter_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_key
```

### Running the Application
```bash
python main.py
```
- Option 1: Interactive mode with automatic location detection
- Option 2: Example demonstrations

**Interactive Mode Features:**
- Automatic GPS location detection
- No manual coordinate entry required
- Real-time province detection
- Perfect for mobile integration

### Testing
```bash
# Test LangGraph planner
python test_langgraph.py

# Test location functionality (offline)
python test_offline.py

# Test with location data
python test_location.py

# Test Gemini Flash integration
python test_gemini.py

# See Telegram bot examples
python telegram_example.py

# Test automatic location detection
python demo_auto_interactive.py

# Test plan evaluation agent
python test_plan_evaluation.py

# Run webhook server for production
python webhook_server.py
```

## Database Schema

The system uses Supabase with the `fm_stations` table:
```sql
CREATE TABLE fm_stations (
    id SERIAL PRIMARY KEY,
    station_name TEXT NOT NULL,
    frequency DECIMAL(5,2),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    province TEXT,
    district TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Route Optimization

Algorithm selection based on problem size:
- **≤ 8 stations**: Brute force (optimal)
- **9-10 stations**: Christofides algorithm
- **11-25 stations**: 2-opt local search
- **> 25 stations**: Nearest neighbor (greedy)

## Key Dependencies

- **langgraph>=0.2.0**: Agent workflow orchestration
- **supabase>=2.0.0**: Database integration
- **geopy>=2.3.0**: Geocoding services
- **networkx>=3.0**: Graph algorithms for route optimization
- **openai>=1.0.0**: OpenRouter API client base

## Thai Language Support

The system processes Thai language input for:
- Station count extraction ("หา 10 สถานี")
- Time constraint parsing ("30-40 นาที")
- Location identification ("จังหวัดชัยภูมิ")
- Natural Thai response generation

## Mobile & Telegram Bot Integration

### Real-time Location Support
- `location_tool.py`: GPS coordinate handling
- `telegram_bot.py`: Telegram webhook integration
- Real-time location from mobile devices
- Distance calculations and route optimization

### Telegram Bot Features
- Location sharing support
- Thai/English bilingual responses
- Mobile-optimized formatting with emojis
- Webhook integration for real-time processing

### Mobile App Integration
```python
# Direct API integration
from planner import FMStationPlanner
planner = FMStationPlanner()
result = planner.plan_inspection_with_location(
    "หาสถานี FM 10 แห่งใกล้ฉัน",
    (14.0583, 100.6014)  # GPS coordinates
)
```