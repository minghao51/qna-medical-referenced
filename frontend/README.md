# Frontend

SvelteKit frontend for:

- the main chat experience at `/`
- the evaluation dashboard at `/eval`

## Commands

```bash
npm install
npm run dev
npm run build
npm run preview
npm run test
```

## Dependencies

### Markdown Rendering
- **svelte-markdown**: Parse and render markdown in chat responses
- **highlight.js**: Syntax highlighting for code blocks

### Usage

The `MarkdownRenderer` component is used in the main chat page to render assistant messages. It supports full CommonMark markdown plus GitHub-flavored tables, with syntax highlighting for Python, JavaScript, TypeScript, Bash, JSON, and XML.


## Local Expectations

- The frontend typically runs on Vite's default local port during normal development.
- Playwright uses port `5174` via `frontend/playwright.config.ts`.
- The backend API is expected at `http://localhost:8000`.

## Key Locations

- `src/routes/+page.svelte` for the chat page
- `src/routes/eval/+page.svelte` for the evaluation dashboard
- `src/lib/components/` for reusable UI components
- `tests/` for Playwright end-to-end tests

For full project setup, use `docs/quickstart.md` from the repo root.
