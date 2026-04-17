# Second Brain: Ingest

Process all raw files into structured wiki entries with Obsidian wikilinks.

**Vault:** `~/SecondBrain/`

## Instructions

Run these bash commands to find files:
```bash
find ~/SecondBrain/raw -type f -not -path "*/assets/*" -not -name ".DS_Store"
```

For each file found:

1. **Read** the file content
2. **Analyze** and extract:
   - Main topic and key takeaways (3-5 bullet points)
   - Entities mentioned: people, companies, products, places
   - Concepts and frameworks discussed
   - Related sources or references
3. **Create or update wiki entries:**
   - `wiki/entities/` — one file per person/company/product with [[wikilinks]] to related concepts and sources
   - `wiki/concepts/` — one file per idea/framework with [[wikilinks]] to entities and sources
   - `wiki/sources/` — one summary file for the source itself with [[wikilinks]] to all entities and concepts it covers
4. **Wiki entry format:**
   ```markdown
   # [Title]
   
   ## Summary
   [2-3 sentence summary]
   
   ## Key Points
   - [point 1]
   - [point 2]
   
   ## Connections
   - Related to: [[Entity or Concept]]
   - See also: [[Another Note]]
   
   ## Source
   [original file or URL if available]
   
   ## Tags
   #[relevant-tags]
   ```
5. **After processing** each raw file, move it to `~/SecondBrain/raw/processed/` (create the directory if needed)
6. **Report** a summary: how many files processed, what wiki entries were created/updated, new connections found

## Rules
- Every wiki entry MUST contain at least 2 `[[wikilinks]]` to other entries
- Never delete raw files — move to raw/processed/ after ingesting
- If a wiki entry already exists, append new information rather than overwriting
- Use consistent naming: Title Case for all wiki entry filenames
