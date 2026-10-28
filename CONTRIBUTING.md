# Contributing

Contributions are welcome! Here's how:

1. Fork the repo
2. Create a branch: `git checkout -b feat/your-feature`
3. Enable the secret-scanning pre-commit hook: `git config core.hooksPath .githooks`
4. Make your changes and add tests under `tests/` where it makes sense
5. Run the suite: `pip install pytest && python3 -m pytest tests`
6. Open a pull request

Never commit API keys, `.env` files, or your personal vault (`wiki/`, `raw/`, `outputs/`). See [docs/SECURITY.md](docs/SECURITY.md).

## Ideas for contributions
- Linux (systemd/cron) and Windows Task Scheduler equivalents of the local-mode launchd jobs
- More capture sources (Reddit, LinkedIn, RSS, email)
- More LLM providers in `auto_ingest.py` (Anthropic, Gemini, local Ollama)
- A web query UI for people who don't use Discord
- Better local-model prompts for higher quality wiki entries
- Richer lint rules (orphan and drift detection)
