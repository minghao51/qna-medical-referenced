1. First think through the problem, read the codebase for relevant files.
2. Before you make any major changes, check in with me and I will verify the plan.
3. Please every step of the way just give me a high level explanation of what changes you made
4. Make every task and code change you do as simple as possible. We want to avoid making any massive or complex changes. Every change should impact as little code as possible. Everything is about simplicity.
5. Maintain a documentation file that describes how the architecture of the app works inside and out.
6. Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering. Make sure to investigate and read relevant files BEFORE answering questions about the codebase. Never make any claims about code before investigating unless you are certain of the correct answer - give grounded and hallucination-free answers.
7. Running the Application
   - **Preferred method: Docker Compose**
     - Start both backend and frontend with: `docker-compose up`
     - Rebuild if code changes: `docker-compose up --build`
     - Stop services: `docker-compose down`
     - Backend runs on http://localhost:8001
     - Frontend runs on http://localhost:5174
   - **Local development (for active development with hot reload):**
     - Backend: `uv run python -m src.main` (runs on port 8000)
     - Frontend: `cd frontend && bun run dev` (runs on port 5173)
8. Python environment
    - "Use uv for Python package management and to create a .venv if it is not present."
    - "IMPORTANT: Always use uv run for all Python commands. Never use plain python or python3."
    - Use uv commands in your project's workflow. Common commands include:
    - uv sync to install/sync all dependencies.
    - uv run <command> (e.g., uv run pytest, uv run ruff check .) to execute commands within the managed environment.
    - uv add <package> to add a dependency to your pyproject.toml file.
9. When creating or generating Markdown (.md) files, you must strict adhere to the following naming convention: YYYYMMDD-filename.md
---
