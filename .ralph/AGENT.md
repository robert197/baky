# BAKY Build & Test Commands

## Development (all via Docker)
- Start services: `make up`
- Stop services: `make down`
- Django migrations: `make migrate`
- Create migrations: `make makemigrations`
- Django shell: `make shell`
- Run any manage.py: `make manage CMD="<command>"`

## Testing
- Full test suite: `make test`
- Specific test: `make test ARGS="-k test_name"`
- E2E tests: `make e2e`
- Validation suite: `make validate`
- Lint: `make lint`

## Git & GitHub
- View roadmap: `gh issue view 44 -R robert197/baky`
- View issue: `gh issue view <N> -R robert197/baky`
- Close issue: `gh issue close <N> -R robert197/baky`
- Check issue state: `gh issue view <N> -R robert197/baky --json state -q .state`
