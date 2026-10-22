# WarrantyMind — AI-Powered Pixel Warranty & Service Management

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-FF6B6B?style=for-the-badge)
![MCP](https://img.shields.io/badge/MCP-Multi--Context_Protocol-6C63FF?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

> **WarrantyMind** is a full-stack, agentic AI warranty-processing platform for Google Pixel devices. It orchestrates a multi-agent pipeline — vision inspection, web research, RAG policy retrieval, LLM diagnostic reasoning, and human-in-the-loop review — through a FastAPI backend and a rich single-page frontend.

---

---

## Table of Contents

1. [About the Project](#about-the-project)
   - [Executive Summary](#executive-summary)
   - [The Problem We Solve](#the-problem-we-solve)
   - [The WarrantyMind Solution](#the-warrantymind-solution)
   - [Core Design Principles & Philosophy](#core-design-principles--philosophy)
   - [Stakeholder Personas & Value Matrix](#stakeholder-personas--value-matrix)
2. [Overview & Key Features](#overview--key-features)
3. [Architecture Overview](#architecture-overview)
4. [System Flowchart — End-to-End Case Lifecycle](#system-flowchart--end-to-end-case-lifecycle)
5. [Component Deep-Dive](#component-deep-dive)
6. [MCP Architecture Deep-Dive](#mcp-architecture-deep-dive)
7. [Data Flow Diagrams](#data-flow-diagrams)
8. [Case Workflow States](#case-workflow-states)
9. [Role-Based Access Control](#role-based-access-control)
10. [Environment Configuration](#environment-configuration)
11. [Installation & Quick Start](#installation--quick-start)
12. [Running with Docker](#running-with-docker)
13. [API Reference](#api-reference)
14. [Demo Credentials](#demo-credentials)
15. [Project Structure](#project-structure)
16. [Testing](#testing)
17. [Safety & Guardrails](#safety--guardrails)

---

## About the Project

### Executive Summary

**WarrantyMind** is an advanced, production-grade agentic AI warranty resolution platform engineered specifically for consumer electronics, with first-class specialization for **Google Pixel devices** (Pixel 6 through Pixel 9 Pro Fold). 

Modern device warranty processing is notoriously broken: customers wait weeks navigating disjointed support portals, service centers battle inconsistent hardware evaluations, and manufacturers hemorrhage billions through warranty fraud or mishandled adjudications. 

WarrantyMind transforms this paradigm by deploying a synchronized multi-agent cognitive architecture adhering to the **Model Context Protocol (MCP)**. It automates device damage verification, invoice validation, policy retrieval, OEM advisory research, and technician slot reservations—all while enforcing strict **Human-in-the-Loop (HITL)** governance so that no binding financial or warranty claim decision is made without authorized human oversight.

---

### The Problem We Solve

Consumer electronics warranty operations face four acute systemic bottlenecks:

1. **Subjective & Error-Prone Damage Assessment**:
   Customers upload blurry, uncalibrated photos. Traditional claim workflows rely on overworked Tier-1 support reps who cannot reliably distinguish between harmless cosmetic scuffs, deep hairline screen fractures, liquid contact indicator (LCI) triggering, or battery swelling.
2. **Opaque & Complex Policy Clauses**:
   Warranty manuals span dozens of dense clauses with subtle geographic exemptions (e.g., standard 1-year limited warranties vs. extended coverage programs for Pixel 8 display banding or Pixel 7 battery bulges). Customers and agents routinely misapply terms, leading to erroneous denials or costly wrongful approvals.
3. **Disjointed Web & Community Research**:
   Known hardware defects (e.g., recurring display flickering or camera lens spontaneous cracking) often trend across Google Issue Trackers, Reddit, and XDA weeks before formal recall bulletins. Frontline reps have zero real-time visibility into these active community advisories.
4. **Friction in Service Center Handoffs**:
   Online triage rarely connects cleanly with walk-in repair depots. Customers arrive without diagnostic pre-briefs, slots get double-booked, and physical technician findings fail to loop back into the core adjudicator.

---

### The WarrantyMind Solution

WarrantyMind resolves these pain points through a fully integrated, transparent, five-tier pipeline:

```
[Customer Upload]  -->  [Vision & OCR MCP]  -->  [Dual-Stream Research]
                              |                           |
                              v                           v
                       [Pixel Telemetry]          [Known Bug Matches]
                              \                           /
                               v                         v
                       [Policy RAG]  -->  [LLM Diagnostic Agent]
                                                  |
                                                  v
                                      [Interactive Interview]
                                                  |
                                                  v
                                      [HITL Adjudication Gate]
                                                  |
                                                  v
                                    [Technician Slot Booking]
```

- **Multimodal Visual Evidence**: Combines local Ollama Vision Models (`gemma4:e2b` / vision LLMs) with PIL-based pixel telemetry (analyzing blur, brightness, edge variance, and color histograms) to validate physical condition and cross-reference device serial numbers against proof-of-purchase invoices.
- **Lexical Policy RAG (Zero Hallucination)**: Completely avoids ungrounded vector drift by utilizing deterministic SQLite lexical querying across genuine Google Pixel warranty clauses and extended repair programs.
- **Dual-Stream Live Research**: Queries official Google Support advisories and enthusiast forum threads in parallel via Brave Search, constrained by rigorous domain allowlisting.
- **Interactive Diagnostic Interview**: When evidence is ambiguous, an autonomous diagnostic interview agent synthesizes targeted follow-up questions tailored to the exact symptom pattern before rendering recommendations.
- **Atomic Service Center Orchestration**: Links digital adjudication directly to physical repair center capacity via atomic SQLite slot reservations (`BEGIN IMMEDIATE`), complete with repair estimate sheets.

---

### Core Design Principles & Philosophy

1. **AI Proposes, Humans Decide (Responsible AI)**:
   The system never auto-rejects or auto-approves warranties behind closed doors. The engine acts as an expert investigative co-pilot that produces structured adjudication briefs, cost breakdowns, and policy citations—requiring human agents or certified technicians to sign off.
2. **Model Context Protocol (MCP) Decoupling**:
   Every analytical tool (Vision, Web Research, Policy Store, Operations) runs as a standalone MCP server with standardized JSON-RPC protocols. Tools can be audited, scaled, or swapped independently of the orchestrator.
3. **Local-First Privacy & Cost Efficiency**:
   Designed to execute locally or in hybrid clouds via Ollama, preventing proprietary customer device photos and private purchase invoices from leaking to closed third-party cloud APIs.
4. **Deterministic & Auditable State Machine**:
   Every case transition is logged as an immutable state event with cryptographic token sessions, granular RBAC, and full outbox event dispatching.

---

### Stakeholder Personas & Value Matrix

| Persona | Primary Needs & Pain Points | How WarrantyMind Delivers |
|---|---|---|
| **Claimant (Device Owner)** | Wants fast, clear answers without waiting on hold; needs simple photo upload and local appointment scheduling. | Instant AI triage, guided diagnostic questionnaire, transparent policy citations, and instant appointment booking in under 3 minutes. |
| **Support Agent** | Overwhelmed by ticket volume; struggles to verify invoice authenticity and cross-reference obscure warranty clauses. | Pre-assembled diagnostic summaries, OCR invoice cross-checks, highlighted policy matches, and single-click approval/escalation. |
| **Service Center Technician** | Receives devices with vague descriptions; needs standardized physical inspection worksheets and parts catalog. | Comprehensive incoming device packet, structured physical inspection submission form, and automated cost estimation. |
| **OEM / Operations Lead** | Needs to curtail warranty fraud, maintain brand loyalty, track recurring component failures, and audit claim workflows. | Strict anti-tampering heuristics, real-time analytics on trending device defects, and a tamper-proof SQLite audit trail. |

---

## Overview & Key Features

WarrantyMind is designed as a production-ready, responsible AI warranty processing system. It does **not** make autonomous warranty decisions — every coverage conclusion requires explicit human verification. The AI pipeline accelerates and structures the investigation; humans close the loop.

| Feature | Detail |
|---|---|
| **Multimodal Evidence Inspection** | Ollama VLM (Gemma 4 vision) + Pillow pixel-level telemetry to validate device photos |
| **Web Research (Brave Search)** | Parallel official Google + community searches with strict domain allowlisting |
| **Policy RAG** | Lexical retrieval from an internal SQLite policy clause store; no hallucinated coverage claims |
| **LLM Diagnostic Agent** | Ollama text model synthesizes all evidence into focused Q&A with safe fallback |
| **Human-in-the-Loop** | Six distinct interrupt states guarantee a human reviews before any repair commitment |
| **Technician Portal** | Service-center technicians submit hardware inspection; adjudication logic runs post-inspection |
| **Support Escalation** | Full escalation path to human support with a structured handoff packet |
| **Secure Auth** | PBKDF2-SHA256 session tokens, HMAC fingerprinting, 12-hour token expiry |
| **Transactional Slot Booking** | Optimistic locking via SQLite BEGIN IMMEDIATE prevents double-booking |
| **Outbox Events** | Every major transition emits an outbox event for downstream integration |

---

## Architecture Overview

```
+-------------------------------------------------------------------------+
|                          Browser (SPA)                                  |
|          static/index.html  .  static/app.js  .  static/styles.css     |
+-----------------------------------+-------------------------------------+
                                    |  HTTP REST (Bearer token)
                                    v
+-------------------------------------------------------------------------+
|               FastAPI Application  (warrantymind/main.py)               |
|                                                                         |
|   Auth  ---  Orders  ---  Cases (CRUD + Workflow transitions)           |
|                                 |                                       |
|                     Depends(get_current_user)                           |
+-----------------------------------+-------------------------------------+
                                    |  calls
                                    v
+-------------------------------------------------------------------------+
|          WarrantyMindOrchestrator  (orchestrator/graph.py)              |
|                                                                         |
|  run_initial_investigation()                                            |
|  resume_after_diagnostic_interview()                                    |
|  resume_after_slot_booking()                                            |
|  resume_after_technician_inspection()                                   |
|  escalate_to_human_support()                                            |
+------+-------------+------------------+------------------+--------------+
       |             |                  |                  |
       v             v                  v                  v
+----------+  +-----------+  +-------------+  +------------------+
|Evidence  |  |Diagnostic |  |Policy RAG   |  |Service Ops       |
|MCP Server|  |Interview  |  |MCP Server   |  |MCP Server        |
|          |  |MCP Server |  |             |  |                  |
|.inspect  |  |.create_   |  |.retrieve_   |  |.get_estimates    |
|  photos  |  |  interview|  |  guidance   |  |.list_slots       |
|.extract  |  |.reanalyze |  |             |  |.compile_sheet    |
|  invoice |  |  answers  |  |             |  |                  |
+----+-----+  +-----+-----+  +------+------+  +---------+--------+
     |              |               |                    |
     v              v               v                    v
+---------+  +-------------------+  +------------------------------+
|  Ollama |  |  OllamaCaseAgent  |  |         SQLite DB            |
|  Vision |  |  (text LLM)       |  |                              |
|  (VLM)  |  |                   |  |  users / sessions            |
|gemma4:  |  |  + ResearchAgents |  |  orders / cases              |
| e2b     |  |   . Brave Search  |  |  policy_clauses              |
|         |  |     (warranty +   |  |  price_catalog               |
+---------+  |      community)   |  |  service_slots               |
             +-------------------+  |  outbox_events               |
                                    +------------------------------+
```

---

## System Flowchart — End-to-End Case Lifecycle

```
Customer logs in
      |
      v
Selects Order (Pixel Phone / Watch / Pixelbook)
      |
      v
POST /api/cases  ---  multipart: symptom + description + photos?
      |
      +--[photos uploaded]----------------------------------------------+
      |                                                                  |
      |   Evidence MCP: inspect_device_photos                           |
      |   +------------------------------------------+                  |
      |   | 1. Pillow pixel-level telemetry           |                  |
      |   |    . green channel spike detection        |                  |
      |   |    . resolution & file size validation    |                  |
      |   | 2. Ollama VLM (Base64 images)             |                  |
      |   |    . product_relevance check              |                  |
      |   |    . visible damage classification        |                  |
      |   |    . observable symptoms extraction       |                  |
      |   +------------------------------------------+                  |
      |                                                                  |
      |   [inconsistent / VLM unavailable] --> HTTP 422 / 503 (reject) |
      |   [consistent] -------------------------------------------------+
      |
      v
Evidence MCP: extract_invoice_metadata
   . Parse uploaded JSON/text invoice OR use order DB record
   . Cross-check serial number & purchase date

Research Agents (parallel, ThreadPoolExecutor x2)
   +-------------------------------------------------+
   | WarrantyResearchAgent                            |
   |  . Brave Search -> site:support.google.com       |
   |  . Only google.com domain results kept           |
   |  . Cached 30 min in-memory with thread lock      |
   +-------------------------------------------------+
   | CommunityResearchAgent                           |
   |  . Brave Search -> site:reddit.com/r/GooglePixel |
   |    + site:support.google.com/pixelphone/community|
   |  . Tagged as anecdotal, not policy evidence      |
   +-------------------------------------------------+

Policy RAG MCP: retrieve_pixel_warranty_guidance
   . Lexical (token overlap) retrieval from policy_clauses table
   . Attaches official Google source URLs from research results
   . preliminary_eligibility always = REQUIRES_OFFICIAL_POLICY_VERIFICATION

Diagnostic Interview MCP -> OllamaCaseAgent.create_initial_response()
   . Sends: product info + VLM obs + research + policy guidance
   . Returns: customer_response + 2-4 focused Q&A + confidence rating

Service Ops MCP:
   . get_preliminary_repair_estimates  (price_catalog lookup)
   . list_available_service_slots
   . compile_service_job_sheet  (v1)

Case saved to DB
workflow_status = AWAITING_DIAGNOSTIC_INTERVIEW
interrupt = await_diagnostic_interview
      |
      v
Customer answers diagnostic questions
POST /api/cases/{id}/interview-reply
      |
      v
OllamaCaseAgent.evaluate_answers()
   . Re-synthesizes all evidence + customer answers
   . Updates refined_diagnosis_hypothesis + confidence
   . compile_service_job_sheet (updated)

workflow_status = AWAITING_CUSTOMER_SLOT_CONSENT
interrupt = await_customer_slot_consent
      |
      v
Customer reviews pricing & books service slot
POST /api/cases/{id}/book-slot
   . BEGIN IMMEDIATE transaction (prevents double-booking)
   . Validates quote_version (stale-quote guard)
   . Locks slot: is_booked = 1
   . Emits outbox event: APPOINTMENT_BOOKED_JOB_SHEET_V1_READY
   . compile_service_job_sheet (v1_pre_inspection)

workflow_status = BOOKED_AWAITING_TECHNICIAN_INSPECTION
interrupt = await_technician_inspection
      |
      v
Technician (same service_center_id) submits inspection report
POST /api/cases/{id}/technician-inspection
   . serial_verified  .  physical_impact_damage  .  liquid_contact_detected
   . confirmed_fault_component  .  technician_notes

Adjudication Logic (Orchestrator decision tree):
   +--------------------------------------------------------------------+
   | serial_verified = False  ->  REJECTED_SERIAL_MISMATCH              |
   | fault = no_fault_found   ->  NO_HARDWARE_FAULT_FOUND               |
   | policy = HUMAN_REVIEW    ->  AWAITING_HUMAN_POLICY_REVIEW          |
   | eligible + no exclusion  ->  APPROVED_FREE_WARRANTY_OR_PROGRAM     |
   | else                     ->  PAID_REPAIR_QUOTE_ISSUED               |
   +--------------------------------------------------------------------+

   compile_service_job_sheet (v2_final_adjudication)
   Emits: TECHNICIAN_INSPECTION_COMPLETED_JOB_SHEET_V2

         +------------------------------------------+
         |                                          |
         v                                          v
[Requires paid consent]                  [Free warranty / review]
POST /api/cases/{id}/repair-consent      Human support acts
   . customer approves / declines
   . REPAIR_AUTHORIZED_IN_PROGRESS
   . PAID_REPAIR_DECLINED_RETURN_DEVICE

[At any stage - optional path]
POST /api/cases/{id}/escalate
   . Builds structured Support Handoff Packet
   . policy citations, VLM obs, research brief, evidence gaps
   . interrupt = await_human_support_resolution

POST /api/cases/{id}/support-reply
   . Support agent posts resolution or override
   . Can waive_diagnostic_fee
```

---

## Component Deep-Dive

### FastAPI Application Layer (`warrantymind/main.py`)

The application entry point mounts the static SPA and exposes 12 REST endpoints.

| Concern | Implementation |
|---|---|
| **Session Security** | Raw Bearer tokens are never stored — only their HMAC-SHA256 fingerprint is persisted via `_session_fingerprint()`. |
| **Token Expiry** | Sessions older than 12 hours are invalidated and deleted on any authenticated request. |
| **Product Guard** | `_require_pixel_case()` blocks legacy records from entering the Pixel workflow (HTTP 410). |
| **Photo Upload** | Pillow verifies MIME type + max 10 MB + max 40 MP resolution. SHA-256 in filename. Up to 4 images per case. |
| **Async Offload** | `run_in_threadpool()` keeps synchronous Ollama HTTP calls off the async event loop. |
| **Startup Seeding** | In non-production, `seed_demo_data()` runs automatically to populate users, orders, slots, and policy clauses. |

---

### Orchestrator — Workflow Graph (`warrantymind/orchestrator/graph.py`)

The `WarrantyMindOrchestrator` class acts as the **workflow supervisor** — called by the FastAPI layer at each interrupt point.

#### `run_initial_investigation()`

Executes the 7-step investigation pipeline on case creation:

```
Step 1 -> Evidence:     VLM photo inspection + invoice extraction
Step 2 -> Research:     official Google warranty search (parallel thread)
Step 3 -> Research:     community posts search (parallel thread)
Step 4 -> Policy RAG:   retrieve warranty guidance clauses
Step 5 -> Diagnostic:   Ollama synthesizes all data -> questions generated
Step 6 -> Service Ops:  pricing estimates + available slots
Step 7 -> Service Ops:  compile Job Sheet v1
```

Returns full `case_state` dict with `current_interrupt = "await_diagnostic_interview"`.

#### `resume_after_diagnostic_interview()`
Calls `OllamaCaseAgent.evaluate_answers()` with normalized customer answers. Updates `refined_diagnosis_hypothesis` and generates updated Job Sheet.

#### `resume_after_slot_booking()`
Attaches `booking_record`, sets interrupt to `await_technician_inspection`, emits Job Sheet v1.

#### `resume_after_technician_inspection()`
Implements full adjudication decision tree. Serial mismatch -> no fault -> human review -> free warranty -> paid quote. Emits Job Sheet v2.

#### `escalate_to_human_support()`
Builds structured `support_handoff` packet with: evidence reviewed, AI recommendation, cited clauses, research brief, unresolved objection, recommended support actions.

---

### MCP Servers

All MCP servers use `LocalFastMCPRegistry` — a lightweight Python-level tool registry that mirrors the MCP protocol tool schema.

#### `evidence-mcp-server` (`mcp_servers/evidence_mcp.py`)

| Tool | Description |
|---|---|
| `inspect_device_photos` | Pillow pixel telemetry + Ollama VLM via Base64. Returns structured `VisualObservationResult`. |
| `extract_invoice_metadata` | Parses JSON or free-text invoice. Cross-checks serial and purchase date against order DB. |

**VLM Pipeline:**
1. Pillow 40x40 grid-sample: green OLED emission spikes, bright/dark pixel ratios
2. Base64 encode images -> POST to `OLLAMA_BASE_URL/api/generate`
3. Structured JSON: `product_relevance`, `visible_external_damage`, `observable_symptoms`, `feedback`
4. Falls back to complaint-text heuristics if Ollama unavailable

#### `pixel-diagnostic-agent` (`mcp_servers/diagnostic_interview_mcp.py`)

| Tool | Description |
|---|---|
| `create_research_grounded_diagnostic_interview` | VLM obs + research + policy -> customer response + 2-4 Q&A questions |
| `reanalyze_customer_answers_with_ollama` | Re-synthesis after customer answers -> refined hypothesis + confidence |

Both delegate to `OllamaCaseAgent` with safe fallback if Ollama unreachable.

#### `pixel-warranty-research` (`mcp_servers/policy_rag_mcp.py`)

| Tool | Description |
|---|---|
| `retrieve_pixel_warranty_guidance` | Lexical token-overlap retrieval from `policy_clauses` table. Top 4 results + official URLs. Always REQUIRES_OFFICIAL_POLICY_VERIFICATION. |

#### `service-ops-mcp-server` (`mcp_servers/service_ops_mcp.py`)

| Tool | Description |
|---|---|
| `get_preliminary_repair_estimates` | Looks up `price_catalog`. Returns `not_configured` if empty (no invented prices ever). |
| `list_available_service_slots` | Returns unbooked `service_slots` rows. |
| `compile_service_job_sheet` | Assembles 7-section structured Job Sheet from full case state. |

---

### Agents (`warrantymind/agents/`)

#### `OllamaCaseAgent` (`agents/ollama_case_agent.py`)

Core LLM reasoning component. Uses `/api/chat` with strict system prompt enforcing:
- No invented prices, policies, or citations
- Community posts treated as anecdotes only
- Only describe visible VLM evidence
- Return structured JSON: `customer_response`, `refined_diagnosis_hypothesis`, `confidence`, `questions`, `source_citations`, `evidence_gaps`
- Never recommend factory reset without backup warning

`_normalize()` validates and sanitizes all LLM output, enforcing field types, lengths, and allowed citation IDs.

#### `WarrantyResearchAgent` (`agents/research.py`)
- Query: `site:support.google.com OR site:store.google.com "{model}" warranty repair {region} {symptom}`
- Strict filter: only `google.com` domain results kept
- 30-minute in-memory cache with thread lock

#### `CommunityResearchAgent` (`agents/research.py`)
- Query: Reddit/r/GooglePixel + Google Help Community
- All results tagged `source_type: community_anecdote`
- Privacy guardrail: `_safe_search_terms()` strips customer narrative; only product/symptom label words sent

---

### Database Layer (`warrantymind/database.py`)

SQLite with MEMORY journal mode. Eight tables:

```
users               <- PBKDF2 hash, role, full_name, service_center_id
sessions            <- HMAC-fingerprinted tokens, created_at timestamp
orders              <- Customer device purchases (Pixel Phone/Watch/Pixelbook)
policy_clauses      <- Internal SOP guidance with product_scope, region, depends_on
price_catalog       <- Repair estimates per component (empty until approved source configured)
service_slots       <- Available service center appointment windows
cases               <- Full case lifecycle; state_json blob = entire case state
outbox_events       <- Transactional event log for downstream integration
```

Password security: PBKDF2-SHA256 with 310,000 iterations. Legacy SHA-256 hashes auto-upgraded at next login.

---

### Frontend (`static/`)

| File | Description |
|---|---|
| `index.html` | Single HTML shell, semantic layout, meta SEO tags |
| `styles.css` | 42 KB — dark theme, glassmorphism cards, animated workflow states, responsive grid |
| `app.js` | 48 KB vanilla JS — multi-role SPA, tab routing, case state machine rendering |

Role-aware UI:
- **Customer** — orders list, case creation with photo upload, diagnostic Q&A, slot picker, repair consent
- **Technician** — inspection form gated to their `service_center_id`
- **Support** — case browser, escalation thread, resolution actions (waive fee, priority override)

---

## MCP Architecture Deep-Dive

```
+-------------------------------------------------------------------+
|                   LocalFastMCPRegistry                             |
|                 (mcp_servers/protocol.py)                         |
|                                                                    |
|  server_name: str                                                 |
|  instructions: str                                                |
|  _tools: Dict[str, ToolDefinition]                                |
|                                                                    |
|  @registry.tool(name, description, input_schema)                  |
|  def my_tool(**kwargs) -> Any                                     |
|                                                                    |
|  registry.list_tools()  -> List[ToolDef]  <- /api/mcp/discovery   |
|  registry.call_tool(name, args) -> Any    <- Orchestrator          |
+-------------------------------------------------------------------+
```

Each MCP server is a **singleton** instantiated at import time. Tools register with full JSON Schema input definitions. The orchestrator calls `mcp.call_tool(name, args)` which dispatches to the registered Python function.

`/api/mcp/discovery` exposes all 4 servers and their tools with full schemas — compatible with MCP Inspector.

> **Note:** This uses local in-process Python registries. An external MCP transport (stdio/SSE) is not required for local deployment but can be added by wrapping each registry in a proper MCP server process.

---

## Data Flow Diagrams

### Photo Upload & VLM Validation

```
Customer uploads photo
         |
         v
FastAPI: content_type check (JPEG/PNG/WebP only)
         |
         v
Pillow: Image.open() -> verify() + resolution check (max 40MP)
         |
         v
SHA-256 fragment -> unique filename -> save to UPLOAD_DIR
         |
         v
evidence_mcp.inspect_device_photos()
         |
    +----+-------------------------------------+
    v                                          v
Pillow pixel telemetry              Ollama VLM call
. green channel spike %             . Base64 encode images
. bright / dark pixel ratio         . Structured JSON prompt
. green_line_signature_detected     . product_relevance check
                                    . observable_symptoms list
    +----------------+--------------+
                     v
      product_relevance == "consistent" ?
              |                |
             YES               NO
              |                |
              v                v
         Continue          Delete saved files
         pipeline          Return HTTP 422 / 503
```

### Brave Search Privacy Guardrail

```
Customer complaint text
         |
         v  _safe_search_terms()  --  regex allowlist
         |  (product+symptom words only; names, serial
         |   numbers, addresses, complaint narrative stripped)
         v
query = "site:support.google.com {model} warranty repair {symptom}"
         |
         v
Brave Search API  (HTTPS, country param = region from order)
         |
         v
Domain filter: only *.google.com results accepted
         |
         v
Assign source_id W1, W2, ...  ->  attach to case state
```

---

## Case Workflow States

```
                    +---------------------------+
                    |   AWAITING_DIAGNOSTIC_    |
                    |   INTERVIEW               |
                    |   interrupt:              |
                    |   await_diagnostic_       |
                    |   interview               |
                    +------------+--------------+
                                 |  Customer answers Q&A
                                 v
                    +---------------------------+
                    |  AWAITING_CUSTOMER_       |
                    |  SLOT_CONSENT             |
                    |  interrupt:               |
                    |  await_customer_slot_     |
                    |  consent                  |
                    +------------+--------------+
                                 |  Customer books slot
                                 v
                    +---------------------------+
                    |  BOOKED_AWAITING_         |
                    |  TECHNICIAN_INSPECTION    |
                    |  interrupt:               |
                    |  await_technician_        |
                    |  inspection               |
                    +------------+--------------+
                                 |  Technician submits report
                                 v
              +------------------+---------------------+
              |                                        |
              v                                        v
+-----------------------------+      +---------------------------+
| AWAITING_CUSTOMER_          |      | COMPLETED_UNDER_WARRANTY  |
| REPAIR_CONSENT              |      | (free repair approved)    |
| interrupt:                  |      +---------------------------+
| await_customer_repair_      |
| consent                     |
+------------+----------------+
             |
      +------+-------+
      v              v
+----------------+   +------------------------------+
| REPAIR_        |   | PAID_REPAIR_DECLINED_        |
| AUTHORIZED_IN_ |   | RETURN_DEVICE                |
| PROGRESS       |   +------------------------------+
+----------------+

[Any state can escalate to:]
+------------------------------+
| ESCALATED_TO_HUMAN_SUPPORT   |
| interrupt:                   |
| await_human_support_         |
| resolution                   |
+------------------------------+
```

---

## Role-Based Access Control

| Endpoint | Customer | Technician | Support |
|---|---|---|---|
| `POST /api/auth/login` | YES | YES | YES |
| `GET /api/orders` | Own orders only | All orders | All orders |
| `POST /api/cases` | YES | NO | NO |
| `POST .../interview-reply` | Own case only | NO | NO |
| `POST .../book-slot` | Own case only | NO | NO |
| `POST .../technician-inspection` | NO | Same service_center_id only | NO |
| `POST .../repair-consent` | Own case only | NO | NO |
| `POST .../escalate` | Own case only | NO | YES |
| `POST .../support-reply` | Own case, no resolution_action | NO | YES, all actions |

---

## Environment Configuration

Copy `.env.example` to `.env` and set:

```dotenv
# Ollama (required for AI features)
WM_ENABLE_OLLAMA=true
WM_OLLAMA_BASE_URL=http://127.0.0.1:11434
WM_TEXT_MODEL=gemma4:e2b
WM_VISION_MODEL=gemma4:e2b
WM_EMBED_MODEL=embeddinggemma-2:270m
WM_VISION_REQUEST_TIMEOUT=210
WM_TEXT_REQUEST_TIMEOUT=120

# Brave Search (optional)
WM_BRAVE_SEARCH_API_KEY=
WM_BRAVE_SEARCH_BASE_URL=https://api.search.brave.com/res/v1/web/search
WM_RESEARCH_TIMEOUT_SECONDS=12
WM_RESEARCH_COUNTRY=IN

# Storage
WM_STORAGE_DIR=./runtime/uploads
WM_DB_PATH=./runtime/warrantymind.db

# Security
WM_SECRET_KEY=change-this-in-production-to-a-random-32-char-string
WM_ENV=local
WM_MAX_UPLOAD_BYTES=10485760
WM_MAX_IMAGE_PIXELS=40000000
```

---

## Installation & Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) running locally with a vision+text model
- (Optional) [Brave Search API key](https://brave.com/search/api/)

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/WarrantyMind_Advanced_MCP.git
cd WarrantyMind_Advanced_MCP

python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# Unix/macOS
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-optional.txt  # optional PDF support

cp .env.example .env
# edit .env

ollama pull gemma4:e2b

uvicorn warrantymind.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

### Quick Start Scripts

```powershell
# Windows
.\start_windows.ps1
```

```bash
# Unix
chmod +x start_unix.sh && ./start_unix.sh
```

---

## Running with Docker

```bash
docker-compose up --build
```

The compose file mounts `./runtime` so SQLite DB and uploads persist across restarts.

---

## API Reference

### Authentication

```
POST /api/auth/login
Body: {"username": "customer1", "password": "Customer123!"}
Response: {"token": "wm_...", "username": "...", "role": "...", "full_name": "...", "service_center_id": null}

All protected endpoints: Authorization: Bearer wm_<token>
```

### Health & Discovery

```
GET /api/health/components   ->  Ollama + Brave Search + agent status
GET /api/mcp/discovery       ->  All MCP server + tool schemas
GET /api/config/client       ->  Demo mode flag
```

### Case Workflow Endpoints

```
GET  /api/orders                                ->  List orders
GET  /api/slots                                 ->  Available service slots
POST /api/cases                                 ->  Create case (multipart)
GET  /api/cases                                 ->  List cases
GET  /api/cases/{id}                            ->  Get case state
POST /api/cases/{id}/interview-reply            ->  Customer Q&A answers
POST /api/cases/{id}/book-slot                  ->  Book service appointment
POST /api/cases/{id}/technician-inspection      ->  Technician hardware report
POST /api/cases/{id}/repair-consent             ->  Customer repair decision
POST /api/cases/{id}/escalate                   ->  Escalate to support
POST /api/cases/{id}/support-reply              ->  Support agent message
```

---

## Demo Credentials

| Role | Username | Password | Notes |
|---|---|---|---|
| Customer | `customer1` | `Customer123!` | 4 demo orders: Pixel 9 Pro, Pixel 8, Pixelbook Go, Pixel Watch 3 |
| Customer | `customer2` | `Customer123!` | No orders |
| Technician | `technician1` | `Tech123!` | Assigned to CENTER-MAA-01 (Chennai) |
| Support | `support1` | `Support123!` | Senior Pixel Support Specialist |

---

## Project Structure

```
WarrantyMind_Advanced_MCP/
+-- warrantymind/
|   +-- main.py                          FastAPI app, all endpoints, auth
|   +-- config.py                        Environment-driven configuration
|   +-- database.py                      SQLite schema, seeding, auth utils
|   +-- schemas.py                       Pydantic models for requests + results
|   +-- orchestrator/
|   |   +-- graph.py                     WarrantyMindOrchestrator (workflow)
|   +-- mcp_servers/
|   |   +-- protocol.py                  LocalFastMCPRegistry base
|   |   +-- evidence_mcp.py              Photo inspection + invoice extraction
|   |   +-- diagnostic_interview_mcp.py  LLM diagnostic Q&A
|   |   +-- policy_rag_mcp.py            Policy clause retrieval
|   |   +-- service_ops_mcp.py           Pricing, slots, job sheets
|   +-- agents/
|       +-- ollama_case_agent.py         LLM reasoning agent (text)
|       +-- research.py                  Brave Search warranty + community
+-- static/
|   +-- index.html                       SPA shell
|   +-- app.js                           Frontend logic (48 KB)
|   +-- styles.css                       Dark theme styles (42 KB)
+-- tests/
|   +-- test_workflow.py
+-- scripts/
|   +-- index_policies.py
|   +-- run_eval_suite.py
|   +-- setup_demo.py
+-- docs/images/
+-- runtime/                             Generated at runtime (gitignored)
+-- .env.example
+-- .gitignore
+-- requirements.txt
+-- requirements-optional.txt
+-- docker-compose.yml
+-- start_windows.ps1
+-- start_unix.sh
+-- LICENSE
```

---

## Testing

```bash
pytest tests/ -v
pytest tests/ --cov=warrantymind --cov-report=html
pytest tests/test_workflow.py -v
```

---

## Safety & Guardrails

| Guardrail | Implementation |
|---|---|
| **No autonomous warranty decisions** | `preliminary_eligibility` always = `REQUIRES_OFFICIAL_POLICY_VERIFICATION`. Every coverage conclusion requires human sign-off. |
| **No invented prices** | `price_catalog` starts empty; repair costs only appear when an approved catalogue is loaded. |
| **No fabricated citations** | Ollama citations validated against actual `source_id` values from research results. |
| **Photo evidence limitation** | VLM results explicitly state they cannot verify internal damage, serial identity, or warranty eligibility. |
| **Community posts clearly labelled** | All Reddit/community results tagged `source_type: community_anecdote` with `source_limitations`. |
| **Privacy in search queries** | `_safe_search_terms()` strips all customer narrative; only product model and symptom topic words sent to Brave Search. |
| **Technician service-center lock** | Technicians can only submit inspections for cases at their `service_center_id`. |
| **Stale quote guard** | Slot booking requires current `quote_version` to prevent outdated pricing consent. |
| **Transactional booking** | `BEGIN IMMEDIATE` + `SELECT changes()` prevents concurrent double-booking race conditions. |
| **Production secret enforcement** | `WM_ENV=production` refuses to start with weak or default `WM_SECRET_KEY`. |

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

Built with: [FastAPI](https://fastapi.tiangolo.com/) · [Ollama](https://ollama.com/) · [Pydantic](https://docs.pydantic.dev/) · [Pillow](https://python-pillow.org/) · [Brave Search API](https://brave.com/search/api/) · [SQLite](https://sqlite.org/)
