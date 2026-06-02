# Contributing to Signal Core AI

Thank you for your interest in contributing! Signal Core AI is an open-source RL engine for supply chain optimization, and we welcome contributions from the community.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/signal-core-ai.git
   cd signal-core-ai
   ```
3. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Set up the development environment:**
   ```bash
   cd backend
   pip install -r requirements.txt
   cp .env.example .env
   python main.py  # Starts on http://localhost:8002
   ```

## Development Workflow

### Backend (Python / FastAPI)

```bash
cd backend

# Run the server
python main.py

# Run tests
pytest

# Format code
black . --line-length 100
ruff check .
```

### Mobile App (Flutter / Dart)

```bash
cd storeops

# Get dependencies
flutter pub get

# Run on web
flutter run -d chrome

# Analyze code
flutter analyze

# Format code
dart format .
```

### RL Engine (Python / PyTorch)

```bash
cd SignalCoreAI

# Train a tabular Q-Learning agent
python scm_engine.py

# Train a DQN agent
python train_dqn.py
```

## Code Style

- **Python**: [PEP 8](https://peps.python.org/pep-0008/) — use `black` for formatting and `ruff` for linting
- **Dart**: Follow the official [Dart style guide](https://dart.dev/effective-dart/style) — use `dart format`
- **Commits**: Use clear, descriptive commit messages. Prefer [Conventional Commits](https://www.conventionalcommits.org/) format:
  - `feat: add PPO agent implementation`
  - `fix: correct FEFO expiry calculation`
  - `docs: update API reference`

## Pull Request Process

1. Ensure your code passes all existing tests
2. Add tests for any new functionality
3. Update documentation if you're changing APIs or behavior
4. Keep PRs focused — one feature or fix per PR
5. Fill out the PR template with a clear description
6. Request a review from a maintainer

## Areas We Need Help With

We'd love contributions in these areas:

### 🧠 RL & ML
- [ ] PPO / SAC agent implementations
- [ ] Demand forecasting models (Prophet, LSTM, Transformer)
- [ ] Multi-agent coordination strategies
- [ ] Reward function experimentation

### 🔌 Integrations
- [ ] SAP ERP connector
- [ ] Oracle ERP connector
- [ ] Shopify / WooCommerce webhooks
- [ ] Tally / QuickBooks integration

### 🏗️ Infrastructure
- [ ] Helm charts for Kubernetes
- [ ] Terraform modules for AWS/GCP
- [ ] Redis caching layer
- [ ] Horizontal scaling with Ray

### 📱 Mobile App
- [ ] iOS-specific optimizations
- [ ] Offline-first improvements
- [ ] Dark mode enhancements
- [ ] Accessibility (a11y) improvements

### 📝 Documentation
- [ ] Tutorials and walkthroughs
- [ ] Architecture deep-dives
- [ ] Video demos
- [ ] Translations

## Reporting Bugs

Use [GitHub Issues](../../issues) with the **Bug Report** template. Include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, Flutter version)
- Logs or screenshots

## Suggesting Features

Use [GitHub Issues](../../issues) with the **Feature Request** template. Include:
- Problem description
- Proposed solution
- Alternative approaches considered

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

## Questions?

- Open a [GitHub Discussion](../../discussions)
- Tag your issue with `question`

Thank you for helping make supply chain management smarter! 🚀
