# Literature Mapping skill

Generate or review a literature mapping entry for a research paper — the
structured content that fills the Literature Map table's Research Objective /
Methodology & Sample / Key Findings / Limitations & Gaps / Relevance columns.
Use whenever you are asked to literature-map a paper, build a literature review
matrix, or summarize a paper into the review table.

One row per paper, one entry per paper. The table columns and the JSON keys
they map to:

| Key (JSON)            | Table column                | Meaning                                                                 |
| --------------------- | --------------------------- | ----------------------------------------------------------------------- |
| `research_objective`  | Research Objective / Questions | The paper's primary purpose, research question or hypothesis.         |
| `methodology`         | Methodology & Sample        | Research design, data sources, sample size/demographics, analysis approach. |
| `key_findings`        | Key Findings                | Main empirical or theoretical conclusions.                              |
| `limitations`         | Limitations & Gaps          | Constrained samples, bias, scope limits, unaddressed variables.         |
| `relevance`           | Relevance / Contribution    | How this study could inform the researcher's own work (supports a method, contradicts a theory, provides context). |

`citation` (Author, Year) and `apa_reference` (APA 7th) are optional extras —
include them when asked; otherwise they are derived from the paper metadata.

## Output contract

Reply with STRICT JSON only: a single JSON object, no markdown code fences, no
prose before or after, no keys beyond the ones specified.

```json
{
  "research_objective": "...",
  "methodology": "...",
  "key_findings": "...",
  "limitations": "...",
  "relevance": "..."
}
```

## Rules

1. Every value must be 2-4 sentences, grounded in the paper's title, abstract
   and excerpts. Do not invent facts, numbers, sample sizes, or authors.
2. Never leave a field empty. If the paper is silent on a field, write
   `Not stated in the paper.`
3. No markdown code fences, no commentary, no extra keys — a stray fence or
   trailing sentence is the top cause of the table staying blank.
4. If the paper provides no abstract or excerpts, base the fields on the title
   alone and mark the rest `Not stated in the paper.`
5. `key_findings` must be conclusions, not a restatement of the objective.
6. For multiple papers, return one JSON object per paper (or a JSON array with
   an `id`/`title` key per object when the caller asks for a batch).

## Citation Rules (APA 7th Edition)

When generating summaries, reviews, or analyses of papers, follow these citation rules:

1. Every factual claim, finding, or assertion MUST include a parenthetical citation:
   - Single author: (Author, Year)
   - Two authors: (Author1 & Author2, Year)
   - Three+ authors: (Author1 et al., Year)
   - Specific page: (Author, Year, p. X)
2. Multiple sources for one claim: (Author1, Year1; Author2, Year2)
3. No author available: ("Short Title", Year)
4. No date available: (Author, n.d.)
5. Every summary MUST end with a References section listing all cited works alphabetically.
6. Reference format for articles: Author, A. A., & Author, B. B. (Year). Title of article. *Title of Periodical*, volume(issue), pages. https://doi.org/xxxxx
7. Reference format for books: Author, A. A. (Year). *Title of work: Capital letter also for subtitle*. Publisher. https://doi.org/xxxxx
8. Never invent page numbers, authors, DOIs, or years not present in the provided context.
9. In-text citations must correspond to a full reference entry.

## Example

For "Attention Is All You Need", a good entry is:

```json
{
  "research_objective": "To replace recurrent and convolutional sequence models with a purely attention-based architecture, testing whether self-attention alone is sufficient for state-of-the-art machine translation (Vaswani et al., 2017).",
  "methodology": "Proposes the Transformer, built on multi-head self-attention and position-wise feed-forward layers, trained on WMT 2014 English-to-German and English-to-French translation tasks (Vaswani et al., 2017).",
  "key_findings": "The Transformer reaches BLEU scores of 28.4 on English-to-German and 41.8 on English-to-French, outperforming previous ensembles while training significantly faster and in parallel (Vaswani et al., 2017).",
  "limitations": "Not stated in the paper.",
  "relevance": "Provides the architectural basis for most modern LLM training regimes; useful as a methodological baseline and a citation anchor for transformer-based work."
}
```

## Verifying before you finish

- The output parses as JSON (no fences, no prose).
- All requested keys are present and non-empty.
- Each field is grounded in the source text given to you.
- The keys exactly match the table column keys above.
- Every factual claim includes a proper parenthetical citation.
