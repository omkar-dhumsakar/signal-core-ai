# BigBasket Strategy & Pitch Document

To successfully pitch Signal Core AI to BigBasket (Tata Enterprise), you must demonstrate a deep understanding of their supply chain complexity and how your RL (Reinforcement Learning) architecture outpaces their legacy ERP logic.

---

## 1. BigBasket's Current Operating Model

BigBasket operates a **Multi-Echelon, Multi-Format** supply chain that is vastly more complicated than standard Q-Commerce grids.

*   **Three-Tier Routing**: 
    1. **Farmer Connect / FMCG Warehouses**: Direct sourcing from farmers and national brands.
    2. **Central Distribution Centers (CDCs)**: Colossal warehouses on city outskirts that act as primary holding tanks.
    3. **Dark Stores / Local Hubs**: Local fulfillment centers deep inside urban zones.
*   **Three-Format Delivery**:
    1. **BB Slotted**: Next-day/Same-day large basket deliveries.
    2. **BB Daily**: Subscription-based early morning macro-logistics (milk/eggs).
    3. **BB Now**: 10-20 minute quick commerce drop-shipping.
*   **Current Tech Infrastructure**: They rely on massive traditional ERP systems (often SAP-backed or deeply entrenched custom monoliths) which use **static Min/Max thresholds** and traditional time-series forecasting (ARIMA/Prophet) rather than adaptive Reinforcement Learning.

---

## 2. Signal Core AI: The Breakdown

### Specific Advantages (Your Pitch Highlights)
1. **Adaptive Deep RL vs. Static Thresholds**: BigBasket’s current systems likely trigger orders when stock hits `X`. Signal Core AI uses Q-Learning to measure *velocity*, generating dynamic restock directives based on live POS webhooks, preventing stockouts during flash anomalies.
2. **Automated FEFO Price Mitigation**: Your engine tracks `oldest_batch_hours`. Instead of letting a CDC warehouse worker discover rotting perishables, the AI automatically bypasses the PO generator and pushes a **"Flash Sale"** markdown to the consumer app before the spoil date.
3. **Cross-Fleet Rebalancing**: BigBasket currently wastes money over-ordering from suppliers. Signal Core AI actively intercepts Purchase Orders and checks sibling Dark Stores for saturated surplus, generating internal **Transfer Directives** instead.

### Current Limitations (What BigBasket Will Ask About)
1. **ERP Integration Engine**: Signal Core AI currently runs on SQLite/Memory. BigBasket will need enterprise data connectors to sync with SAP/Oracle.
2. **Transportation Management (TMS)**: The AI generates POs and Replenishments, but does not currently optimize the physical truck loading or route mapping between the CDC and the Dark Stores.
3. **Vendor Bidding & Procurement**: Signal Core spits out a single PO to a designated supplier. BigBasket relies on a multi-vendor bidding matrix to get the lowest price daily for fresh produce.
4. **Extreme Scale Limits**: The current Q-Learning matrices are built for 500-1,000 SKUs. BigBasket carries **40,000+ SKUs** across hundreds of cities.

---

## 3. Comparison Table

| Capability | BigBasket Legacy ERP / Rules Engine | Signal Core AI |
| :--- | :--- | :--- |
| **Inventory Ordering** | Static Min/Max trigger thresholds | Dynamic Reinforcement Learning (Q-Learning) |
| **Spike Reaction Time** | Next-day batch processing | Instant (via `/api/v1/webhooks/pos-sale`) |
| **Spoilage / FEFO** | Manual inventory audits & ad-hoc discounts | Automated FEFO intercept & Flash Sale webhook |
| **Store Overstock** | Trapped capital, eventual expiration | Cross-Store automatic Fleet Rebalancing |
| **Forward Integration** | Deeply embedded into truck routing | Lacks native TMS/Logistics routing |
| **Data Architecture** | PostgreSQL / SAP massive data lakes | SQLite/Memory (Requires Migration) |

---

## 4. The 90-Day Enterprise Roadmap (Fixing the Limitations)

To secure the enterprise contract, present this 90-day roadmap proving you can adapt SignalCore AI to their scale.

### Phase 1: Enterprise Plumbing (Days 1–30)
**Goal:** Hook the AI engine into BigBasket's massive data lake.
*   **Engineering:** 
    *   Migrate SQLite to standard AWS RDS PostgreSQL.
    *   Build bi-directional Kafka event listeners to ingest BigBasket's master catalogue and live sales streams.
*   **Resources:** 1 Founder (Product/Integration) + AI Coding Assistant.
*   **Est. Budget:** ₹40,000 (AWS RDS & Kafka cluster pilot).

### Phase 2: Massive Scaling & Bidding Logic (Days 31–60)
**Goal:** Expand the RL engine to handle 40,000 SKUs and build multi-vendor routing.
*   **Engineering:** 
    *   Shift the basic Python `rl_bridge` to distributed Ray clusters or localized Numba compilations.
    *   Introduce a "Vendor Bidding Module" into the Purchase Order pipeline (letting the AI select from 3 local suppliers based on live price rather than a static connection).
*   **Resources:** 1 Founder + AI Coding Assistant.
*   **Est. Budget:** ₹85,000 (Reserved GPU instances & Redis clustering).

### Phase 3: Demand Signal Forwarding (Days 61–90)
**Goal:** Propagate local demand signals back up the supply chain.
*   **Engineering:** 
    *   Implement forward-slotted forecasting based on aggregated Dark Store RL signals.
    *   Route consolidated upstream demands to CDCs and suppliers dynamically.
*   **Resources:** 1 Founder + AI Coding Assistant.
*   **Est. Budget:** ₹25,000 (Standard API hosting & compute).

> [!IMPORTANT]
> **Total 90-Day Proposal**
> **Timeline:** 3 Months to full shadow-deployment in one BigBasket city.
> **Resource Ask:** 1 Core Founder + Automated AI Architect (Zero external headcount overhead).
> **Budget Estimate:** ~₹1,50,000 - ₹3,00,000 INR (Purely covers enterprise-grade AWS infrastructure blocks, zero payroll burn).
