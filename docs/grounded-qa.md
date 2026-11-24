# Grounded QA citation validation

The retrieval gate continues to use cosine similarity, not RRF or cross-encoder logits. Only ready, owner-authorized chunks are available to the model. The model is instructed to write one factual claim per line and end each claim with source numbers. The server buffers the full provider response, limits raw characters (including invalid references), rejects invalid or unfinished citation markers, and requires each line/sentence to end in a valid reference and contain claim text. It refuses rather than silently stripping an invalid reference and presenting the remaining claim. Source mappings are server-controlled.

Token delivery is buffered: first visible text arrives after generation and structural validation. Provider failures and truncated streams do not release partial answer text. This trades time to first token for safer output. The sentence splitter is heuristic and can over-refuse abbreviations and complex formatting. A valid citation is NOT proof that the cited passage entails the claim; semantic verification and real answer-quality evaluation remain future work. The existing synthetic retrieval corpus is not an answer-grounding benchmark.

Tests cover valid bilingual references, uncited trailing sentences, invented citations, incomplete references, raw size limits and source mappings.

## Citation syntax

Individual numbers, comma groups, ascending ranges and Arabic-Indic digits are accepted, including [1, 2], [1–3] and [١،٢]. The server normalizes them to consecutive ASCII markers. Every number must belong to the retrieved source set. A malformed group, leading zero, unmatched bracket or out-of-set number refuses the complete answer. Numeric bracketed prose may be conservatively rejected. The citation payload format is unchanged.


## Generation progress

After retrieval passes the gate, the API emits generating with an empty JSON object before reading provider output. The browser distinguishes search from generation. No model text is included in progress events. The generation deadline (QA_GENERATION_TIMEOUT_SECONDS, default 180 seconds) covers provider iteration, not retrieval, follow-up rewriting or database persistence. Timeout emits error and discards buffered text. The provider is closed on cancellation; HTTP provider cancellation does not guarantee remote computation stops. Conversation answers remain buffered until persistence succeeds. The browser reports unexpected stream termination rather than treating it as success.
