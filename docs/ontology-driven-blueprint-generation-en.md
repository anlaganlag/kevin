# Ontology-Driven Blueprint Generation: Deep Analysis & Architecture Design

> **Date**: 2026-03-29
> **Context**: UPS / Logistics industry — BA Agent + business stakeholders co-create an Ontology, connected to an Executor for fully automated delivery
> **Status**: Strategic architecture document


---

## 1. The Big Picture: What You Are Building

```
┌──────────────────────────────────────────────────────────┐
│                    Knowledge Flywheel                     │
│                                                          │
│   Pre-built Knowledge Foundation                         │
│   (UPS API specs, logistics standards, integration       │
│    patterns)                                             │
│           +                                              │
│   Business Stakeholder Co-creation                       │
│   (Specific scenarios, constraints, system integration   │
│    details)                                              │
│           ↓                                              │
│   BA Agent → Ontology (UPS ↔ Customer integration map)  │
│           ↓                                              │
│   Blueprint Generator (Ontology → executable blueprint)  │
│           ↓                                              │
│   Executor (Blueprint → PR / deployment / documentation) │
│           ↓                                              │
│   Deliverables → Feedback → Ontology continuously        │
│   enriched                                               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

On the surface, this looks like an "AI writes code" system.

**In reality, it is a platform that turns enterprise integration knowledge into a structured asset — and then executes that knowledge automatically.**

---

## 2. Why This Is Exceptionally Valuable in Logistics

### 2.1 The Unique Complexity of Logistics Integration

Logistics is not "a system." It is a **multi-party collaboration network**:

```
eCommerce Platform ←→ UPS API ←→ UPS Internal Systems ←→ WMS ←→ Last-Mile Delivery ←→ Customer Systems
    │                                                                        │
    └── Every arrow is an integration point, and each one involves:          │
        - Data format requirements                                           │
        - Business rule constraints                                          │
        - Error handling specifications                                      │
        - SLA requirements                                                   │
        - Compliance mandates (customs, hazmat, cross-border)                │
        └────────────────────────────────────────────────────────────────────┘
```

**A seemingly simple request — "integrate with UPS Returns API" — involves:**

| Layer | Hidden Complexity |
|-------|-------------------|
| API Integration | UPS Returns API version, authentication method, rate limits |
| Business Rules | Return windows, per-category return policies, refund rules |
| Data Mapping | Customer SKU → UPS package type, customer address format → UPS address standard |
| Error Handling | Address validation failures, oversized packages, hazmat identification |
| Compliance | Cross-border return customs declarations, country-specific return regulations |
| Downstream Cascades | Return triggers inventory update → WMS → finance system refund |

**This knowledge is scattered across UPS documentation, account managers' heads, historical support tickets, and hard-won lessons from past failures.**

No one has ever systematically structured it. That is exactly what BA Agent + Ontology does.

### 2.2 Market Gap

| Existing Tool | What It Can Do | What It Cannot Do |
|---------------|----------------|-------------------|
| UPS Developer Kit | Provides API documentation | Does not know the customer's system landscape |
| MuleSoft / Dell Boomi | Integration platform with drag-and-drop connectors | Does not know UPS business rules |
| Devin / Cursor | Can write code | Does not know UPS API edge cases |
| Consulting Firms | Produces solution documents | Cannot execute automatically |

**Your position: the only system that simultaneously possesses frontline UPS integration knowledge AND automated execution capability.**

---

## 3. Ontology Architecture: Three Layers + Two Perspectives

### 3.1 Three-Layer Model

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Business Concept Layer (What)                 │
│                                                         │
│  [Package] --contains--> [Product]                      │
│  [Product] --has--> [Hazmat Classification]             │
│  [Return] --triggers--> [Refund]                        │
│  [Return] --requires--> [Return Label]                  │
│  [Customer] --subscribes--> [Service Tier:              │
│                              Ground/Express/Freight]    │
│                                                         │
│  Each node carries:                                     │
│    - Business rules (30-day return window)              │
│    - Data constraints (max weight 150 lbs)              │
│    - Compliance markers (cross-border requires customs  │
│      declaration)                                       │
└────────────────────┬────────────────────────────────────┘
                     │ maps_to
┌────────────────────▼────────────────────────────────────┐
│  Layer 2: System Layer (Where)                          │
│                                                         │
│  UPS Side:                                              │
│    [Returns API v2] --endpoint--> /returns/labels       │
│    [Tracking API] --webhook--> status_update            │
│    [Address Validation API] --validates--> [Address]    │
│    [Billing System] --calculates--> [Shipping Cost]     │
│                                                         │
│  Customer Side:                                         │
│    [eCommerce Platform] --tech: Shopify / custom-built  │
│    [WMS] --tech: Manhattan / custom-built               │
│    [ERP] --tech: SAP / Oracle                           │
│                                                         │
│  Integration Points:                                    │
│    [eCommerce Platform] --calls--> [Returns API v2]     │
│    [Returns API v2] --notifies--> [WMS]                 │
│    [WMS] --updates--> [ERP]                             │
│                                                         │
│  Each system node carries:                              │
│    - Tech stack (Java / Python / SAP ABAP)              │
│    - Repository URL (github.com/org/repo)               │
│    - Owner (team / contact)                             │
│    - Constraints (change approval requirements,         │
│      deployment windows)                                │
│    - API spec version                                   │
└────────────────────┬────────────────────────────────────┘
                     │ governed_by
┌────────────────────▼────────────────────────────────────┐
│  Layer 3: Process Layer (How)                           │
│                                                         │
│  Standard Integration Process:                          │
│    Requirements Analysis → API Integration → Data       │
│    Mapping → Integration Testing → UAT → Security       │
│    Review → Canary Rollout → Monitoring                 │
│                                                         │
│  Risk-based Branching:                                  │
│    Low  (config change): Dev → Test → Deploy            │
│    Med  (API integration): Dev → Integration Test →     │
│                            UAT → Deploy                 │
│    High (core logic change): Full process + Security    │
│                              Review + Dual Approval     │
│                                                         │
│  Organization-specific Processes:                       │
│    UPS: Billing system changes → require Finance        │
│         approval                                        │
│    UPS: Cross-border scope → require Compliance review  │
│    Customer: may have their own change management       │
│              process                                    │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Two Perspectives

The same ontology, viewed from two angles:

**UPS Perspective** (looking inward):

```
What APIs do I have → What are the specs for each → What are the business rules →
What are the usage constraints → Known errors and handling patterns
```

**Customer Perspective** (looking outward):

```
What are my systems → Which UPS capabilities do I need →
How do I map my data → What are my constraints (deployment windows, tech stack, approval workflows)
```

**The core value of the Ontology is connecting these two perspectives:**

```
Customer's [Shopify Order]
    → maps to UPS [Shipment Request]
    → requires calling [Shipping API v3]
    → must first call [Address Validation API]
    → if cross-border → also requires [Customs API]
    → Customer's Shopify stack → use Node.js SDK
    → UPS side requires OAuth2 authentication
    → This customer is on Express tier → SLA constraints apply
```

**This end-to-end chain does not exist in UPS documentation. The customer cannot piece it together either. Only your ontology contains the complete mapping.**

---

## 4. From Ontology to Blueprint: The Automated Generation Engine

### 4.1 Generation Process

```
Input:
  - User requirement (natural language): "Our Shopify store needs UPS returns integration"
  - Ontology (knowledge graph + documentation)
  - Pre-built Blueprint pattern library

Processing:
  Step 1: Entity Recognition & Linking
  Step 2: Impact Scope Analysis
  Step 3: Constraint Collection
  Step 4: Process Matching
  Step 5: Blueprint Assembly

Output:
  - Complete Blueprint YAML
  - Human-readable execution plan
```

### 4.2 Step 1: Entity Recognition & Linking

Claude + Ontology working in tandem:

```
User says: "Our Shopify store needs UPS returns integration"

Entity Recognition:
  "Shopify" → System Layer: [eCommerce Platform, tech=Shopify]
  "UPS returns" → Business Concept Layer: [Return]
                → System Layer: [Returns API v2]

Link Expansion (automatic graph traversal from ontology):
  [Return] --requires--> [Return Label] --generated_by--> [Returns API v2]
  [Return] --triggers--> [Refund] --processed_by--> [Billing System]
  [Return] --updates--> [Inventory] --lives_in--> [WMS]
  [Returns API v2] --requires--> [Address Validation API] (prerequisite dependency)
  [Shopify] --connects_via--> [Webhook] (integration pattern)
```

### 4.3 Step 2: Impact Scope Analysis

Automatically derived from link expansion:

```
Direct Impact:
  ✦ Shopify side: New return initiation flow + webhook receiver required
  ✦ UPS Returns API: Label generation + status tracking integration needed

Indirect Impact (automatically discovered via ontology relationships):
  ✦ Address Validation: Return address must be validated (Returns API prerequisite)
  ✦ WMS: Return receipt requires warehouse system notification
  ✦ Billing: Refund must trigger the billing system

Risk Flags (automatically extracted from ontology constraint properties):
  ⚠ Involves Billing System → requires Finance approval
  ⚠ If cross-border returns → requires Compliance review
  ⚠ Returns API v2 rate limit: 100 req/min
```

### 4.4 Step 3: Constraint Collection

Automatically aggregated from all ontology layers:

```yaml
constraints:
  business_rules:
    - return_window: 30 days
    - non_returnable_categories: [hazmat, custom_made]
    - return_shipping_policy: seller_pays (Express), buyer_pays (Ground)

  technical_constraints:
    - Shopify: webhook must return 200 within 5 seconds
    - Returns API: OAuth2 authentication, sandbox environment available
    - rate_limit: 100 req/min (queuing mechanism required)

  compliance:
    - cross_border_returns: customs declaration (CN22/CN23)
    - PII: return address contains personal data, requires redacted storage

  process_constraints:
    - involves_billing: Finance approval required (approver_1 / approver_2)
    - core_system_change: dual code review required
    - deployment_window: Tuesday/Thursday 10:00-14:00 UTC
```

### 4.5 Step 4: Process Matching

Based on impact scope and constraints, match from the Process Layer:

```
Involves Billing System (core) → Risk Level: HIGH
High-risk process:
  Requirements Analysis → API Integration → Data Mapping → Integration Testing →
  UAT → Security Review → Finance Approval → Canary Rollout → Monitoring
```

### 4.6 Step 5: Blueprint Assembly

```yaml
blueprint:
  metadata:
    generated_from: ontology
    requirement: "Shopify store UPS returns integration"
    risk_level: high
    affected_systems: ["Shopify", "Returns API v2", "Address Validation", "WMS", "Billing"]
    constraints_applied: 12
    estimated_steps: 8

  blocks:
    - block_id: B1
      name: "Requirements Analysis & Data Mapping"
      runner: claude_cli
      prompt_template: |
        Analyze the Shopify Returns → UPS Returns data mapping:

        Shopify return data structure:
        {{shopify_return_schema}}      # Injected from ontology customer system layer

        UPS Returns API request format:
        {{ups_returns_api_schema}}     # Injected from ontology UPS system layer

        Business rules:
        {{business_rules}}             # Injected from ontology business concept layer

        Output: .kevin/data-mapping.md

    - block_id: B2
      name: "Address Validation Integration"    # ← Prerequisite discovered by ontology
      dependencies: [B1]
      runner: claude_cli
      context:
        repo: "{{customer_repo}}"    # From ontology customer system node
        tech: "Node.js"             # From ontology tech stack property
        api_docs: "{{address_validation_api_docs}}"  # Injected from ontology
      prompt_template: |
        Implement UPS Address Validation API integration:
        - Use {{tech}} SDK
        - Return address must be validated before creating return label
        - Handle validation failure: prompt user to correct address
        - Rate limit: {{rate_limit}}

    - block_id: B3
      name: "Returns API Integration"
      dependencies: [B2]            # Address validation is a prerequisite
      runner: claude_cli
      context:
        repo: "{{customer_repo}}"
        api_version: "v2"
        auth: "OAuth2"              # From ontology
      prompt_template: |
        Implement UPS Returns API v2 integration:
        - Create return label (POST /returns/labels)
        - Receive status updates (Webhook)
        - Business rules: {{return_business_rules}}
        - Error handling: {{known_error_patterns}}  # Historical experience injected from ontology
        - PII redaction: redact return address before storage

    - block_id: B4
      name: "WMS Inventory Sync"          # ← Indirect impact discovered by ontology
      dependencies: [B3]
      runner: claude_cli
      context:
        repo: "{{wms_repo}}"
        tech: "{{wms_tech}}"
      prompt_template: |
        Notify WMS on return receipt:
        - Trigger condition: UPS status = "delivered_to_warehouse"
        - Payload: SKU, quantity, return reason
        - Interface: {{wms_inbound_api}}  # From ontology

    - block_id: B5
      name: "Integration Testing"
      dependencies: [B3, B4]
      runner: claude_cli
      prompt_template: |
        Write end-to-end integration tests:
        - Shopify initiates return → Address validation → Create label → Status update → WMS receipt
        - Use UPS sandbox environment: {{sandbox_config}}
        - Test failure scenarios: invalid address, oversized package, cross-border

    - block_id: B6
      name: "Security Review"              # ← Required by high-risk process
      dependencies: [B5]
      runner: claude_cli
      prompt_template: |
        Security review checklist:
        - OAuth2 token secure storage (no hardcoding)
        - PII field handling (address redaction)
        - API key rotation strategy
        - Webhook signature verification
        - Rate limit compliance

    - block_id: B7
      name: "Finance Approval Request"     # ← Ontology: Billing involvement → requires Finance approval
      dependencies: [B5]
      runner: api_call
      runner_config:
        method: POST
        url: "{{approval_system_url}}"
        body:
          type: "billing_change_approval"
          description: "Returns feature involves Billing System integration"
          approvers: ["{{finance_approver_1}}", "{{finance_approver_2}}"]

    - block_id: B8
      name: "Create PR & Deploy"
      dependencies: [B6, B7]       # Both security review + finance approval must pass
      runner: shell
      runner_config:
        command: |
          # Deployment window check (from ontology: Tue/Thu 10:00-14:00 UTC)
          # Canary strategy: 10% → 50% → 100%
          gh pr create --title "feat: UPS Returns integration for {{customer_name}}"
```

**The critical point: every line of this Blueprint is derived from the ontology — it is not a generic template.** B2 (Address Validation) exists because the ontology knows Returns API depends on Address Validation. B4 (WMS Sync) exists because the ontology knows returns affect inventory. B7 (Finance Approval) exists because the ontology knows Billing involvement requires Finance sign-off.

---

## 5. Hidden Insights

### 5.1 The Ontology Is the Product — Not the Executor

```
Executor = Engine (anyone can build one)
Ontology = Map (only someone who has walked the terrain can draw it)
Blueprint = Navigation Route (map + destination → auto-generated)
```

Devin has an engine but no map. It can write code, but it does not know what error code UPS Returns API v2 should return when address validation fails. It does not know who must approve changes that touch Billing. It does not know the deployment window is Tuesday and Thursday.

**You are not selling "AI that writes code." You are selling "UPS integration knowledge + automated execution."**

### 5.2 The BA Agent Is the Entry Point of the Data Flywheel

```
Customer 1 integrates returns → ontology gains returns knowledge
Customer 2 integrates returns → ontology already has returns knowledge → faster delivery →
                                plus Customer 2's unique constraints are captured
Customer 3 integrates returns → Blueprint is nearly auto-generated →
                                minutes-level delivery (vs. weeks previously)
```

**Every customer engagement enriches the ontology.** By the time the 10th customer integrates returns, the ontology already contains the pitfalls from 9 previous customers, every edge case, and every data mapping variant.

This is a network effect. **But not a user-count network effect — a knowledge-density network effect.**

### 5.3 Hidden Pricing Power

Traditional model:
```
Consulting firm quote: "UPS returns integration → 2 weeks requirements +
4 weeks development + 2 weeks testing = $150K"
```

Your model:
```
Ontology already has returns knowledge → Blueprint auto-generated →
Executor runs → PR in 2 hours → human review → ship

Cost: a few dollars in API calls
Price: $50K (still 1/3 of a consulting firm)
Margin: >95%
```

**Once knowledge enters the ontology, marginal cost approaches zero. But each delivery still provides the full value of a complete integration solution.**

### 5.4 The Ontology Is a Natural Compliance Vehicle

Logistics compliance requirements — customs, hazardous materials, GDPR, cross-border data — are extraordinarily complex.

```
Auditor asks: "Why doesn't the returns process include a customs declaration step?"

Answer (traditional): "Uh... the developer may have missed it?"

Answer (Ontology-driven):
  "Because the [Return] node in the ontology has scope=domestic,
   which does not trigger the [Cross-Border] marker. Therefore,
   the Process Layer did not match the customs declaration step.
   For cross-border returns, the ontology would automatically
   activate compliance constraints, and the Blueprint would
   include CN22/CN23 declaration steps.
   Here is the Blueprint generation log: [link]"
```

**Every decision is traceable to a specific node and rule in the ontology.** This is not a bolted-on "audit feature" — it is an inherent property of ontology-driven architecture.

### 5.5 Why Competitors Cannot Replicate This

To replicate your system, a competitor would need:

| Requirement | Difficulty | Timeline |
|-------------|-----------|----------|
| Build an Executor | Easy | 1 week |
| Build a BA Agent | Moderate | 1 month |
| Acquire UPS API integration knowledge | Hard — requires hands-on integration experience | 6 months |
| Accumulate edge cases and hard-won lessons | Very hard — requires real customer projects | 1-2 years |
| Build a comprehensive UPS ↔ Customer ontology | Nearly impossible — requires extensive frontline project work | 3+ years |

**Time is the ultimate moat. Every additional customer engagement adds another layer to the ontology, widening the gap competitors must close.**

### 5.6 The Blueprint Pattern Library: A Hidden Second Product

As the ontology matures, a pattern emerges:

```
Returns Integration Blueprint    (validated 9 times, 3 variants)
Shipping Integration Blueprint   (validated 15 times, 5 variants)
Tracking Integration Blueprint   (validated 20 times, 2 variants)
Billing Integration Blueprint    (validated 7 times, 4 variants)
```

These battle-tested Blueprint patterns are themselves a product:
- Licensable to UPS partner ecosystem
- Available to third-party integrators
- Positionable as UPS's officially recommended integration methodology

**The shift: from "doing integrations for customers" to "defining how integrations should be done."** This is the leap from service provider to standard-setter.

### 5.7 Horizontal Expansion to Other Carriers

```
UPS Ontology (built):
  Returns, Shipping, Tracking, Billing, Warehousing, Cross-border...

FedEx Ontology (to build):
  Returns, Shipping, Tracking, Billing, Warehousing, Cross-border...
  └── 70% of the Business Concept Layer is reusable (industry-universal)
  └── 30% requires rebuilding (FedEx-specific APIs and rules)

DHL Ontology (to build):
  └── Same 70% reuse
```

**The Business Concept Layer is industry-universal.** The business logic of "returns" is largely the same at UPS and FedEx. The differences live in the System Layer (different APIs) and the Process Layer (different approval workflows).

This means the cost of expanding to a second carrier is significantly lower than the first.

### 5.8 The Most Undervalued Capability: Error Prevention

The ontology's greatest value is not "auto-generating Blueprints." It is **knowing what should not be done and what is likely to go wrong.**

```
User says: "Just sync Shopify order data directly to UPS"

AI without ontology: "Sure, let me write a sync script..."

AI with ontology:
  "⚠ Warning: the ontology indicates that Shopify order data contains PII
   (customer addresses). Direct sync violates GDPR. Historical records
   show Customer X was flagged during audit in 2025-Q3 for a similar
   operation.

   Recommendation: route through the data redaction layer first (the
   ontology contains a validated standard approach), then sync to UPS.
   Shall I generate a Blueprint using this approach?"
```

**The ontology does not just know "how to do things" — it knows "when you should not do things that way."** This preventive knowledge is the most valuable capability of an experienced consultant, now encoded into the system.

---

## 6. Ontology Schema Design

### 6.1 Node Types

```yaml
node_types:
  # Layer 1: Business Concepts
  business_concept:
    properties:
      name: string
      description: string
      domain: enum [shipping, returns, tracking, billing, customs, warehousing]
      rules: list[BusinessRule]
      compliance_tags: list[string]  # ["GDPR", "customs", "hazmat"]
      data_schema: object            # Standard data structure for this concept

  # Layer 2: Systems
  system:
    properties:
      name: string
      owner: string                  # UPS | customer
      tech_stack: string             # "Java/Spring", "Node.js", "SAP ABAP"
      repo: string                   # Git repo URL (if applicable)
      api_specs: list[APISpec]       # OpenAPI/Swagger references
      constraints: list[Constraint]  # Change approval, deployment windows, SLA
      environment: object            # sandbox/staging/prod URLs

  # Layer 3: Processes
  process:
    properties:
      name: string
      trigger_conditions: list[string]  # What conditions trigger this process
      steps: list[ProcessStep]
      risk_level: enum [low, medium, high, critical]
      required_approvals: list[string]
```

### 6.2 Relationship Types

```yaml
relationship_types:
  # Business Concept ↔ Business Concept
  triggers:       # [Return] --triggers--> [Refund]
  requires:       # [Return] --requires--> [Return Label]
  contains:       # [Package] --contains--> [Product]

  # Business Concept ↔ System
  implemented_by: # [Return] --implemented_by--> [Returns API v2]
  data_lives_in:  # [Customer Data] --data_lives_in--> [CRM]

  # System ↔ System
  calls:          # [eCommerce Platform] --calls--> [Returns API]
  depends_on:     # [Returns API] --depends_on--> [Address Validation API]
  syncs_with:     # [WMS] --syncs_with--> [ERP]

  # System ↔ Process
  governed_by:    # [Billing System] --governed_by--> [Finance Approval Process]

  # Business Concept → Data Mapping
  maps_to:        # [Shopify Order] --maps_to--> [UPS Shipment Request]
    properties:
      field_mapping: object  # {"shopify.line_items" → "ups.packages"}
      transformation: string # Transformation logic description
```

### 6.3 Knowledge Accumulation Structure

```yaml
# Attached to any node or relationship
experience:
  - type: "known_issue"
    description: "Returns API v2 returns 500 instead of 400 when package weight exceeds 70 lbs"
    discovered_at: "2025-11-15"
    workaround: "Client-side weight pre-validation; route packages over 70 lbs to Freight Returns"
    affected_customers: 3

  - type: "best_practice"
    description: "Process Shopify webhooks via async queue to avoid 5-second timeout"
    confidence: high  # Validated 5+ times

  - type: "gotcha"
    description: "Cross-border return label generation requires calling Customs API first to obtain declaration ID"
    not_in_official_docs: true  # Not documented in official API docs
```

**Knowledge marked `not_in_official_docs: true` is the most valuable.** This is the kind of insight you only gain by encountering the problem firsthand.

---

## 7. Blueprint Generator Architecture

### 7.1 Generation Pipeline

```
Input:
  requirement (natural language)
  ontology (knowledge graph + documentation)
  blueprint_patterns (validated pattern library)

┌────────────────────────────────────────┐
│  Step 1: Entity Recognition & Linking  │
│  Claude + Ontology                     │
│  "Shopify returns" →                   │
│    Business: [Return, Return Label,    │
│              Refund]                   │
│    Systems: [Shopify, Returns API,     │
│             WMS]                       │
│    Compliance: [PII, Cross-border?]    │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 2: Graph Traversal               │
│  Starting from identified nodes,       │
│  traverse relationships                │
│  Discovered: Address Validation        │
│              (prerequisite dependency) │
│  Discovered: Billing (refund trigger)  │
│  Discovered: 3 known_issues            │
│  Discovered: 2 best_practices          │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 3: Constraint Aggregation        │
│  Collect constraints from all involved │
│  nodes                                 │
│  Business rules: 7                     │
│  Technical constraints: 4              │
│  Compliance requirements: 2            │
│  Process requirements: HIGH risk →     │
│                        full process    │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 4: Pattern Matching              │
│  Existing "returns integration"        │
│  pattern → 3 variants                  │
│  Best match: Variant B (Shopify +      │
│              domestic)                 │
│  Delta: customer has no WMS →          │
│         skip B4 block                  │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 5: Blueprint Assembly            │
│  Claude assembles final Blueprint:     │
│  - Based on matched pattern            │
│  - Inject all constraints              │
│  - Inject known_issues into prompts    │
│  - Inject field_mapping into data      │
│    mapping steps                       │
│  - Add approval steps per risk level   │
│  Output: Blueprint YAML                │
└────────────────────────────────────────┘
```

### 7.2 Claude's Role

Claude is not "writing a Blueprint." It is **querying the ontology and assembling existing knowledge**:

```
What Claude does:     Understand requirement → Locate entities in ontology →
                      Traverse relationships → Assemble Blueprint
What Claude does NOT: Guess UPS API behavior → Fabricate business rules →
                      Assume system architecture

Knowledge source:   Ontology (deterministic)
Reasoning source:   Claude (flexible)
Assembly output:    Blueprint (executable)
```

**This is why your approach outperforms Devin:** Devin relies 100% on Claude's reasoning. Your approach draws 80% from the ontology's deterministic knowledge and only 20% from Claude's reasoning. Higher determinism yields more consistent quality.

---

## 8. Implementation Roadmap

| Phase | Objective | Deliverable | Value |
|-------|-----------|-------------|-------|
| **Phase 0** (complete) | Executor as a Service | /execute, /status, /callback | Execution capability |
| **Phase 1** | Ontology Schema Standardization | Three-layer nodes + relationship types + knowledge accumulation structure | BA Agent has a standardized output format |
| **Phase 2** | Blueprint Generator MVP | Requirement + Ontology → Blueprint YAML | Closed loop: knowledge → execution |
| **Phase 3** | Teams Integration | Teams message → BA Agent → Blueprint → Executor → Teams reply | End-user accessible |
| **Phase 4** | Knowledge Flywheel | Execution results feed back → ontology auto-enrichment | Continuous improvement |

### Phase 2 MVP Implementation

The Blueprint Generator is fundamentally a single function:

```python
def generate_blueprint(
    requirement: str,           # User requirement
    ontology: OntologyGraph,    # Knowledge graph
    patterns: list[Blueprint],  # Existing Blueprint patterns
) -> Blueprint:

    # 1. Claude: Extract ontology entities from requirement
    entities = claude_extract_entities(requirement, ontology.node_names())

    # 2. Graph traversal: Expand impact scope
    scope = ontology.traverse(entities, max_depth=3)

    # 3. Collect constraints
    constraints = ontology.collect_constraints(scope.nodes)

    # 4. Match existing patterns
    pattern = find_best_pattern(patterns, scope)

    # 5. Claude: Assemble Blueprint
    blueprint = claude_assemble_blueprint(
        requirement=requirement,
        scope=scope,
        constraints=constraints,
        base_pattern=pattern,
        known_issues=ontology.get_experiences(scope.nodes),
    )

    return blueprint
```

**This function can live inside the BA Agent, the Teams Bot, or as a standalone Edge Function.** Where it runs is a deployment decision, not an architectural one.

---

## 9. Long-Term Vision

```
Year 1:
  UPS returns/shipping/tracking ontology → auto-generated Blueprints → delivery

Year 2:
  Complete UPS ontology → Blueprint pattern library →
  New customer onboarding drops from weeks to hours

Year 3:
  Expand to FedEx, DHL → logistics industry ontology standard →
  "The Stripe of logistics integration" (one-line integration with any carrier)

Year 5:
  Expand into supply chain → end-to-end supply chain coverage →
  Ontology becomes industry knowledge infrastructure
```

**The starting point is UPS returns integration. The destination is a knowledge operating system for the logistics industry.**
