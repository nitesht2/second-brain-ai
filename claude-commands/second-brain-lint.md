# Second Brain: Lint

Health check the wiki — find conflicts, gaps, orphaned notes, and missing connections.

**Vault:** `~/SecondBrain/`

## Instructions

1. **Scan all wiki files:**
   ```bash
   find ~/SecondBrain/wiki -type f -name "*.md"
   ```

2. **For each wiki entry, check:**
   - Does it have at least 2 `[[wikilinks]]`? Flag any with fewer as orphaned
   - Are all `[[wikilinks]]` pointing to files that actually exist? Flag broken links
   - Is the content still current (check if source in raw/processed/ has a newer version)?
   - Are there contradictions between entries on the same topic?

3. **Build a connection map:**
   - List all entities and what concepts they link to
   - Identify clusters of notes that don't connect to each other (silos)
   - Suggest 3-5 new wikilinks that would add value

4. **Check for gaps:**
   - Topics mentioned in sources/ but with no entry in entities/ or concepts/
   - Entries that are stubs (under 100 words) and should be expanded

5. **Generate a lint report** saved to `~/SecondBrain/outputs/`:
   ```
   YYYY-MM-DD Lint Report.md
   ```
   Format:
   ```markdown
   # Wiki Lint Report
   Date: YYYY-MM-DD
   
   ## Summary
   - Total wiki entries: N
   - Orphaned notes (< 2 links): N
   - Broken wikilinks: N
   - Stubs to expand: N
   
   ## Errors (must fix)
   - [ ] [[Note Name]] — broken link to [[Missing Note]]
   
   ## Warnings (should fix)
   - [ ] [[Note Name]] — only 1 wikilink, suggest linking to [[Related]]
   
   ## Suggestions (nice to have)
   - Consider adding [[New Topic]] — referenced 3x but no wiki entry
   - Connect [[Entity A]] to [[Concept B]] — strong thematic overlap
   
   ## Gaps
   [topics that appear in sources but aren't in wiki yet]
   ```

6. **Report inline** the summary counts and top 3 action items
