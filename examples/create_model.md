# Sample Conversation: Model Registration

**You:** I would like to register a model
`[Calling: get_prompt_other_registration_workflow({})]`

**AI:** You're logged in and ready to register a model. Here's what we'll do:

1. Collect required model information.
2. Collect any optional fields.
3. Review and confirm everything.
4. Proceed with registration.

---

**AI:** 1. **Model Name:** What is the name of the software model?
**You:** Testing MCP Model
**AI:** 2. **Model Description:** Please provide a short description.
**You:** This model is being made to test MCP tools
**AI:** 3. **Documentation URL:** Provide a full URL to the model documentation.
**You:** just use http:/example.com for testing
**AI:** 4. **Source URL:** Please provide the URL to the source code or repository.
**You:** same as documentation
**AI:** 5. **Display Name (optional):** What display name should be shown for this model?
**You:** MCP Model
**AI:** 6. **User Metadata (optional):** Any extra key-value metadata in JSON format?
**You:** lets just do author as harry potter

---

### Summary of Collected Information

* **Model Name:** Testing MCP Model
* **Description:** This model is being made to test MCP tools
* **Documentation URL:** [http://example.com](http://example.com)
* **Source URL:** [http://example.com](http://example.com)
* **Display Name:** MCP Model
* **User Metadata:** {"author": "harry potter"}

---

**AI:** Do you confirm this information and wish to register the model?
**You:** that looks good

**[Confirmation Required]**
You are about to call `create_model` with the following arguments:

```json
{
  "name": "Testing MCP Model",
  "description": "This model is being made to test MCP tools.",
  "documentation_url": "http://example.com",
  "source_url": "http://example.com",
  "display_name": "MCP Model",
  "user_metadata": "{\"author\": \"harry potter\"}"
}
```

**You:** yes

**AI:** The model **"Testing MCP Model"** has been registered successfully!
You can view it here: [https://hdl.handle.net/[redacted]/[redacted]}](https://hdl.handle.net/[redacted]/[redacted])

