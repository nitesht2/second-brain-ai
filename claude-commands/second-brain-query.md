# Second Brain: Query

Search and synthesize answers from your wiki knowledge base.

**Vault:** `~/SecondBrain/`

**Usage:** `/second-brain-query What did Karpathy study at Stanford?`

## Instructions

The user's question is: $ARGUMENTS

1. **Scan the wiki** to find relevant files:
   ```bash
   find ~/SecondBrain/wiki -type f -name "*.md"
   ```

2. **Read all wiki files** — search for content related to the question

3. **Synthesize an answer:**
   - Answer directly from the knowledge in wiki/
   - Cite the specific wiki entries used (e.g., "According to [[Andrej Karpathy]]...")
   - If the wiki doesn't have enough info, say so explicitly — do NOT hallucinate
   - List which wiki entries were most relevant

4. **Save the output** to `~/SecondBrain/outputs/`:
   ```
   YYYY-MM-DD [Short Query Title].md
   ```
   Output format:
   ```markdown
   # Query: [Question]
   Date: YYYY-MM-DD
   
   ## Answer
   [synthesized answer with [[wikilinks]] to sources]
   
   ## Sources Used
   - [[Wiki Entry 1]]
   - [[Wiki Entry 2]]
   
   ## Gaps Identified
   [any knowledge gaps — what would help answer this better]
   ```

5. **Report** the answer inline in the chat, plus confirm the output was saved
