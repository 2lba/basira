# Reviewly - AI Code Reviewer

## Project Overview
Open source AI-powered code reviewer for GitHub Pull Requests.
Free alternative to CodeRabbit, fully self-hostable.

## Owner
Abdulaziz AlQahtani (@2lba)
mechE student, Alkhobar SA.

## Goals
- Production-grade code quality
- Realistic target: ~70% of CodeRabbit's feature set, 100% free
- Audience: developers worldwide (GitHub stars)

## Tech Stack
- Backend: Python 3.13 + FastAPI + SQLAlchemy 2.0 async + asyncpg
- AI: Claude API (Anthropic) - claude-sonnet-4-5
- Queue: Redis + arq (async background jobs)
- Database: PostgreSQL 16
- Frontend: React 19 + Vite + Tailwind 3
- GitHub: GitHub App with webhooks
- Deployment: Docker Compose

## Architecture Flow
1. GitHub webhook fires on PR open/sync
2. Backend verifies HMAC signature, queues job
3. Worker fetches PR diff via GitHub API
4. Worker chunks diff intelligently (by file, by hunk)
5. Worker calls Claude API with structured prompt
6. Worker posts review comments back via GitHub API
7. Web dashboard shows history, settings, repo management

## Build Order (no fixed days, work at natural pace)
1. Scaffolding: docker-compose, db schema, FastAPI skeleton, React skeleton
2. GitHub OAuth + GitHub App configuration
3. Webhook receiver + signature verification + job queue
4. Diff fetcher + intelligent chunking
5. Claude review engine + prompt engineering
6. PR comment posting + handling threads
7. Dashboard: auth, repo list, enable/disable, review history
8. Settings: review rules, ignored paths, severity threshold
9. Tests (unit + integration)
10. CI: GitHub Actions
11. Documentation + screenshots + landing page
12. Release v0.1.0

Work on items in order. Don't skip ahead. Complete each before next.

## Code Standards
- Zero AI fingerprints in code or commits
- No emojis anywhere
- Commit messages: lowercase, short, natural ("init", "auth", "webhook handler", "review engine")
- English only (this targets global audience)
- Type hints required in Python
- Tests for critical paths (auth, webhook verification, AI integration)
- Black + Ruff for Python formatting
- ESLint + Prettier for JS

## Security Requirements
- GitHub webhook HMAC SHA-256 verification (mandatory)
- All API keys in env vars, never in code or commits
- Rate limiting on all public endpoints (slowapi)
- bcrypt direct (NOT passlib - it's broken with bcrypt 5.x)
- JWT for session auth
- GitHub access tokens encrypted at rest (Fernet)
- Validate all Claude API responses before posting to GitHub
- CSP headers, X-Frame-Options, etc on frontend
- No console.log of secrets

## Lessons Learned (apply automatically)
- Use bcrypt directly, never passlib
- Avoid React StrictMode in production (breaks auth flows)
- CORS middleware needs custom wrapper for exception responses (use CORSAlwaysOnMiddleware pattern)
- Pydantic field_validator needed for PostgreSQL native types (INET, UUID)
- Docker build context is sandboxed - copy files into the service directory
- React 19 needs --legacy-peer-deps for some libs (react-is required for recharts)
- Always pin go.mod to minimum supported version, not local version
- Never use special chars (@, !, /) in dev passwords (shell parsing breaks)
- datetime.now(timezone.utc) - never datetime.utcnow (deprecated)

## Working Style
- Long autonomous sessions are fine
- Test after each feature with docker compose up
- Commit after each working feature with natural message
- Web search before answering about libraries (knowledge cutoff Jan 2026)
- If a decision is ambiguous, document the choice in commit message
- If something is genuinely uncertain, leave a TODO comment and continue

## Out of Scope for v0.1.0
- IDE plugins
- GitLab/Bitbucket support
- Custom AI models
- Billing/pricing infrastructure
- Multi-tenant orgs (single user for now)
- Custom languages beyond what Claude handles natively

## Stop Conditions (when to wait for owner)
- About to make irreversible changes (delete data, force push)
- Tests failing and root cause unclear after 30 min
- Architecture decision affects later 5+ files
- External service requires owner credentials (GitHub App registration, domain)
## Extended Security Requirements

### Input Validation
- All POST/PATCH endpoints: Pydantic schemas with strict types
- Max sizes: PR diff max 10MB, comments max 100KB
- File path sanitization (no ../ traversal)
- URL validation for webhooks (no internal IPs)

### Database
- SQLAlchemy ORM only (no raw SQL except migrations)
- Parameterized queries enforced
- DB user has minimum privileges (no DROP, no GRANT)
- Connection pool limits to prevent exhaustion

### Authentication & Sessions
- JWT expiry: 1 hour
- Refresh tokens: 7 days, single-use
- Account lockout: 5 failed logins per 15 min
- Password requirements: 12+ chars (no max), no common passwords
- Force re-auth for sensitive operations (deleting repo)

### Frontend Security
- React escapes by default - no dangerouslySetInnerHTML
- CSP: strict, no inline scripts, no eval
- Cookies: HttpOnly, Secure, SameSite=Strict
- CSRF tokens for state-changing operations
- Subresource Integrity (SRI) for CDN scripts

### Logging
- Never log: passwords, tokens, API keys, full request bodies
- Structured logging (JSON via structlog)
- Sensitive fields auto-redacted by middleware
- Audit log for: login, repo enable/disable, settings change

### Dependencies
- Pin all versions (no ^ or ~ in package.json)
- Dependabot enabled
- pip-audit in CI
- npm audit in CI

### API Limits
- Rate limit per IP: 100 req/min general, 5 req/min for auth
- Rate limit per user: 1000 req/hour
- Request timeout: 30s
- Body size limit: 10MB

### Secrets Management
- .env never committed (in .gitignore)
- Production secrets via environment only
- Rotate Fernet key procedure documented
- GitHub App private key: separate file, chmod 600

### Disclaimer
Security is layered. No system is unhackable. The goal is to make
the system require significant effort to compromise, not to make
it theoretically impossible.
## Design System

### Visual Identity
- Brand personality: Professional, technical, trustworthy
- Inspiration references: Linear, Vercel, Stripe (clean, sharp, dark-mode first)
- NOT inspired by: generic Bootstrap admin templates, Material Design boilerplate

### Color Palette
- Primary background: #0a0a0a (near black)
- Surface: #141414
- Border subtle: #1f1f1f
- Border emphasis: #2a2a2a
- Text primary: #f5f5f5
- Text secondary: #a3a3a3
- Text muted: #525252
- Accent: #6366f1 (indigo) for primary actions
- Success: #10b981
- Warning: #f59e0b
- Error: #ef4444
- AI insight highlight: #8b5cf6 (violet)

### Typography
- Display/Headings: Inter (weight 600-700)
- Body: Inter (weight 400-500)
- Code/Monospace: JetBrains Mono
- Sizes: text-xs (12) | text-sm (14) | text-base (16) | text-lg (18) | text-xl (20) | text-2xl (24) | text-4xl (36) | text-6xl (60)
- Line height: 1.5 for body, 1.2 for headings

### Spacing & Layout
- Base unit: 4px
- Common: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96
- Max content width: 1280px
- Sidebar width: 240px
- Card padding: 24px
- Section spacing: 64px on landing, 32px in app

### Components Style
- Buttons: 8px border-radius, no shadow by default, subtle hover state
- Cards: 12px border-radius, 1px border (not shadow)
- Inputs: 8px radius, 1px border, focus ring (2px indigo at 40% opacity)
- Tables: zebra stripes optional, sticky header on scroll
- Modals: backdrop blur, fade-in 150ms
- Code blocks: dark background even in light mode, syntax highlighted via shiki

### Motion
- Default transition: 150ms ease-out
- Hover transitions: 100ms
- Page transitions: 200ms
- Reduce motion: respect prefers-reduced-motion
- No bouncy/playful animations (this is a dev tool)

### Dark Mode First
- Design dark first, light mode as adaptation
- Most developers prefer dark
- Use CSS variables for theme switching

### Landing Page
- Hero: short tagline + subtitle + 2 CTAs (GitHub stars + Get Started)
- Live demo or screenshot of actual review comment
- 3-4 feature sections with mini visuals
- Pricing: "Free, forever, self-hosted" prominently
- Comparison table vs CodeRabbit (honest about features missing)

### Dashboard Pages
- Sidebar navigation, top header for user menu only
- Empty states: helpful illustrations + CTA
- Loading states: skeleton screens, not spinners
- Error states: explain what failed + recovery action

### Accessibility
- WCAG 2.1 AA minimum
- Keyboard navigation for all interactions
- Focus visible always
- Color contrast 4.5:1 minimum
- Screen reader labels on icon buttons
- Form errors associated with inputs

### What to Avoid
- No emoji in UI (icons via Lucide instead)
- No gradients except subtle on hero
- No 3D effects
- No glassmorphism
- No "AI sparkles" decoration
- No stock illustrations from unDraw
## AI Engine Specifications

### Model Selection
- Default: claude-sonnet-4-5 (balance speed/quality)
- For complex repos: option to use claude-opus-4-5 (slower, deeper)
- User selectable in settings, default sonnet

### Prompting Strategy
- System prompt: emphasize "senior engineer" tone, no hedging
- Few-shot examples: include 3-5 high-quality review examples
- Context window: include surrounding code (not just the diff)
- Output format: structured JSON (file, line, severity, category, message, suggestion)

### Review Categories
- bug: actual logic errors
- security: vulnerabilities, exposed secrets, injection risks
- performance: O(n²) where O(n) possible, N+1 queries, memory leaks
- maintainability: complexity, naming, dead code
- style: formatting, conventions (low priority, often muted by user)
- suggestion: improvement ideas (non-blocking)

### Severity Levels
- critical: must fix (security, data loss, crashes)
- major: should fix (bugs, significant perf issues)
- minor: consider fixing (maintainability)
- nit: optional (style, naming)

### Token Management
- Hard limit: 100k tokens per PR
- If diff too large: split by file, review separately
- Cache results by diff hash (avoid re-reviewing same code)
- Track cost per review for analytics

### Quality Controls
- Skip auto-generated files (package-lock.json, *.min.js, migrations/)
- Skip binary files
- Configurable ignore patterns per repo
- Confidence threshold: don't post low-confidence comments

### Failure Modes
- Claude API down: retry 3x with exponential backoff, then queue
- Invalid JSON response: re-prompt with stricter format
- Empty review: post "No issues found" comment (not silence)
- Rate limited: queue and process when limit resets
## Database Design Principles

### Naming Conventions
- Tables: plural snake_case (users, repositories, reviews)
- Columns: snake_case (created_at, github_repo_id)
- Foreign keys: {table_singular}_id (user_id, repo_id)
- Indexes: idx_{table}_{column(s)} (idx_reviews_repo_id)
- Unique constraints: uq_{table}_{column(s)}

### Required Columns on Every Table
- id: UUID primary key (uuid_generate_v4())
- created_at: timestamptz NOT NULL DEFAULT now()
- updated_at: timestamptz NOT NULL DEFAULT now() (auto-update trigger)

### Soft Delete Strategy
- Use deleted_at: timestamptz nullable
- Never DELETE rows (audit trail)
- Filter WHERE deleted_at IS NULL in queries

### Migrations
- Alembic for all schema changes
- Each migration must be reversible (downgrade implemented)
- Never modify existing migrations (only forward)
- Test downgrade before merging

### Indexes Strategy
- Foreign keys: always indexed
- Frequently filtered columns: indexed
- Composite indexes for common query patterns
- Don't over-index (writes get slower)

## Testing Requirements

### What to Test
- All authentication flows (login, JWT, refresh)
- Webhook signature verification (positive + negative cases)
- AI response parsing (malformed JSON, partial responses)
- Permission checks (user can only access their repos)
- Rate limiting (over and under threshold)

### What NOT to Test
- Third-party libraries (assume they work)
- Trivial getters/setters
- Pure UI components without logic

### Test Structure
- Unit: pytest, mocked external services
- Integration: real Postgres + Redis (testcontainers), mocked Claude API
- E2E: only critical happy paths (login → enable repo → simulate webhook → see review)

### Coverage Targets
- Critical paths (auth, webhook, AI): 80%+
- Business logic services: 60%+
- API routes: 50%+ (FastAPI handles a lot)
- Overall: 60%+

### Test Naming
- test_should_{behavior}_when_{condition}
- Example: test_should_reject_webhook_when_signature_invalid

### Fixtures
- Reusable factories (factory-boy)
- No hardcoded test data sprinkled in files
- Reset DB state between tests

## Error Handling

### User-Facing Errors
- Show what went wrong (not "An error occurred")
- Show what to do next (retry, contact support, check input)
- Never expose stack traces or internal IDs
- Map to status codes correctly:
  - 400: client did something wrong
  - 401: not authenticated
  - 403: authenticated but not allowed
  - 404: resource doesn't exist (or user can't see it)
  - 409: conflict (duplicate, concurrent edit)
  - 422: validation failed (with field-level details)
  - 429: rate limited
  - 500: our fault, log it
  - 503: temporarily unavailable

### Error Response Shape
{
  "error": {
    "code": "INVALID_WEBHOOK_SIGNATURE",
    "message": "Webhook signature verification failed",
    "details": { "expected_algo": "sha256" }
  }
}

### Logging Strategy
- ERROR: requires action (alerts, page on-call)
- WARN: something unusual, no action needed
- INFO: important events (review completed, user signed up)
- DEBUG: development only, off in production

### Sentry / Monitoring
- Exception tracking via Sentry SDK
- Sample 100% of errors, 10% of transactions
- Tag by user_id, repo_id, environment
- Source maps uploaded for frontend

## GitHub Integration Specifics

### GitHub App Permissions Required
- Repository: Contents (read), Pull requests (read+write), Metadata (read)
- Organization: Members (read) - for team features later
- User: Email (read) - for notifications

### Webhook Events to Subscribe
- pull_request: opened, synchronize, reopened
- pull_request_review_comment: for thread responses (later)
- installation: created, deleted
- installation_repositories: added, removed

### Rate Limit Handling
- GitHub API: 5000 req/hour per installation
- Use ETags for conditional requests
- Cache repo metadata 5 min
- Spread requests across installations

### Authentication Flow
- Installation access tokens (not user tokens) for API calls
- Tokens expire in 1 hour, refresh proactively
- Store installation_id, not access_token (regenerate as needed)

### Comment Strategy
- One summary review comment (overview)
- Inline comments for specific issues (max 20 per PR)
- Threaded replies to user questions (later feature)
- Edit own comments on PR re-sync (don't duplicate)
- Use review threads, not loose comments

## Performance Targets

### Response Times (95th percentile)
- API endpoints: <200ms
- Dashboard page load: <1s
- Webhook receive to queue: <100ms
- Review completion: <60s for typical PR (under 1000 lines)

### Resource Limits
- Backend: 512MB RAM, 0.5 CPU per instance
- Worker: 1GB RAM, 1 CPU per instance
- Postgres: connection pool max 20 per service
- Redis: max memory 256MB, evict LRU

### Scalability Boundaries
- v0.1: handle 100 repos, 1000 reviews/day
- Single Postgres instance fine
- Horizontal scale: workers can be multiplied
- Bottleneck likely: Claude API rate limits, not infra

## Project Structure

reviewly/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes (one file per resource)
│   │   ├── core/         # config, security, dependencies
│   │   ├── models/       # SQLAlchemy ORM
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # business logic
│   │   ├── workers/      # background jobs (arq)
│   │   ├── integrations/ # github, anthropic clients
│   │   ├── main.py
│   │   └── __init__.py
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── pages/        # route components
│   │   ├── components/   # reusable (ui/, features/)
│   │   ├── hooks/        # custom hooks
│   │   ├── api/          # API client functions
│   │   ├── lib/          # utilities
│   │   ├── styles/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── Dockerfile
│   ├── package.json
│   └── README.md
├── deployment/
│   ├── docker/
│   └── k8s/ (later, ignore for v0.1)
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── screenshots/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── .gitignore
├── .env.example
├── LICENSE (MIT)
├── README.md
└── CLAUDE.md

### Rules
- One concept per file (no god files)
- Max 300 lines per file (split if larger)
- Imports order: stdlib, third-party, local
- Type hints on all public functions

## Brand & Naming

### Product Name
- Working name: Reviewly (placeholder, change before v1.0)
- Alternative ideas to consider before release:
  - PRReview (descriptive)
  - CodeWise
  - Reviewer
  - DiffCheck
  - Audit (taken)
- Avoid: anything with "AI" in name (overused, dated quickly)

### Domain Strategy
- Not buying domain until product proven
- GitHub Pages for landing initially: 2lba.github.io/reviewly

### Tagline Drafts
- "AI code reviews. Open source. Self-hosted."
- "Senior engineer feedback on every PR."
- "Your AI pair reviewer."

### Logo
- Skip elaborate logo for v0.1
- Use a simple wordmark in Inter font
- Single icon: simplified version, monochrome

## Honest Project Limits

### What This Tool Will Do Well
- Catch obvious bugs (null checks, off-by-one, unused variables)
- Identify security issues with known patterns
- Suggest performance improvements
- Flag style inconsistencies
- Suggest better naming and structure

### What This Tool Will Struggle With
- Domain-specific business logic correctness
- Subtle race conditions
- Architecture decisions
- Whether code matches business requirements
- Code in less common languages (focus on top 10)

### What This Tool Will NOT Do
- Auto-fix code (read-only reviewer)
- Replace human reviewers (assist, not replace)
- Understand verbal context from chats/docs
- Run the code (static analysis only)
- Detect malicious intent

### Comparison with CodeRabbit (be honest in README)
- Feature parity goal: 60-70%
- Missing in v0.1: chat replies on threads, custom rules engine, learning from feedback, multi-AI consensus
- Better than CodeRabbit: free, self-hostable, open source, transparent prompts

## Release Strategy

### v0.1.0 (MVP) Definition of Done
- All features in build order completed
- Tests passing
- Docker compose up works on fresh machine
- README with screenshots, install instructions, demo
- LICENSE (MIT) committed
- At least 5 PRs reviewed successfully in dogfooding (use on own repos)

### Launch Channels (in order)
1. Personal GitHub (public)
2. Personal Twitter/X
3. r/programming, r/opensource subreddits
4. Hacker News (Show HN)
5. Dev.to article
6. Awesome Lists submissions

### NOT Launching
- Product Hunt (premature, save for v1.0)
- Paid ads (no money to burn)
- LinkedIn (later, after traction)

### Success Metrics (8 weeks post-launch)
- Minimum: 100 GitHub stars, 5 self-hosters
- Expected: 500 stars, 50 hosters, 1 contributor PR
- Stretch: 2000 stars, 500 hosters, 10 contributors


## No AI Fingerprints (Critical)

Everything must look like it was written by a human developer. Zero traces of AI assistance.

### Commit Messages
- All lowercase, short, natural
- Examples: "init", "auth", "webhook handler", "fix typo", "wip on dashboard"
- NEVER: "feat:", "chore:", "refactor:" prefixes (conventional commits look AI-generated)
- NEVER: "Generated by Claude", "Co-authored-by: Claude"
- NEVER: emoji in commits
- NEVER: long descriptive commits ("Implement comprehensive webhook handler with...")

### Code Comments
- Minimal comments, only when code isn't self-explanatory
- Natural tone: "# tricky: github sometimes sends null here" not "# This function processes the incoming webhook payload"
- NEVER: docstring blocks that explain obvious things
- NEVER: section banner comments like "# ===== AUTH SECTION ====="
- NEVER: emoji in code or comments
- NEVER: TODO with "Generated by AI" or similar
- Acceptable TODOs: "# todo: handle large diffs"
- Comments in English (project is English-only)

### Code Style
- Variable names: short but clear (user, repo, pr - not user_object, repository_instance)
- No over-abstraction (no AbstractBaseFactoryFactory)
- Pythonic / idiomatic, not enterprise Java style
- Pragmatic: ship working code, not theoretically perfect code

### Documentation Files
- README written in casual technical English
- No "Welcome to the documentation!" intros
- No marketing speak ("revolutionary", "cutting-edge", "seamless")
- Get to the point: what it does, how to install, how to use

### File Names
- Lowercase, simple: auth.py, webhook.py, review_engine.py
- No: AuthenticationHandlerService.py, WebhookProcessorImpl.py

### Error Messages
- Natural: "GitHub returned 401" not "An authentication error has occurred while attempting to communicate with the GitHub API"
- Direct: "Webhook signature invalid" not "The provided webhook signature does not match the expected signature"

### What Triggers the "AI Smell"
- Bullet-heavy documentation
- Three-paragraph commit messages
- Excessive markdown formatting in code comments
- Emojis used as decoration
- "🚀" or "✨" anywhere
- Phrases: "robust", "scalable", "production-ready" (use only if true and rare)
- Headers in markdown files like "## 🎯 Goals" (the emoji is the giveaway)

### How to Tell If Your Output Smells Like AI
Before committing, ask: "Would a sleepy developer at 11pm write this comment?" 
If the answer is "no, it's too polished" - simplify it.
