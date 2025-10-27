# Provena MCP Conversational Interface – Dev Log & Project Notes

## What was done

- Built a proof-of-concept (POC) conversational interface for Provena using Model Context Protocol (MCP) and LLMs.
- Implemented a terminal-based chatbot client that interacts with an MCP server exposing Provena tools.
- Enabled natural language workflows for searching and creating Provena records.
- Integrated OAuth authentication (browser-based flow) for secure access.
- Added debug mode for inspecting tool calls and API responses.
- Made the OpenAI model configurable via `.env`.

## Overall Progress

- POC is functional: users can interact with Provena via terminal chat, leveraging LLMs and MCP tools.
- Demonstrated reduction in friction for metadata management and research workflows.
- Example interactions and workflows are documented in the `examples/` folder.

## Challenges for Production

- **Multi-user support:**
  - Current POC stores tokens locally per user/session; not suitable for concurrent users or shared server deployments.
  - Would need a secure, scalable token/session management system for production.
- **Authentication:**
  - OAuth flow works for single-user POC, but production would require robust user management, token expiry handling, and possibly refresh tokens.
- **Server architecture:**
  - MCP server is single-process and not designed for high concurrency or cloud deployment.
  - Scaling to multiple users and integrating with Provena’s web platform would require architectural changes.
- **Security:**
  - Tokens are stored locally; production should use secure storage and follow best practices.
- **Integration:**
  - For full platform integration, a web-based chatbot UI and tighter coupling with Provena’s authentication and user management would be needed.

## Future Directions

- Integrate the conversational interface as a chatbot within the Provena web platform.
- Support multiple users, sessions, and secure token management.
- Enhance tool coverage and add more workflows.
- Improve error handling, logging, and monitoring for production use.
- Explore other LLMs and hosting options for scalability.

## Useful Links

- Provena documentation: https://docs.provena.io/
- Model Context Protocol docs: https://modelcontextprotocol.io/docs/getting-started/intro

## Notes & Shortcuts

- Debug mode (`python client/mcp_client.py dev`) shows all tool call and API response details.
- OpenAI model can be set in `.env` via `OPENAI_MODEL`.
- Example conversations are in the `examples/` folder.

## Summary

This POC demonstrates that conversational AI can significantly reduce friction in research metadata workflows. The next step is to move from terminal-based POC to a fully integrated, multi-user, secure chatbot experience within the Provena platform.
