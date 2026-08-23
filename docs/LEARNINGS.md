# what broke and how i fixed it

keeping this updated as i build, since its a required part of the submission.

---

### 1. mcp sdk breaking change (fastmcp moved)

when i first `pip install mcp`, it grabbed version 2.0.0 by default. every
mcp tutorial and the official docs example use `from mcp.server.fastmcp
import FastMCP`, but in 2.0.0 that module doesn't exist anymore - it got
renamed/moved to `mcp.server.mcpserver`. import failed with
`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`.

fix: pinned the dependency to `mcp==1.9.4` in requirements.txt instead of
letting it grab latest. lesson - always pin versions for anything actively
being developed, "just install latest" bit me here on day one.

### 2. PyJWT conflict on pip install

`pip install mcp` failed the first time with
`ERROR: Cannot uninstall PyJWT 2.7.0, RECORD file not found` - some
system-level package installed outside of pip's normal tracking.

fix: `pip install mcp --ignore-installed PyJWT` to force past it. not a
great fix long term, a proper venv from the start avoids this entirely,
which is what the README setup instructions use.

### 3. (placeholder - fill in once i run the agent against real data)

things i expect to actually break once i run this against groq for real:
- llm might not always return valid json even when told to - i added a
  fallback that escalates to human if json parsing fails, but need to check
  how often that actually triggers
- rag retrieval quality with keyword overlap vs semantic matching - if the
  llm's diagnosis quality is weak, this is probably why, and the fix is
  swapping to real embeddings

---

*i'll add more entries here as i actually run the batch and hit real issues -
this file is meant to be filled in live during building, not written after
the fact.*
