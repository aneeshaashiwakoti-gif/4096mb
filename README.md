# CodeImpact Backend & AI Reasoning Engine (Person 3)

CodeImpact is an AI-powered developer intelligence platform that transforms raw repository changes and dependency graphs into deep semantic reasoning, grounded impact explanations, deterministic risk scores, and safe code-fix proposals.

> *"Git tells you what changed. A dependency graph tells you what is connected. CodeImpact tells you what the change means."*

---

## 1. Team Responsibilities & Boundaries

CodeImpact is built by a 4-person team with strict modular separation of concerns:

- **Person 1 (Local Agent)**: Local project access, file watching, change detection, raw file diffs, test execution.
- **Person 2 (Analyzer)**: AST parsing, symbol extraction, caller/callee resolution, dependency graphs, impact discovery.
- **Person 3 (THIS MODULE — Backend & AI Reasoning)**: FastAPI service, LLM integration, semantic impact explanation, deterministic risk engine, citation verification, safe fix proposals with unified diffs, Q&A assistant (`/ask`), validation contracts.
- **Person 4 (Frontend)**: Web/desktop UI, code viewers, graph visualizations, risk indicators, developer approval interface, diff viewers.

> **CRITICAL BOUNDARY ENFORCEMENT**:
> - This backend does **NOT** access local disks directly (arbitrary `C:/`, `D:/` drive scanning belongs to Person 1).
> - This backend does **NOT** compute dependency graphs or AST trees (belongs to Person 2).
> - This backend does **NOT** automatically modify files on disk. Fixes are returned as non-destructive proposals with unified diffs for developer review and Local Agent execution.

---

## 2. Client-Agnostic Architecture

The backend is fully client-agnostic and serves:
1. **Desktop App** (Electron / Tauri)
2. **Browser Web Application**
3. **VS Code Extension**

### Architecture Flow:

```
[Local Codebase]
       ↓
[Person 1: Local Agent]  (Watches files, extracts changed lines & snippets)
       ↓
[Person 2: Analyzer]     (Traces callers, builds call graph, packages JSON)
       ↓
[Person 3: FASTAPI BACKEND]
  ├── Analyzer Adapter  (Normalizes analyzer payload)
  ├── Reasoning Engine  (Queries LLM with strict grounding prompt)
  ├── Claim Verifier    (Deterministic citation verification against evidence)
  ├── Risk Engine       (Deterministic scoring from blast radius & contracts)
  └── Fix Engine        (No-assumption safe rewrite & unified diff generation)
       ↓
[Person 4: Frontend]     (Visualizes risk, impact chain, diffs, approval buttons)
       ↓ (Developer clicks "Approve Fix")
[Person 1: Local Agent]  (Applies diff to disk, runs tests, triggers re-analysis)
```

---

## 3. Installation & Setup

### Requirements:
- Python 3.10+
- pip

### Setup:
```powershell
# Navigate to backend directory
cd C:\Users\Nitisha\.gemini\antigravity\scratch\codeimpact\backend

# Install dependencies
pip install -r requirements.txt
```

You'll see:
- Number of chunks produced
- A text preview of chunk 0 with its file path and line range
- Embedding dimension (3072 for Gemini gemini-embedding-2 / gemini-embedding-001, 384 for local)
- `output/chunks.json` written
## 4. Environment Variables & Configuration

Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DEMO_MODE` | `true` | When `true`, runs completely offline with deterministic mock responses. No API key needed. |
| `HOST` | `127.0.0.1` | Host address to bind FastAPI server. |
| `PORT` | `8000` | Port to run FastAPI server. |
| `LLM_PROVIDER` | `openai` | Active provider: `openai` or `demo`. |
| `OPENAI_API_KEY` | `""` | OpenAI API key (kept backend-side only; never exposed to frontend). |
| `OPENAI_MODEL` | `gpt-4o` | Model identifier. |
| `OPENAI_TIMEOUT_SECONDS`| `30.0` | Timeout threshold for LLM requests. |
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | CORS allowed origins for Person 4's frontend. |

---

## 5. Running the Backend & Interactive Documentation

### Start Server:
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Swagger UI & OpenAPI:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI JSON**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 6. Core API Endpoints

### 1. `GET /health`
Returns system status, active provider, model, and demo mode state.

### 2. `POST /impact/explain`
Receives structured change and dependency data from Person 2, returns semantic explanation, deterministic risk, root cause, verified claims, and recommendations.

### 3. `POST /impact/verify`
Deterministically verifies citations against supplied code evidence snippets (checks file match, line boundary containment, and snippet text presence).

### 4. `POST /ask`
Repository-grounded developer Q&A assistant. Answers queries regarding why components are affected, root cause, or risk factors. If developer requests a fix, generates a fix proposal safely.

### 5. `POST /fix/propose`
Generates non-destructive code rewrite proposals with unified diffs. Adheres strictly to the **No-Assumption Rule**.

### 6. `POST /fix/apply`
Returns `501 Not Implemented` with `FILESYSTEM_ACCESS_RESTRICTED`. Informs callers that file application belongs to Person 1's Local Agent.

### 7. `POST /validate` & `POST /impact/reanalyze`
Evaluates post-fix evidence snippets to verify if the regression was resolved (`VERIFIED`, `PARTIALLY_RESOLVED`, `STILL_AFFECTED`, `UNKNOWN`).

---

## 7. The No-Assumption Policy & Safe Fix Engine

CodeImpact enforces a strict policy:

$$\text{DEVELOPER INTENT} + \text{REPOSITORY EVIDENCE} + \text{IMPACT ANALYSIS} = \text{PROPOSED FIX}$$

$$\text{LLM GUESS} \neq \text{CODE CHANGE}$$

1. **Explicit Developer Intent**: Developer must supply `instruction` and optional `constraints`.
2. **Repository Grounding**: If `cart.py` returns `CartTotal`, the engine will **ONLY** propose `total.tax` if the supplied evidence explicitly defines `class CartTotal` exposing the `tax` attribute.
3. **Refusal to Guess**: If the class definition or field structure is not in the supplied evidence, the engine returns:
   - `status: "NEEDS_MORE_EVIDENCE"`
   - Detailed message requesting the definition of `CartTotal`
4. **Ambiguity Handling**: If the developer instruction is ambiguous (e.g. `"fix it"`), the engine returns `status: "NEEDS_CLARIFICATION"`.

---

## 8. Deterministic Risk Engine

Risk is evaluated deterministically (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `UNKNOWN`) based on explainable factors:
- **Change Types**: `RETURN_TYPE_CHANGE`, `SIGNATURE_CHANGE`, `DATABASE_CONTRACT_CHANGE`, `AUTHORIZATION_CHANGE`.
- **Blast Radius**: Number of direct callers and depth of transitive impact chain.
- **Contract Intersections**: Breaking syntax patterns (e.g., dictionary subscription `['tax']` on object returns).
- **Domain Criticality**: Grounded intersections with sensitive operational domains (`payment`, `auth`, `database`).

---

## 9. Person 2 (Analyzer) Integration Contract

Person 2 sends structured JSON to `POST /impact/explain`:

```json
{
  "project_id": "demo-project",
  "change": {
    "file": "cart.py",
    "start_line": 42,
    "end_line": 48,
    "symbol": "calculate_total",
    "change_type": "RETURN_TYPE_CHANGE",
    "description": "Return type changed from dictionary to CartTotal",
    "before": "return {'subtotal': subtotal, 'tax': tax}",
    "after": "return CartTotal(subtotal, tax)"
  },
  "impacted_components": [
    {
      "file": "payment.py",
      "start_line": 87,
      "end_line": 90,
      "symbol": "process_payment",
      "relationship": "calls"
    }
  ],
  "impact_chain": [
    "cart.py:calculate_total",
    "payment.py:process_payment",
    "checkout.py:checkout"
  ],
  "evidence": [
    {
      "file": "cart.py",
      "start_line": 42,
      "end_line": 48,
      "content": "def calculate_total(cart):\n    ...\n    return CartTotal(subtotal, tax)\n"
    },
    {
      "file": "payment.py",
      "start_line": 87,
      "end_line": 90,
      "content": "    total = calculate_total(cart)\n    tax = total['tax']\n"
    }
  ]
}
```

*Note: An isolated `AnalyzerAdapter` normalizes naming variations without modifying reasoning logic.*

---

## 10. Person 4 (Frontend) Integration Contract

Person 4 receives predictable Pydantic JSON responses:

```json
{
  "summary": "Function calculate_total in cart.py modified its return type from a dictionary to a CartTotal object instance. Downstream caller payment.py uses dictionary subscript syntax, leading to runtime failure.",
  "risk": {
    "level": "HIGH",
    "reason": "High risk: RETURN_TYPE_CHANGE causes interface incompatibility in 1 downstream caller(s)...",
    "factors": [
      "High-impact change type: RETURN_TYPE_CHANGE breaks interface contracts across callers.",
      "Contract change directly intersects with critical domains: Payment transaction and billing path.",
      "Evidence reveals dictionary subscript access on return type that was changed to an object."
    ]
  },
  "impact_type": "RETURN_TYPE_CHANGE",
  "root_cause": {
    "file": "cart.py",
    "line": 42,
    "symbol": "calculate_total",
    "reason": "Return type contract was altered from dict to CartTotal without updating caller access patterns.",
    "citations": [
      {
        "file": "cart.py",
        "start_line": 42,
        "end_line": 48,
        "symbol": "calculate_total",
        "verified": true
      }
    ]
  },
  "direct_impacts": [
    {
      "file": "payment.py",
      "symbol": "process_payment",
      "line_range": "87-90",
      "reason": "Directly invokes calculate_total and executes total['tax'], expecting dict.",
      "citations": [
        {
          "file": "payment.py",
          "start_line": 87,
          "end_line": 90,
          "verified": true
        }
      ]
    }
  ],
  "indirect_impacts": [
    {
      "file": "checkout.py",
      "symbol": "checkout",
      "reason": "Transitively impacted caller in the execution chain calling process_payment.",
      "path": [
        "cart.py:calculate_total",
        "payment.py:process_payment",
        "checkout.py:checkout"
      ]
    }
  ],
  "claims": [
    {
      "statement": "cart.py:42 changed return type to CartTotal",
      "category": "FACT",
      "verified": true
    },
    {
      "statement": "payment.py:89 relies on dictionary subscription syntax",
      "category": "FACT",
      "verified": true
    }
  ],
  "recommended_actions": [
    "Update payment.py line 89 to access total.tax instead of total['tax']",
    "Run test suite for payment processing"
  ],
  "confidence": "HIGH",
  "uncertainties": []
}
```

---

## 11. Automated Test Suite

Run the full automated pytest suite offline without requiring an OpenAI API key:

```powershell
python -m pytest tests/ -v
```

All 25 unit and integration tests pass:
- `/health` check
- Valid and invalid `/impact/explain`
- Empty evidence handling
- Deterministic citation verification & hallucination detection
- Deterministic risk engine scoring & boundary escalation
- Safe fix proposals & unified diff generation
- Developer constraint enforcement & `NEEDS_MORE_EVIDENCE` triggers
- Client-agnostic filesystem boundary (`POST /fix/apply` restriction)
- Repository-grounded `/ask` assistant & intent analysis
- `AnalyzerAdapter` normalization
- `POST /validate` & `POST /impact/reanalyze`
