# Sample Conversation: Organisation Registration via MCP

**You:** I would like to register a new organization please  
**AI:** I will help you register a new organization in the Provena registry. The process involves collecting the required information first, then optional information if applicable, summarizing everything for you, and finally getting your confirmation before registration.

Let's start with the required information:

1. **What is the name of the organization?**  

**You:** MCP Org

**AI:** 2. **What is the display name of the organization?** (This is optional; if you want it to be the same as the name, you can just say "same".)  
**You:** same

**AI:** 3. **What is the ROR (Research Organizational Registry) ID or URL for the organization?** (This is also optional; if you don't have one, you can skip it.)  
**You:** skip

**AI:** 4. **Do you have any additional metadata you would like to provide?** (This is optional; please specify if you have any additional information.)  
**You:** testkey - testvalue

**AI:** Here's a summary of the information collected for your organization registration:

- **Name:** MCP Org 
- **Display Name:** MCP Org (same as name)  
- **ROR:** None  
- **User Metadata:** {"testkey": "testvalue"}

Please confirm that this information is correct and that you would like to proceed with the registration.

**You:** yes

**[Confirmation Required]**  
You are about to call `create_organisation` with the following arguments:

```json
{
  "name": "MCP Org",
  "display_name": "MCP Org",
  "ror": null,
  "user_metadata": {
    "testkey": "testvalue"
  }
}
```

**You:** yes

**AI:** The organization "MCP Org" has been registered successfully!  
You can access it using the following ID: [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted]).

---

