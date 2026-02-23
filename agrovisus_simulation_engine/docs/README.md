# AgroVisus Simulation Engine - Documentation Index

Welcome to the AgroVisus Simulation Engine documentation!

---

## 📚 Quick Links

### Getting Started
- [Main README](../README.md) - Project overview and quick start
- [Installation Guide](#installation) - Detailed setup instructions
- [Configuration Guide](#configuration) - Config reference

### Architecture
- [Architecture Overview](architecture/architecture_analysis.md) - System design
- [Model Protocols](architecture/model_protocols.md) - Interface contracts
- [Design Patterns](architecture/design_patterns.md) - Patterns used

### Guides
- [Running Simulations](guides/running_simulations.md) - How to run sims
- [Training RL Agents](guides/training_rl.md) - RL training guide
- [Model Configuration](guides/model_config.md) - Configuring models

### API Reference
- [SimulationService](api/simulation_service.md) - Main service API
- [SimulationFacade](api/simulation_facade.md) - RL interface API
- [ET0Service](api/et0_service.md) - ET0 calculation API
- [Models](api/models.md) - Model APIs

### Development
- [Contributing](development/contributing.md) - How to contribute
- [Testing](development/testing.md) - Running and writing tests
- [Code Style](development/code_style.md) - Style guidelines

---

## 📖 Documentation Structure

```
docs/
├── architecture/          # System architecture docs
├── guides/               # User guides
├── api/                  # API reference
├── development/          # Developer docs
└── walkthroughs/         # Implementation walkthroughs
```

---

## 🔍 Find What You Need

### I want to...

**Run a simulation**
→ See [Running Simulations](guides/running_simulations.md)

**Train an RL agent**
→ See [Training RL Agents](guides/training_rl.md)

**Understand the architecture**
→ See [Architecture Overview](architecture/architecture_analysis.md)

**Configure models**
→ See [Model Configuration](guides/model_config.md)

**Add new features**
→ See [Contributing](development/contributing.md)

**Write tests**
→ See [Testing](development/testing.md)

---

## 📝 Recent Updates

### Latest (Phase 3 Complete)
- ✅ ET0 consolidation walkthrough
- ✅ Model decoupling walkthrough
- ✅ Phase 3 complete summary

### Phase 2
- ✅ Config validation guide
- ✅ Soil validation guide
- ✅ Quick fixes walkthrough

---

## 💡 Key Concepts

### Services
- **SimulationService**: Orchestrates all models
- **ET0Service**: Calculates reference evapotranspiration
- **SimulationFacade**: Simplified interface for RL

### Models
- **CropModel**: Growth, phenology, biomass
- **SoilModel**: Water balance, drainage
- **NutrientModel**: N cycling, stress
- **DiseaseModel**: Disease pressure

### Patterns
- **Protocols**: Type-safe interfaces
- **Facade**: Simplified API
- **Service**: Business logic encapsulation

---

## 🎯 Documentation Goals

This documentation aims to:
- Help users get started quickly
- Explain architecture and design decisions
- Provide clear API references
- Guide contributors

---

For questions or suggestions, please open an issue!
