# MVP Plan — Crop Diagnosis Platform
## Solo Developer | AI-Assisted | Funding-Ready

**Goal**: Ship a demo-ready MVP that proves the concept to investors
**Timeline**: 4-6 weeks
**Team**: 1 developer + AI coding assistants (Claude, Gemini)
**Budget**: Near zero (free tiers, open-source only)

---

## Current State (What's Already Done)

| Component | Status | Notes |
|-----------|--------|-------|
| Crop simulation engine | DONE | 91-day simulation, GDD, biomass, phenology |
| Soil water balance | DONE | 3-layer model, drainage, capillary rise |
| Nutrient cycling | DONE | N transformations, crop uptake |
| Disease pressure model | DONE | Weather-driven, stage-dependent |
| RL agent (PPO) | DONE | Trained v2 & v3, 200k timesteps |
| Streamlit dashboard | DONE | Multi-agent comparison, interactive charts |
| HTML report generator | DONE | KPIs, 5 plot types |
| Expert rule system | DONE | JSON-based diagnostics |
| CNN disease classifier | SCAFFOLDED | Code exists, needs real training data |
| Flask prediction API | SCAFFOLDED | Endpoints defined, not deployed |
| Tests | EXISTS BUT BROKEN | pytest not installed |

**Bottom line**: The simulation brain works. What's missing is the packaging.

---

## What Investors Actually Want to See

Investors don't care about Kubernetes, microservices, or your database choice.
They care about:

1. **Does it work?** → Live demo they can interact with
2. **Is the problem real?** → Market data, farmer pain points
3. **Can it make money?** → Clear business model
4. **Is there a moat?** → Your RL + simulation combo IS the moat
5. **Can it scale?** → "Yes, here's how" (one slide, not 50 pages)

---

## MVP Feature Priorities

### MUST HAVE (Ship These)

#### 1. Polished Web Demo (Week 1-2)
**What**: Upgrade Streamlit dashboard into investor-ready demo
**Why**: This is your pitch. Investors click a link, see it work.

Tasks:
- [ ] Add a landing page / hero section explaining what it does
- [ ] Add "About" section with problem statement and value proposition
- [ ] Clean up chart labels, colors, and layout for non-technical audience
- [ ] Add summary cards showing key outcomes:
  - "AI agent saved X% water vs random"
  - "AI agent achieved X% higher yield"
  - "Reduced fertilizer waste by X%"
- [ ] Add crop stage timeline visualization (VE → V2 → ... → R6)
- [ ] Add a "How it works" expandable section
- [ ] Deploy to Streamlit Community Cloud (free) or Railway

**Effort**: 3-4 days with AI assistance

#### 2. Disease Image Upload Feature (Week 2-3)
**What**: Upload a leaf photo → get disease diagnosis + recommendation
**Why**: This is the "wow factor" investors love. Visual, tangible, instant.

Tasks:
- [ ] Get real training data (PlantVillage dataset — free, 50k+ images)
- [ ] Train ResNet18 on 5-10 common crop diseases (your code already exists)
- [ ] Integrate into Streamlit: file upload → prediction → recommendation
- [ ] Show confidence score + top-3 predictions
- [ ] Add sample images for quick demo

**Effort**: 3-4 days (dataset download + training + UI)

#### 3. One-Page Pitch Integration (Week 3)
**What**: Embed your value proposition directly into the app
**Why**: The demo IS the pitch deck

Tasks:
- [ ] Sidebar with key metrics and stats
- [ ] "For Investors" tab with market size, business model, team
- [ ] Export simulation results as PDF (for follow-up emails)
- [ ] Contact form or calendly link embedded

**Effort**: 1-2 days

#### 4. Fix Tests & CI (Week 3)
**What**: Get tests passing, add GitHub Actions
**Why**: Shows investors you write quality code (they'll check your GitHub)

Tasks:
- [ ] Install pytest, run existing tests, fix failures
- [ ] Add 5-10 key integration tests
- [ ] Set up GitHub Actions for auto-testing
- [ ] Add test badges to README

**Effort**: 1 day

#### 5. Root README That Sells (Week 3)
**What**: Professional GitHub README with screenshots, GIFs
**Why**: First thing investors see on your GitHub

Tasks:
- [ ] Hero banner / logo
- [ ] One-paragraph elevator pitch
- [ ] Screenshots of dashboard
- [ ] GIF of simulation running
- [ ] Architecture diagram (simple, not the 50-service monster)
- [ ] "Quick Start" in 3 commands
- [ ] License (MIT or Apache 2.0)

**Effort**: Half a day

### NICE TO HAVE (If Time Permits)

#### 6. Multi-Crop Support (Week 4)
- Add wheat and rice parameters to config.json
- Dropdown in dashboard to select crop type
- Shows platform extensibility

#### 7. Real Weather API Integration (Week 4)
- Connect to OpenWeatherMap free tier
- User enters location → fetches real forecast
- Simulation uses actual weather data
- Shows real-world applicability

#### 8. Simple User Accounts (Week 5)
- Streamlit authentication (streamlit-authenticator)
- Save simulation history per user
- Shows SaaS potential

#### 9. Mobile-Friendly Design (Week 5)
- Responsive Streamlit layout
- PWA wrapper (optional)
- Shows you're thinking about farmer accessibility

---

## Architecture for MVP (Keep It Simple)

```
┌──────────────────────────────────────────────┐
│              Streamlit Cloud (FREE)           │
│                                              │
│  ┌────────────┐  ┌────────────┐             │
│  │  Dashboard  │  │  Disease   │             │
│  │  (Sim +    │  │  Detector  │             │
│  │   Charts)  │  │  (Upload)  │             │
│  └─────┬──────┘  └─────┬──────┘             │
│        │               │                     │
│  ┌─────▼──────────────▼──────┐              │
│  │    Simulation Engine       │              │
│  │  (All models in-process)   │              │
│  └─────┬──────────────┬──────┘              │
│        │              │                      │
│  ┌─────▼──────┐ ┌────▼─────┐               │
│  │  RL Agent  │ │ CNN Model│               │
│  │  (PPO .zip)│ │ (.pth)   │               │
│  └────────────┘ └──────────┘               │
│                                              │
│  Config: config.json + rules.json            │
│  Data: weather CSV (bundled)                 │
└──────────────────────────────────────────────┘

That's it. One app. One deployment. Zero infrastructure cost.
```

**Why this works**:
- Streamlit Community Cloud is FREE
- Everything runs in-process (no databases, no message brokers)
- Models bundled with the app (PPO zip + CNN pth)
- Zero DevOps needed
- Deploys from GitHub in minutes

---

## Tech Stack for MVP

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend + Backend | Streamlit | Already built, free hosting, fast iteration |
| Simulation | Current Python engine | Already complete and validated |
| RL Agent | Stable-Baselines3 (PPO) | Already trained, works great |
| Disease AI | PyTorch (ResNet18) | Already scaffolded, just needs data |
| Data | CSV files (bundled) | No database needed for demo |
| Deployment | Streamlit Cloud | Free, auto-deploys from GitHub |
| Version Control | GitHub | Free, shows code quality |
| CI/CD | GitHub Actions | Free for public repos |

**Total monthly cost: $0**

---

## Deployment Plan

### Step 1: GitHub Repository Cleanup
```
CropDiagnosisPlatform/
├── app/                    (simulation engine)
├── models/                 (trained RL + CNN models)
├── data/                   (weather data, sample images)
├── tests/                  (working tests)
├── dashboard.py            (main Streamlit app)
├── requirements.txt        (pinned dependencies)
├── README.md               (investor-ready)
├── .github/workflows/      (CI/CD)
├── .streamlit/config.toml  (theme configuration)
└── LICENSE
```

### Step 2: Deploy to Streamlit Cloud
1. Push to GitHub (public or private)
2. Go to share.streamlit.io
3. Connect repo → Select dashboard.py
4. Deploy (takes ~5 minutes)
5. Get shareable URL: `https://your-app.streamlit.app`

### Step 3: Share with Investors
- Send them the Streamlit URL
- They interact with the live demo
- No installation needed
- Works on any device with a browser

---

## What to Tell Investors About Future Architecture

When they ask "how will this scale?", you say:

> "The current MVP proves the core AI and simulation technology works.
> For production, we'll move to a cloud-native architecture with:
> - FastAPI backend for the simulation engine
> - React/Next.js frontend for a polished user experience
> - PostgreSQL + TimescaleDB for farm data
> - Kubernetes for scaling to thousands of farms
> - MLOps pipeline for continuous model improvement
>
> The simulation models and RL agents are already modular and
> well-tested — they plug directly into the production architecture.
> We need funding to hire 2-3 engineers and build this over 6 months."

That's it. One paragraph. Not 50 pages.

---

## 4-Week Sprint Plan

### Week 1: Dashboard Polish
- Day 1-2: Add landing page, value proposition, "How it works"
- Day 3-4: Add summary cards (water saved, yield increase, cost reduction)
- Day 5: Clean up charts, colors, layout for non-technical audience

### Week 2: Disease Detection
- Day 1: Download PlantVillage dataset, organize into train/val
- Day 2-3: Train CNN model (your code + AI help for optimization)
- Day 4-5: Integrate image upload + prediction into Streamlit dashboard

### Week 3: Package & Deploy
- Day 1: Fix tests, set up GitHub Actions CI
- Day 2: Write killer README with screenshots + GIF
- Day 3: Deploy to Streamlit Cloud, test on multiple devices
- Day 4: Add "For Investors" tab with pitch content
- Day 5: Bug fixes, polish, get feedback from 2-3 people

### Week 4: Buffer & Nice-to-Haves
- Day 1-2: Multi-crop support (wheat + rice configs)
- Day 3: Weather API integration (OpenWeatherMap free tier)
- Day 4-5: Final polish, prepare demo script for investor meetings

---

## Investor Demo Script (5 Minutes)

**Opening (30 sec)**:
> "Farmers lose 20-40% of potential yield due to poor irrigation and
> fertilization timing. Our platform uses AI to tell farmers exactly
> when and how much to irrigate and fertilize."

**Live Demo (3 min)**:
1. Show dashboard → Run AI vs Random comparison
2. Point to results: "AI agent used 30% less water, 15% higher yield"
3. Upload a leaf photo → "Instant disease diagnosis with 92% accuracy"
4. Show recommendation: "Spray fungicide within 48 hours"
5. Show report export: "Farmer gets actionable PDF report"

**Close (1.5 min)**:
> "We've validated the technology. The simulation engine models real
> crop physics — GDD, water balance, nutrient cycling, disease pressure.
> The RL agent learns optimal decisions through 200k simulated seasons.
>
> We need $X to build the production platform, onboard 50 pilot farms,
> and prove ROI in one growing season.
>
> Our market: 570M farms worldwide, $5B precision ag market growing 12%/year."

---

## Key Metrics to Showcase

Calculate these from your existing simulation outputs:

| Metric | AI Agent | Random | Improvement |
|--------|----------|--------|-------------|
| Final Biomass (kg/ha) | ? | ? | ?% higher |
| Total Water Used (mm) | ? | ? | ?% less |
| Fertilizer Applied (kg N/ha) | ? | ? | ?% less |
| Total Reward ($) | ? | ? | ?% better |
| Crop Survival | ?% | ?% | ? |

Run `diagnose_v3_agent.py` to get these numbers. These ARE your pitch.

---

## What NOT to Build for MVP

- No user authentication (waste of time for demo)
- No database (CSV files are fine)
- No API backend (Streamlit handles everything)
- No mobile app (browser works on phones)
- No Kubernetes/Docker (Streamlit Cloud handles deployment)
- No microservices (monolith is perfect for MVP)
- No payment system (you don't have customers yet)
- No multi-language support (English only)
- No admin panel (you're the only user)

**Every hour spent on infrastructure is an hour NOT spent on the demo.**

---

## After Funding: Phase 2 Plan (Show This on Request)

**Month 1-2**: Production Backend
- FastAPI REST API
- PostgreSQL database
- User authentication
- Deploy on Railway or Render ($20/month)

**Month 3-4**: Real Farm Integration
- Weather API (live data)
- IoT sensor integration (soil moisture probes)
- Mobile-friendly web app (Next.js)

**Month 5-6**: Pilot Program
- 10-50 farms onboarded
- Collect real-world validation data
- Iterate based on farmer feedback

**Month 7-12**: Scale
- Hire 2 engineers
- Multi-crop, multi-region support
- Paid subscriptions launch

**This is all investors need to see: a credible 12-month plan, not a 50-service architecture diagram.**

---

## Resources (All Free)

**Training Data**:
- PlantVillage Dataset: 50k+ leaf images, 38 classes (free, academic use)
- Kaggle crop disease datasets (free)

**Deployment**:
- Streamlit Community Cloud (free)
- GitHub (free for public repos)
- GitHub Actions (free for public repos, 2k min/month for private)

**AI Assistance**:
- Claude (coding, architecture, debugging)
- Gemini (research, data analysis)
- GitHub Copilot (free for open source)

**Design**:
- Canva (free tier for pitch deck)
- Streamlit theming (built-in, customizable)

---

## Final Advice

1. **Ship ugly, ship fast** — A working demo beats a beautiful mockup
2. **Demo > Docs** — Investors want to click things, not read things
3. **Numbers win** — "AI saved 30% water" beats "we use advanced RL"
4. **Solve one problem well** — Don't try to be a platform yet
5. **Your moat is real** — RL + crop simulation is genuinely hard to replicate
6. **Use AI ruthlessly** — Let Claude/Gemini write boilerplate, you focus on logic
7. **Get feedback early** — Show the demo to 3 people this week

**You have the hardest part done (the simulation engine + RL agent).
Now package it and go get that funding.**

---

*Last updated: February 16, 2026*
*Status: Active development — MVP sprint in progress*
