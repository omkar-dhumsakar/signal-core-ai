# Signal Core AI

**Open-source Reinforcement Learning engine for enterprise supply chain optimization.**

Signal Core AI is an adaptive inventory intelligence layer that sits on top of traditional ERP systems (SAP, Oracle), replacing static min/max reorder thresholds with dynamic Q-Learning and Deep Q-Network (DQN) agents. It processes live POS webhooks, predicts stockouts before they happen, automates spoilage mitigation via FEFO tracking, and rebalances inventory across a multi-echelon hub-and-spoke network.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## Architecture

```
Signal Core AI/
├── SignalCoreAI/              # Core RL Engine
│   ├── scm_engine.py          # Tabular Q-Learning Agent + Stochastic Simulator
│   ├── dqn_engine.py          # Deep Q-Network (PyTorch) for 40K+ SKU scaling
│   └── data_utils.py          # Demand signal generation & SKU profile loader
├── backend/                   # FastAPI REST API
│   ├── main.py                # API endpoints + async EDA webhooks
│   ├── models.py              # Pydantic request/response schemas
│   ├── rl_bridge.py           # Bridges RL agents → mobile-friendly directives
│   ├── data_utils.py          # PostgreSQL/SQLite database layer
│   ├── kafka_gateway.py       # Kafka event stream consumer (mock/live)
│   └── .env.example           # Environment configuration template
├── storeops/                  # Flutter Mobile App (Android/iOS/Web)
│   └── lib/
│       ├── models/            # Directive, PurchaseOrder, InventoryItem
│       ├── services/          # API client + offline sqflite cache
│       ├── providers/         # State management (ChangeNotifier)
│       ├── screens/           # Home, Dashboard, Inventory Audit, PO Summary
│       └── widgets/           # DirectiveCard, ConfidenceGauge, MonsoonBanner
├── k8s/                       # Kubernetes deployment manifests
├── Dockerfile                 # Production container image
└── docker-compose.yaml        # Local dev stack
```

## Quick Start

### 0. 🐳 Enterprise Docker Stack (Recommended)
You can launch the entire ecosystem (FastAPI, Redis, Kafka, Zookeeper) with one command:
```bash
docker-compose up --build
```
The API will be available at `http://localhost:8002`.

---

### 1. Backend (FastAPI - Manual Setup)

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure database (PostgreSQL or SQLite fallback)
cp .env.example .env
# Edit .env with your DATABASE_URL (or leave as "sqlite" for local dev)

# Start the server
python main.py
```

The API starts at `http://localhost:8002`. Swagger docs at `/docs`.

### 2. Flutter App (StoreOps)

```bash
cd storeops
flutter pub get
flutter run -d chrome    # Web
flutter run              # Android/iOS emulator
```

> The app connects to `http://localhost:8002` (web) or `http://10.0.2.2:8002` (Android emulator).

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/directives` | Fetch RL-generated inventory directives |
| GET | `/api/v1/stores` | List all dark stores / hubs |
| GET | `/api/v1/products` | Full product catalog |
| GET | `/api/v1/categories` | Product category list |
| POST | `/api/v1/orders/confirm` | Confirm a restock order |
| POST | `/api/v1/orders/adjust` | Log a human adjustment (RLHF feedback) |
| POST | `/api/v1/orders/generate-pos` | Generate Purchase Orders |
| POST | `/api/v1/inventory/audit` | Manual stock count sync |
| POST | `/api/v1/webhooks/pos-sale` | Ingest POS sale events (async) |
| POST | `/api/v1/inventory/inbound-qc` | Inbound quality control (async) |
| POST | `/api/v1/webhooks/forward-demand` | Forward demand signal injection |
| GET | `/api/v1/monsoon/status` | Monsoon delay status |
| POST | `/api/v1/auth/login` | Store manager authentication |
| GET | `/health` | Agent health check |

## Core Features

### Adaptive RL Inventory Engine
- **Tabular Q-Learning** for fast training on small SKU sets
- **Deep Q-Network (DQN)** with SKU embeddings for scaling to 40,000+ SKUs
- **Vectorized NumPy inference** — processes entire catalog in milliseconds

### Multi-Echelon Hub-and-Spoke
- Central Distribution Center (CDC) → Dark Stores topology
- Cross-fleet rebalancing: auto-generates **Transfer Directives** between sibling stores
- Per-store RL agents with independent inventory state

### Spoilage Prevention (FEFO)
- Tracks `oldest_batch_hours` and `shelf_life_hours` per SKU
- Three-tier expiry risk classification (green → yellow → red)
- Auto-escalates priority when produce approaches expiration

### Demand Signal Forwarding
- Real-time POS webhook ingestion via async background tasks
- Forward-slotted demand forecasting from Dark Store signals
- Monsoon-aware lead time adjustment (June–September)

### Human-in-the-Loop (RLHF)
- Store managers approve or adjust AI recommendations
- Adjustment deltas logged for future reward shaping
- Confidence scoring per directive

### Enterprise Database
- **PostgreSQL** (via Neon.tech / Supabase / AWS RDS) for production
- **SQLite** automatic fallback for local development
- Dual-mode abstraction — zero code changes to switch

## RL Agent Details

### State Space
`(inventory_level, pipeline_stock, demand_signal)` — continuous input for DQN, discretized for tabular Q-Learning.

### Action Space
`[0, 2500, 5000, 7500, 10000, 15000]` → mapped to retail units `[0, 10, 25, 50, 75, 100]`

### Reward Function
Negative cost function: `-(stockout_penalty × promo_multiplier + holding_cost)`

### DQN Architecture
```
Input: [Inventory, Pipeline, Signal] + SKU Embedding(dim=16)
  → Linear(128) → ReLU
  → Linear(64)  → ReLU
  → Linear(num_actions)  # Q-values per action
```
- Experience Replay Buffer (20,000 transitions)
- Target Network with periodic sync
- Epsilon-greedy exploration with decay

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite` | PostgreSQL connection string or `sqlite` for local |

## Contributing

Contributions are welcome! We'd love help in these areas:

### 🧠 RL & ML
- [ ] PPO / SAC agent implementations
- [ ] Demand forecasting models (Prophet, LSTM, Transformer)
- [ ] Multi-agent coordination strategies
- [ ] Reward function experimentation

### 🔌 Integrations
- [x] SAP ERP connector (via Kafka)
- [x] Oracle ERP connector (via Kafka)
- [ ] Shopify / WooCommerce webhooks
- [ ] Tally / QuickBooks integration

### 🏗️ Infrastructure
- [x] Helm charts / Manifests for Kubernetes
- [ ] Terraform modules for AWS/GCP
- [x] Redis caching layer
- [x] Dockerization & `docker-compose` stack
- [ ] Horizontal scaling with Ray

### 📱 Mobile App
- [ ] iOS-specific optimizations
- [ ] Offline-first improvements
- [x] Dark mode enhancements (implemented via Dark TV background)
- [ ] Accessibility (a11y) improvements

### 📝 Documentation
- [ ] Tutorials and walkthroughs
- [ ] Architecture deep-dives
- [ ] Video demos
- [ ] Translations

### How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 — see [LICENSE](LICENSE) for details.

## Author

**Omkar Dhumaskar** — Founder, Signal Core AI
