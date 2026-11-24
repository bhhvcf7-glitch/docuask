# Conversation memory

Apply Alembic migrations before use. POST /conversations creates a chat; GET /conversations lists up to 100 owned chats; GET /conversations/{id} returns up to 100 recent completed turns; DELETE removes the chat and its turns. All lookups use the authenticated owner. POST /qa/ask accepts optional conversation_id; omitting it preserves stateless compatibility.

The last six prior questions (at most 1000 characters each) are supplied to the configured LLM to rewrite follow-ups into a standalone search question. Earlier answers are not used as evidence. The existing retrieval and citation validation still run for every question. If the rewrite provider is unavailable, the original question is used. Only successful cited answers are persisted; refusals and failed requests are not. Historical answers are stored as text, not as live citations; they may outlive deletion of an original PDF. Delete the conversation to remove its stored text. The minimal UI maintains an active conversation until sign-out or New chat; the UI supports listing, opening and deleting historical chats. Concurrent asks are not serialized and may observe the same prior history. Semantic rewrite quality is not yet benchmarked.

See [measured retrieval results](eval/production-results.md) for evidence; follow-up rewriting quality is not separately measured.
