# Demo Repository for RepoPilot AI

This repository is a purpose-built demonstration project showcasing the capabilities of **RepoPilot AI**:

1. **Import Dependency Graph & Impact Analysis**:
   - `app/routes.py` -> `app/auth.py` -> `app/database.py` and `app/crypto.py`.
   - Modifying `app/database.py` directly impacts `app/auth.py` (direct) and `app/routes.py` (transitive blast radius).
2. **Static Code Analysis (Ruff)**:
   - Contains an intentional mutable default argument finding in `app/auth.py` (`roles: list[str] = []`, Ruff rule `B006`).
3. **AI Debug Assistant**:
   - Diagnoses the `B006` finding in `app/auth.py`, presents verified evidence from chunks and graph callers, and provides a hypothesis with root causes and code diff.
4. **Machine Learning Defect Risk**:
   - `app/payments.py` has high cyclomatic complexity ($v(g) > 10$) and multiple decision paths, triggering elevated defect risk probability with top SHAP drivers.
5. **Code Search & RAG**:
   - Semantic vector search and RAG assistant answer questions about password hashing, authentication flow, and payment fees with bracketed `[file:lines]` citations.
6. **Test Generation & Sandbox Runner**:
   - Synthesizes pytest unit tests and executes them inside an isolated Docker sandbox container.
