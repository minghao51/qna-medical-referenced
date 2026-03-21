# Medical Intake Agent - Implementation Plan

**Date**: 2026-03-20
**Status**: Approved for Implementation

## Executive Summary

**Problem**: The current RAG pipeline only sees the immediate query, not the user's health context (age, cholesterol, BP, etc.) that appears scattered across chat history. This causes retrieval to miss relevant medical tables.

**Solution**: A **Medical Intake Agent** that:
1. Asynchronously monitors conversation for health parameters
2. Proactively asks for unknown values (max 2 per turn)
3. Maintains a persistent **User Health Profile** (30-day TTL)
4. Augments RAG queries with known parameters
5. Provides appropriate disclaimers when values are unknown

---

## Decisions

| Decision | Choice |
|----------|--------|
| Intake agent execution | Asynchronous (background processing) |
| Max follow-up questions per turn | 2 |
| Record declining parameters | No |
| Profile TTL | 30 days (same as chat history) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER CHAT                                    │
│   "I'm 35, sleep 6hrs"  "Is my cholesterol okay?"                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MEDICAL INTAKE AGENT (Async)                       │
│                                                                      │
│  Responsibilities:                                                    │
│  1. Extract known health parameters from conversation               │
│  2. Identify missing parameters relevant to query                   │
│  3. Proactively ask user for missing values (max 2 per turn)       │
│  4. Maintain evolving User Health Profile                           │
│                                                                      │
│  Trigger: After every user message (async, non-blocking)             │
│  Output: Follow-up questions OR "proceed" signal                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    USER HEALTH PROFILE STORE                         │
│                                                                      │
│  {                                                                   │
│    "session_id": "abc123",                                          │
│    "extracted_at": "2026-03-20T18:00:00Z",                         │
│    "parameters": {                                                  │
│      "age": { "value": 35, "source": "conversation", "updated_at": ... },
│      "gender": { "value": "male", "source": "conversation", ... },  │
│      "sleep_hours": { "value": 6, "source": "conversation", ... }, │
│      "blood_pressure": { "systolic": UNKNOWN, "diastolic": UNKNOWN },
│      "cholesterol": { "ldl": 130, "hdl": 45, "total": UNKNOWN },   │
│      "blood_glucose": { "value": UNKNOWN },                         │
│      "bmi": { "value": UNKNOWN }                                    │
│    },                                                                │
│    "discrepancies": [                                               │
│      { "parameter": "ldl", "old": 130, "new": 150, "flagged_at": ... }
│    ]                                                                 │
│  }                                                                   │
│                                                                      │
│  TTL: 30 days                                                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG + GENERATION                                  │
│                                                                      │
│  Query Augmentation:                                                 │
│  - Original: "Is my cholesterol okay?"                              │
│  - Augmented: "35yo male, LDL=130, HDL=45, cholesterol query..."      │
│                                                                      │
│  Generation Instructions:                                             │
│  - If param known: Provide personalized advice                       │
│  - If param unknown: Provide general advice + "please provide"       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Conversation Flow Examples

### Example 1: Parameter Known
```
User:    "I'm 35, sleep about 6 hours a night"
System:  [Extracts: age=35, sleep=6hrs. Stores in profile.]

User:    "Is my cholesterol okay?"
System:  [Profile has LDL=130, HDL=45 from earlier conversation]
         [Retrieval with: 35yo, LDL=130, HDL=45]
         "With your LDL of 130 mg/dL and HDL of 45 mg/dL..."

User:    "I should mention my LDL was actually 150, not 130"
System:  [Extracts: LDL=150. Flags discrepancy old=130, new=150]
         [Updates profile with new LDL value]
         "Got it, I've updated your LDL to 150 mg/dL..."
```

### Example 2: Parameter Unknown - Proactive Elicitation
```
User:    "I've been feeling tired lately, could it be my blood pressure?"
System:  [Profile: BP unknown]
         
         "To give you accurate advice about fatigue and blood pressure,
          it would help to know:

          1. Have you measured your blood pressure recently?
          2. If yes, do you remember the systolic (top number) and 
             diastolic (bottom number) values?

          [If you don't have these readings, I can provide general 
           information about how blood pressure can affect energy levels.]"
```

### Example 3: User Provides Data After Prompt
```
User:    "Okay, I just checked - it was 135/85"
System:  [Extracts: BP=135/85. Updates profile.]
         "Thanks! With a reading of 135/85 mmHg..."

User:    "Actually, I think it was 140/90"
System:  [Extracts: BP=140/90. Flags discrepancy (135/85 -> 140/90)]
         [Updates profile]
         "Thanks! I've noted your updated reading of 140/90 mmHg..."
```

### Example 4: User Declines
```
User:    "I don't have a blood pressure monitor at home"
System:  [No parameter recorded]

         "No problem! Without your blood pressure reading, 
          I can share some general information about how 
          blood pressure can affect energy levels..."

          [Retrieval: general BP-fatigue information]
          
          [Disclaimer]: Since I don't have your actual blood 
          pressure reading, here's general guidance..."
```

---

## Component Design

### New Files

| File | Purpose |
|------|---------|
| `src/agents/__init__.py` | Agent package init |
| `src/agents/medical_intake.py` | Medical Intake Agent (LLM-powered parameter extraction + elicitation) |
| `src/storage/user_profile_store.py` | Persistent User Health Profile storage (30-day TTL) |
| `src/rag/context_injector.py` | Query augmentation with user profile |
| `src/app/schemas/intake.py` | Pydantic schemas for intake agent |
| `src/app/routes/intake.py` | Intake API endpoints |
| `tests/test_intake_agent.py` | Unit tests for intake agent |
| `tests/test_user_profile_store.py` | Unit tests for profile store |

### Modified Files

| File | Change |
|------|--------|
| `src/app/routes/chat.py` | Add intake agent call (async) after user message |
| `src/usecases/chat.py` | Add profile retrieval, query augmentation |
| `src/app/schemas/chat.py` | Add `user_profile` field to `ChatRequest` |
| `frontend/src/routes/+page.svelte` | Handle intake agent follow-up questions (new message type: `follow_up`) |
| `docs/architecture/rag-system.md` | Add Medical Intake Agent section |
| `frontend/src/routes/docs/pipeline/+page.svelte` | Add Medical Intake Agent to RAG Query Flow diagram |

---

## API Design

### New Endpoint: `POST /intake/analyze`

Analyzes a message and conversation history to:
1. Extract known health parameters
2. Identify missing relevant parameters
3. Generate follow-up questions if needed (max 2)

**Request:**
```json
{
  "message": "I've been feeling dizzy lately",
  "session_id": "abc123",
  "conversation_history": [
    {"role": "user", "content": "I'm 35"},
    {"role": "assistant", "content": "..."}
  ]
}
```

**Response (needs follow-up):**
```json
{
  "action": "follow_up",
  "questions": [
    {
      "parameter": "blood_pressure",
      "text": "Have you measured your blood pressure recently?",
      "options": ["Yes, I have readings", "No, I haven't checked"]
    }
  ],
  "extracted_parameters": {}
}
```

**Response (proceed):**
```json
{
  "action": "proceed",
  "extracted_parameters": {
    "dizziness_duration": "2 weeks"
  },
  "profile_summary": {
    "known": ["age", "sleep_hours"],
    "relevant_missing": ["blood_pressure"],
    "all_unknown": []
  }
}
```

### New Endpoint: `POST /intake/extract`

Extracts parameters from a user response to follow-up questions.

**Request:**
```json
{
  "session_id": "abc123",
  "parameter": "blood_pressure",
  "response": "135 over 85",
  "response_type": "value"
}
```

**Response:**
```json
{
  "extracted": {
    "blood_pressure": {
      "systolic": 135,
      "diastolic": 85
    }
  },
  "profile_updated": true,
  "discrepancies": []
}
```

**Response (with discrepancy):**
```json
{
  "extracted": {
    "blood_pressure": {
      "systolic": 140,
      "diastolic": 90
    }
  },
  "profile_updated": true,
  "discrepancies": [
    {
      "parameter": "blood_pressure.systolic",
      "old_value": 135,
      "new_value": 140
    }
  ]
}
```

### Modified: `POST /chat`

New flow:
1. Receive user message
2. **Async**: Trigger intake agent to analyze message + history
3. If intake returns `follow_up`: Send questions to frontend, delay RAG
4. If intake returns `proceed`: Continue with RAG using augmented query

---

## Data Models

### UserHealthProfile

```python
class UserHealthProfile(BaseModel):
    session_id: str
    extracted_at: datetime
    parameters: dict[str, HealthParameter]
    discrepancies: list[Discrepancy]

class HealthParameter(BaseModel):
    value: Any  # int, float, str, or None for unknown
    source: Literal["conversation", "follow_up", "manual"]
    updated_at: datetime
    confidence: float = 1.0

class Discrepancy(BaseModel):
    parameter: str
    old_value: Any
    new_value: Any
    flagged_at: datetime
```

### IntakeResult

```python
class IntakeResult(BaseModel):
    action: Literal["proceed", "follow_up"]
    extracted_parameters: dict[str, Any]
    questions: list[FollowUpQuestion] | None
    profile_summary: ProfileSummary


class FollowUpQuestion(BaseModel):
    parameter: str
    text: str
    options: list[str]  # max 2 options
```

---

## DAG Changes (Frontend Pipeline Page)

### Current RAG Query DAG:
```
Query Input → Query Expansion → Hybrid Retrieval → MMR Rerank → Context Format → Generation
```

### Proposed RAG Query DAG:
```
Query Input → Medical Intake Check → Query Expansion → Hybrid Retrieval → MMR Rerank → Context Format → Generation
                                     ↓
                              [If missing params]
                                     ↓
                              Proactive Elicitation → [User provides data]
                                     
                                     ↓
                              Profile Update → Query Re-augmentation
```

---

## Implementation Sequence

### Phase 1: Foundation
1. Create `src/storage/user_profile_store.py` - Profile persistence (30-day TTL)
2. Create `src/app/schemas/intake.py` - Pydantic models
3. Create `src/app/routes/intake.py` - `/intake/analyze`, `/intake/extract` endpoints
4. Create `src/agents/__init__.py`

### Phase 2: Medical Intake Agent
5. Create `src/agents/medical_intake.py` - LLM-powered extraction + elicitation
6. Create `src/rag/context_injector.py` - Query augmentation
7. Modify `src/usecases/chat.py` - Integrate intake + profile

### Phase 3: API Integration
8. Modify `src/app/routes/chat.py` - Add intake agent call (async)
9. Modify `src/app/schemas/chat.py` - Add intake-related schemas

### Phase 4: Frontend
10. Modify `frontend/src/routes/+page.svelte` - Handle `follow_up` messages
11. Update `frontend/src/routes/docs/pipeline/+page.svelte` - Add Intake Agent to DAG

### Phase 5: Documentation
12. Update `docs/architecture/rag-system.md` - Document new flow
13. Add tests for intake agent and profile store

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Intake agent fails | Log error, proceed with RAG using existing profile |
| Profile store unavailable | Create in-memory profile, warn in logs |
| LLM can't parse parameter value | Ask user to rephrase or provide numeric value |
| User provides conflicting value | Store new value, flag discrepancy, proceed |

---

## Testing

1. **Unit Tests**
   - `tests/test_intake_agent.py` - Parameter extraction, follow-up generation
   - `tests/test_user_profile_store.py` - CRUD, TTL, discrepancy tracking

2. **Integration Tests**
   - Full conversation flow with mock LLM
   - Profile persistence across sessions

3. **E2E Tests (Playwright)**
   - User provides health info in chat
   - System asks follow-up questions
   - User responds, system uses data

---

## Files Summary

```
NEW:
  src/agents/__init__.py
  src/agents/medical_intake.py
  src/storage/user_profile_store.py
  src/rag/context_injector.py
  src/app/schemas/intake.py
  src/app/routes/intake.py
  tests/test_intake_agent.py
  tests/test_user_profile_store.py

MODIFY:
  src/app/routes/chat.py
  src/usecases/chat.py
  src/app/schemas/chat.py
  frontend/src/routes/+page.svelte
  frontend/src/routes/docs/pipeline/+page.svelte
  docs/architecture/rag-system.md
```
