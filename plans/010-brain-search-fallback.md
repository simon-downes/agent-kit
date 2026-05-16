# Plan 010: Brain Search Multi-Word Fallback

## Objective

`ak brain search` fails silently when the agent passes multi-word phrases as a single
quoted argument (e.g. `"batch memory extraction"`). Ripgrep treats this as a literal
substring requiring all words consecutively in that exact order. The agent naturally
constructs searches this way — 11 empty results in one session. Fix the search to handle
multi-word terms gracefully: try exact phrase first, fall back to individual words if no
exact match.

## Requirements

- MUST try the full phrase as an exact substring match against content first
  - AC: `ak brain search "batch memory"` finds files containing the literal string "batch memory"
  - AC: Exact phrase matches score higher than individual word matches

- MUST fall back to individual word matching when exact phrase has no content hits
  - AC: `ak brain search "batch memory extraction"` returns results when files contain the words individually but not the exact phrase
  - AC: Files matching more individual words rank higher than files matching fewer

- MUST match the full phrase as a substring against index names and summaries
  - AC: `ak brain search "Hermes Agent"` matches an entity named "Hermes Agent" (score 3)
  - AC: Single-word terms behave identically to current behaviour

- MUST split multi-word terms into individual words for tag matching
  - AC: `ak brain search "terraform modules"` matches an entity tagged `terraform` (score 2)
  - AC: This applies even when the exact phrase also matches content (tags always split)

- MUST preserve existing behaviour for single-word terms
  - AC: All existing tests pass without modification

- SHOULD preserve existing scoring semantics for single-word terms
  - AC: Name/slug match = 3, tag match = 2, summary match = 1, content match = 1

## Design

### Stopword Filtering

When splitting a multi-word term into individual words, remove common stopwords before
matching. This prevents noise from words like "the", "for", "a" matching nearly every
file. Stopwords are only removed during word-splitting — exact phrase matches always use
the original string verbatim.

Stopword list: `a`, `an`, `the`, `and`, `or`, `but`, `in`, `on`, `at`, `to`, `for`,
`of`, `with`, `by`, `from`, `is`, `it`, `as`, `be`, `was`, `are`, `been`, `being`,
`have`, `has`, `had`, `do`, `does`, `did`, `will`, `would`, `could`, `should`, `may`,
`might`, `can`, `this`, `that`, `these`, `those`, `not`, `no`, `so`, `if`, `then`

If all words in a term are stopwords, skip filtering and use them all (degenerate case).

### Scoring

| Match type | Score | Matches | Notes |
|---|---|---|---|
| Name/slug (full phrase substring) | +3 | +1 | Unchanged |
| Tag (per word match) | +2 | +1 | Always split, stopwords removed |
| Summary (full phrase substring) | +1 | +1 | Unchanged |
| Content exact phrase (rg) | +3 | +word count | New — high-value match |
| Content individual word fallback (rg) | +1 | +1 per word | New — stopwords removed, per word that hits |

### Index phase logic (per term)

```
name/slug: match full term as substring (unchanged)
summary:   match full term as substring (unchanged)
tags:      split term into words, remove stopwords, match each word against each tag
```

Tag matching awards +2 once per entry (not per word) to avoid inflating scores for
entries with many tags.

### Content phase logic (per term)

```
if term contains spaces:
    words = remove_stopwords(term.split())
    hits = rg(exact phrase)
    if hits:
        score each hit +3, matches += len(words)
    else:
        for word in words:
            word_hits = rg(word)
            score each hit +1, matches += 1
else:
    hits = rg(term)
    score each hit +1, matches += 1  (unchanged)
```

Exact phrase matches increment `matches` by the word count (not 1). This ensures
the existing sort key `(-matches, -score)` correctly ranks a 3-word exact phrase
(matches=3, score=3) above a file matching only 2 of 3 individual words (matches=2,
score=2), and as a tiebreaker ranks exact phrase above all-words-individually
(matches=3, score=3 vs matches=3, score=3 — tie, but in practice exact phrase files
are unlikely to also appear in word fallback since fallback only runs when exact has
no hits).

### Files changed

- `src/agent_kit/brain/search.py` — `STOPWORDS` set and `_split_words()` helper
- `src/agent_kit/brain/client.py` — index tag matching + content search logic
- `tests/brain/test_client.py` — new test cases

## Milestones

1. Index phase: split tags for multi-word terms
   Approach:
   - Modify the inner loop in `BrainClient.search()` where tags are checked (around line 61)
   - Split the term on whitespace, remove stopwords, check each word against each tag
   - Award score +2 once per entry if any word matches any tag (not per-word)
   - Name and summary matching remain unchanged — full phrase substring
   - ⚠️ Tags can be non-string (int parsed by YAML) — existing `str(tag).lower()` coercion must be preserved
   - ⚠️ If all words are stopwords, skip filtering and use them all
   Tasks:
   - Add `STOPWORDS` set and `_split_words(term)` helper that splits and filters
   - Change tag matching to split multi-word terms into words (minus stopwords) before comparing
   - Add test: multi-word term with individual words matching tags scores 2
   - Add test: single-word term tag matching unchanged
   - Add test: stopwords are excluded from word list ("terraform module for vpc" → ["terraform", "module", "vpc"])
   Deliverable: Multi-word terms match against individual tags with stopwords removed
   Verify: `uv run pytest tests/brain/test_client.py::TestSearch -v` — new tag tests pass, existing tests pass

2. Content phase: exact phrase then word fallback
   Approach:
   - Modify the content search loop in `BrainClient.search()` (Phase 2 section, around line 80)
   - For multi-word terms: call `_rg_search` with the full phrase first
   - If hits: score +3 per hit, increment matches by word count (not 1) so sort key works correctly
   - If no hits: split into words using `_split_words` (stopwords removed), call `_rg_search` per word, score +1 per word-hit, matches +1 per word-hit
   - Single-word terms: unchanged (score +1 as before)
   - `_rg_search` itself needs no changes — it already accepts any query string
   - ⚠️ Excerpt extraction: for exact phrase matches, use the phrase for the excerpt. For word fallback, use the first matching word for the excerpt.
   Tasks:
   - Add conditional logic for multi-word terms in the content search loop
   - Score exact phrase hits at +3
   - Implement word-split fallback (with stopwords removed) with +1 per word
   - Add test: exact phrase in content scores 3
   - Add test: no exact phrase but individual words present triggers fallback, scores +1 per word
   - Add test: single-word content search unchanged (score 1)
   - Add test: exact phrase ranks above all-words-individually for same file count
   - Add test: stopwords not searched in fallback path
   Deliverable: Multi-word content searches return results via fallback when exact phrase isn't found
   Verify: `uv run pytest tests/brain/test_client.py::TestSearch -v` — all tests pass including new fallback tests
