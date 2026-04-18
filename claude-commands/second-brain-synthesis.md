# Second Brain: Synthesis

Generate cross-source insight notes by clustering your wiki and finding patterns Ollama discovers across entries.

**Vault:** `~/SecondBrain/`

## Instructions

1. **Run the synthesis script:**
   ```bash
   python3 ~/SecondBrain/auto_ingest.py --synthesize
   ```

2. **Report inline:**
   - How many clusters were found and their names
   - How many synthesis entries were created or updated
   - The most interesting cross-source insight discovered (read one synthesis file and quote the Key Insight section)

3. **If Ollama is not running**, tell the user to open Ollama.app first, then retry.

4. **After synthesis**, suggest running `/second-brain-lint` to check for any new broken wikilinks in the synthesis entries.

## What synthesis does

- Reads all entries in `wiki/entities/`, `wiki/concepts/`, `wiki/sources/`
- Groups them into 3-6 thematic clusters using the local LLM
- For each cluster, finds: shared patterns, contradictions, and the key insight that only emerges when reading them together
- Writes one `wiki/synthesis/Synthesis - [Theme].md` per cluster

## When to use

- After ingesting 5+ new raw files (new material = new synthesis opportunities)
- Weekly as a knowledge review habit
- When you want to ask: "what have I actually learned from all this?"
