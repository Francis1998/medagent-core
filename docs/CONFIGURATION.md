# Configuration Reference

The maintained configuration reference lives at [`../CONFIGURATION.md`](../CONFIGURATION.md).

Use that root document for:

- LLM key and model settings (defaults: GPT-6.1 Sol, Claude Opus 5.5, Gemini 4 Argon, Kimi K3.1 Pro; alternatives such as Claude Fable 5.2 and Gemini 4 Carbon or Hydrogen), the Kimi endpoint, the completion budget, and sampling-parameter compatibility.
- PubMed, OpenFDA, database, API server, and local knowledge-base settings.
- Safety-sensitive production settings such as `PII_HASH_SALT`, confidence thresholds, and agent timeouts.
- The opt-in CORS allow-list for the HL7 CDS Hooks service (`MEDAGENT_CDS_HOOKS_CORS_ORIGINS`); see [`guides/CDS_HOOKS_GUIDE.md`](guides/CDS_HOOKS_GUIDE.md).

For setup steps, see [`../QUICKSTART.md`](../QUICKSTART.md). For safety controls and research-use constraints, see [`../SAFETY.md`](../SAFETY.md).
