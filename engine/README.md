# AgroVisus Simulation Engine

A sophisticated agricultural simulation platform combining crop growth modeling, soil water balance, nutrient cycling, and disease pressure modeling with reinforcement learning capabilities.

---

## 🌟 Features

- **Multi-Model Simulation**: Integrated crop, soil, nutrient, and disease models
- **Crop Templates**: Pre-validated parameter sets for Corn, Wheat, Rice, Soybean, and Sorghum
- **Weather Integration**: Automated weather data via Open-Meteo with smart caching & fallbacks
- **Interactive Dashboard**: Streamlit + Plotly dashboard with crop comparison
- **Batch Comparison**: CLI tool to compare multiple crops side-by-side
- **HTML Reports**: Dark-themed, auto-generated reports with KPIs and plots
- **Reinforcement Learning**: Custom Gymnasium environment for RL-based farm management
- **Robust Error Handling**: Custom exception hierarchy with user-friendly messages
- **Configurable**: JSON-based configuration with template overrides

---

## 📁 Project Structure

```
agrovisus_simulation_engine/
├── app/                          # Core application code
│   ├── data/                     # Data files
│   │   └── crop_templates.json  # Pre-validated crop parameters (5 crops)
│   ├── env/                      # RL environment
│   │   └── agrovisus_env.py     # Gymnasium environment
│   ├── models/                   # Simulation models
│   │   ├── crop_model.py        # Crop growth model (with validation)
│   │   ├── soil_model.py        # Soil water balance
│   │   ├── nutrient_model.py    # Nutrient cycling
│   │   ├── disease_model.py     # Disease pressure
│   │   ├── rule_evaluator.py    # Expert rules
│   │   └── protocols.py         # Model interfaces
│   ├── services/                 # Business logic services
│   │   ├── simulation_service.py # Main simulation orchestrator
│   │   ├── simulation_facade.py  # Clean API for RL environment
│   │   ├── et0_service.py       # ET0 calculation service
│   │   ├── weather_service.py   # Weather data (Open-Meteo + caching)
│   │   ├── report_generator.py  # HTML report generation
│   │   ├── report_data_manager.py # CSV data management
│   │   ├── data_manager.py      # Data loading
│   │   └── reporting_service.py # Daily report data
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── simulation_report_template.html
│   │   └── comparison_report_template.html
│   └── utils/                    # Utility functions
│       ├── calculations.py       # Scientific calculations
│       ├── validators.py         # Input validation
│       ├── config_loader.py      # Configuration utilities
│       ├── crop_template_loader.py # Crop template management
│       ├── exceptions.py         # Custom exception hierarchy
│       └── leaf_wetness_model.py # Leaf wetness calculation
│
├── tests/                        # Test suite (8 files, 60+ tests)
│   ├── test_integration.py      # End-to-end simulation tests
│   ├── test_crop_templates.py   # Template loading & validation
│   ├── test_weather_service.py  # Weather service & fallbacks
│   ├── test_exceptions.py       # Exception hierarchy
│   ├── test_validators.py       # Input validators
│   ├── test_soil_model_fixes.py # Soil model
│   ├── test_simulation_service.py
│   └── test_rl_env.py
│
├── data/                         # Simulation data
├── outputs/                      # Simulation outputs, reports, plots
├── config.json                   # Main configuration
├── rules.json                    # Expert rules
├── requirements.txt              # Python dependencies
│
├── run.py                        # Run single simulation
├── scenario_runner.py            # Batch compare multiple crops
├── dashboard.py                  # Streamlit interactive dashboard
├── train_agent.py                # Train RL agent
└── diagnose_v3_agent.py         # Evaluate trained agent
```

---

## 🚀 Quick Start

### Installation

```bash
cd agrovisus_simulation_engine
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### Run a Simulation

```bash
# Standard simulation (uses config.json)
python run.py

# Custom duration and crop
python run.py -d 120

# Launch interactive dashboard
streamlit run dashboard.py

# Compare multiple crops
python scenario_runner.py --crops corn wheat rice --days 120
python scenario_runner.py --all --days 90
```

---

## 🔧 Configuration

Edit `config.json` to customize:

- **Simulation Settings**: Duration, location, dates
- **Crop Template**: Select from `corn`, `wheat`, `rice`, `soybean`, `sorghum`
- **Model Parameters**: Crop, soil, nutrient, disease configs
- **Weather Service**: API keys, caching, fallback behavior
- **RL Environment**: Economics, penalties, ET0 method

### Crop Templates

Set `crop_template` in `config.json` to use pre-validated parameters:

```json
{
  "crop_model_config": {
    "crop_template": "wheat"
  }
}
```

Available templates: `corn`, `wheat`, `rice`, `soybean`, `sorghum`

Override individual parameters alongside the template:

```json
{
  "crop_model_config": {
    "crop_template": "corn",
    "harvest_index": 0.55
  }
}
```

---

## 🏗️ Architecture

### Core Services

- **SimulationService**: Orchestrates all models and manages simulation loop
- **ET0Service**: Unified evapotranspiration calculation (Penman-Monteith/Hargreaves)
- **SimulationFacade**: Clean API for RL environment, reduces coupling

### Models (Follow Protocol Interfaces)

- **CropModel** (`ICropModel`): Growth stages, biomass, GDD tracking
- **SoilModel** (`ISoilModel`): Multi-layer water balance with validation
- **NutrientModel** (`INutrientModel`): Nitrogen cycling and stress
- **DiseaseModel** (`IDiseaseModel`): Disease pressure based on weather

### Design Patterns

- **Facade Pattern**: SimulationFacade provides simplified interface
- **Service Pattern**: Business logic encapsulated in services
- **Protocol/Interface**: Type-safe model contracts
- **Dependency Injection**: Services receive dependencies

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_validators.py

# Run with coverage
python -m pytest --cov=app tests/
```

---

## 📊 Model Details

### Crop Model
- Growth stages: Emergence → Vegetative → Reproductive → Maturity
- GDD-based phenology
- Biomass accumulation via radiation use efficiency
- Water and nutrient stress factors

### Soil Model
- Multi-layer cascading bucket model
- Gravity drainage and capillary rise
- ET-based water extraction
- Water balance validation

### Nutrient Model
- Nitrogen mineralization and immobilization
- Fertilizer application tracking
- Crop N demand and uptake
- N stress calculation

### Disease Model
- Weather-driven disease pressure
- Multiple disease types (blight, rust, mildew)
- Leaf wetness duration calculation

---

## 🤖 Reinforcement Learning

### Environment

- **Action Space**: Discrete(4) - Nothing, Irrigate, Fertilize
- **Observation Space**: Normalized crop and soil state
- **Reward**: Economic value minus costs and penalties

### Training

```python
from app.env.agrovisus_env import AgroVisusEnv
from stable_baselines3 import PPO

env = AgroVisusEnv(config, project_root)
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100000)
model.save("trained_agent")
```

---

## 📚 Documentation

Comprehensive documentation available in the artifacts directory:

### Architecture & Design
- `architecture_analysis.md` - System architecture analysis
- `refactoring_plan.md` - Phase 3 refactoring plan

### Implementation Walkthroughs
- `phase3_complete_summary.md` - Complete Phase 3 summary
- `et0_consolidation_walkthrough.md` - ET0 service implementation
- `model_decoupling_walkthrough.md` - Facade pattern implementation
- `quick_fixes_walkthrough.md` - Phase 2 improvements
- `config_validation_walkthrough.md` - Validation implementation
- `soil_validation_walkthrough.md` - Soil model validation

### Progress Tracking
- `task.md` - Task completion checklist
- `progress_review.md` - Gap analysis and progress
- `cleanup_summary.md` - Project cleanup record

---

## 🔄 Recent Improvements

### Phase 4: Core Engine Completion (Latest)

✅ **Weather Hardening** (Week 1)
- Open-Meteo integration with smart caching
- Custom exception hierarchy with user-friendly messages
- Automatic fallback when primary weather source fails

✅ **Crop Templates** (Week 2)
- Pre-validated parameters for 5 crops (Corn, Wheat, Rice, Soybean, Sorghum)
- Template override system for custom experiments
- Input validation on all crop model parameters

✅ **Output & Reporting** (Week 3)
- Dark-themed HTML reports with 7 KPI cards
- Interactive Streamlit dashboard with Plotly charts
- Crop comparison tab with run history
- Clean console summary after each simulation

✅ **Integration & Polish** (Week 4)
- Batch scenario runner for multi-crop comparison
- Comparative HTML reports with side-by-side KPIs
- End-to-end integration test suite
- Updated documentation

### Phase 3: Refactoring

✅ ET0 consolidation, model protocols, SimulationFacade

### Phase 2: Architecture

✅ Input validation, config validation, soil model fixes

### Phase 1: Bug Fixes

✅ Fixed water drainage, extraction logic, shared config loader

---

## 🛠️ Development

### Code Style

- Follow PEP 8
- Type hints for public APIs
- Docstrings for classes and public methods

### Adding New Features

1. Define protocol in `app/models/protocols.py` if creating new model
2. Implement model/service in appropriate directory
3. Add configuration to `config.json`
4. Write tests in `tests/`
5. Update documentation

---

## 📈 Performance

- **Simulation Speed**: ~0.1s per day (120-day season in ~12s)
- **RL Training**: ~1000 episodes in 10-15 minutes
- **ET0 Calculation**: Hargreaves 10x faster than Penman-Monteith

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📝 License

[Add license information]

---

## 📧 Contact

[Add contact information]

---

## 🙏 Acknowledgments

- FAO-56 for Penman-Monteith ET0 method
- PyET library for ET0 calculations
- Stable-Baselines3 for RL algorithms
- Gymnasium for RL environment framework
