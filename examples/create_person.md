# Sample Conversation: Person Registration via MCP

**You:** login  
`[Calling: login_to_provena({})]`  
`[Server log: Authentication completed successfully]`  
`[login_to_provena result]: { "status": "authenticated" }`

**AI:** You have been successfully authenticated. How can I assist you further?

---

**You:** I would like to register a user  
`[Calling: get_prompt_other_registration_workflow({})]`

**AI:** Hello! I'm here to help you register a user in the Provena system. The process will involve collecting some required information, optional information if available, providing a summary of everything we've collected, and finally getting your confirmation before proceeding with the registration.

Let's start with the required fields:

---

**AI:** 1. What is the user's first name?  
**You:** MCP  
**AI:** Great! The user's first name is MCP.

**AI:** 2. What is the user's last name?  
**You:** Robot  
**AI:** Thank you! The user's last name is Robot.

**AI:** 3. What is the user's contact email?  
**You:** mcprobot@botmail.com 
**AI:** Got it! The user's email is mcprobot@botmail.com.

**AI:** 4. Would you like to provide a display name for the user? This field is optional and defaults to the combination of the first and last name.

**You:** use default  

**AI:** Understood! I'll use the default display name, which will be "MCP Robot."

**AI:** 5. Does the user have an ORCID iD?  
**You:** skip  
**AI:** Alright, we'll skip the ORCID field.

**AI:** 6. Is the user ethics approved for the registry? (default is True)  
**You:** yes  
**AI:** Great! The user is ethics approved for the registry.

**AI:** 7. Would you like to include any additional metadata?  
**You:** mcpbotversion - v9000

**AI:** Thank you! I've noted the additional metadata: `{"mcpbotversion": "v9000"}`

---

### Summary of Collected Information

- **First Name:** MCP  
- **Last Name:** Robot  
- **Email:** mcprobot@botmail.com
- **Display Name:** MCP Robot (default)
- **ORCID:** None 
- **Ethics Approved:** Yes  
- **User Metadata:** `{"mcpbotversion": "v9000"}`

---

**AI:** Do you confirm this information for user registration?  
**You:** looks good  

**[Confirmation Required]**  
You are about to call `create_person` with the following arguments:

```json
{
  "first_name": "MCP",
  "last_name": "Robot",
  "email": "mcprobot@botmail.com",
  "display_name": "MCP Robot",
  "orcid": null,
  "ethics_approved": true,
  "user_metadata": {
    "mcpbotversion": "v9000"
  }
}
```

**You:** yes

**AI:** The user "MCP Robot" has been registered successfully! Here are the details:
- **Person ID:** 10378.1/1985046
- **Link to Profile:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])


