# Sample Conversation: Dataset Registration via MCP

**You:** login  
`[Calling: login_to_provena({})]`  
`[Server log: Authentication completed successfully]`  
`[login_to_provena result]: { "status": "authenticated" }`

**AI:** You have been successfully authenticated. How can I assist you further?

---

**You:** I would like to register a dataset please  
`[Calling: get_prompt_dataset_registration_workflow({})]`

**AI:** I'm here to help you register a dataset! The process will involve collecting all required information first, then optional information, followed by a summary for your confirmation, and finally, I'll complete the registration.

Let’s get started with the required information.

---

**AI:** 1. What is the name of the dataset?  
**You:** MCP Usage

**AI:** 2. Please provide a detailed description of the dataset.  
**You:** Using MCP tools to register a dataset

**AI:** 3. Could you provide the publisher ID? (This must be an organization; I can help you search if you're unsure.)  
**You:** I forgot, it should be under hogwarts  
`[Calling: search_registry({'query': 'hogwarts', 'subtype_filter': 'ORGANISATION'})]`  
`[search_registry result: (1 match found, Hogwarts)]`

**AI:** 4. The publisher ID for Hogwarts is: [redacted]. Is that correct?  
**You:** this is hogwarts too

**AI:** 5. What is the created date for this dataset? (Please provide it in any common format, and I will convert it to YYYY-MM-DD.)  
**You:** todays date  
`[Calling: get_current_date({})]`  
`[get_current_date result]: "2025-09-29"`

**AI:** 6. The created date will be: 2025-09-29.

**AI:** 7. What is the published date for this dataset? (You can provide it in any common format as well.)  
**You:** today aswell  
**AI:** 8. The published date will be: 2025-09-29.

**AI:** 9. What is the license URI for this dataset? (e.g., https://creativecommons.org/licenses/by/4.0/)

**AI:** 10. Is the data reposited? (Answer with Yes or No.)  
**You:** yes it is  
**AI:** Since the data is reposited, we can skip the access URI and description.

**AI:** 11. Is ethics registration relevant to this dataset? (Answer with Yes or No.)  
**You:** no

**AI:** 12. Is ethics access relevant to this dataset? (Answer with Yes or No.)  
**You:** no

**AI:** 13. Is indigenous knowledge relevant to this dataset? (Answer with Yes or No.)  
**You:** no

**AI:** 14. Are export controls relevant to this dataset? (Answer with Yes or No.)  
**You:** no

**AI:** 15. What is the purpose of this dataset? (Please provide a brief explanation.)  
**You:** to see is MCP is useful

**AI:** 16. Who owns/manages the rights to this dataset?  
**You:** Harry Potter does

**AI:** 17. What are the usage limitations for this dataset? (Please provide any access or usage restrictions.)  
**You:** there are none

**AI:** 18. How would you like this dataset to be cited? (Please provide the preferred citation format.)  
**You:** No preference

**AI:** 19. Would you like to provide any spatial information? (Answer with Yes or No.)  
**You:** yes

**AI:** 20. What is the spatial coverage? (Please provide in EWKT format with SRID, e.g., SRID=4326;POINT(145.7 -16.2))  
**You:** SRID=4326;POLYGON((150.0 -35.0, 151.0 -35.0, 151.0 -34.0, 150.0 -34.0, 150.0 -35.0))

**AI:** 21. What is the spatial extent? (Provide in EWKT bbox polygon format)  
**You:** SRID=4326;POLYGON((145.0 -38.0, 153.0 -38.0, 153.0 -28.0, 145.0 -28.0, 145.0 -38.0))

**AI:** 22. What is the spatial resolution?  
**You:** 0.05

**AI:** 23. Would you like to provide any temporal information?  
**You:** yes

**AI:** 24. What is the temporal begin date?  
**You:** should be january the 14th of 2002  
**AI:** 25. The temporal begin date will be: 2002-01-14

**AI:** 26. What is the temporal end date?  
**You:** 2005 02 24  
**AI:** 27. The temporal end date will be: 2005-02-24

**AI:** 28. What is the temporal resolution?  
**You:** monthly, i forget the format of that  
**AI:** The ISO8601 format for monthly resolution is P1M.

**AI:** 29. What formats does this dataset have?  
**You:** json

**AI:** 30. What keywords would you like to associate with this dataset?  
**You:** cool fun and awesome and magical

**AI:** 31. Do you have any additional user metadata you would like to provide?  
**You:** Mainly just want some extra data for 'Testing' with the value of 'Using this to test formatting'  
**AI:** 32. The user metadata will be: `{"Testing": "Using this to test formatting"}`

**AI:** 33. Who is the data custodian?  
**You:** harry potter is  
`[Calling: search_registry({'query': 'harry potter', 'subtype_filter': 'PERSON'})]`  
`[search_registry result: (2 matches, selected Harry Potter)]`

**AI:** The data custodian ID for Harry Potter is: [redacted].

**AI:** 34. What are the point of contact details (e.g., email, phone number)?  
**You:** use harry potters email please  
**AI:** The point of contact details will be: [redacted email].

---

### Summary of Collected Information

- **Dataset Name:** MCP Usage  
- **Description:** Using MCP tools to register a dataset  
- **Publisher ID:** [redacted] (Hogwarts)  
- **Organisation ID:** [redacted] (Hogwarts)  
- **Created Date:** 2025-09-29  
- **Published Date:** 2025-09-29  
- **License:** https://creativecommons.org/licenses/by/4.0/  
- **Data Reposited:** Yes  
- **Ethics Registration Relevant:** No  
- **Ethics Access Relevant:** No  
- **Indigenous Knowledge Relevant:** No  
- **Export Controls Relevant:** No  
- **Purpose:** To see if MCP is useful  
- **Rights Holder:** Harry Potter  
- **Usage Limitations:** None  
- **Preferred Citation:** No preference  
- **Spatial Coverage:** SRID=4326;POLYGON((150.0 -35.0, 151.0 -35.0, 151.0 -34.0, 150.0 -34.0, 150.0 -35.0))  
- **Spatial Extent:** SRID=4326;POLYGON((145.0 -38.0, 153.0 -38.0, 153.0 -28.0, 145.0 -28.0, 145.0 -38.0))  
- **Spatial Resolution:** 0.05  
- **Temporal Begin Date:** 2002-01-14  
- **Temporal End Date:** 2005-02-24  
- **Temporal Resolution:** P1M  
- **Formats:** JSON  
- **Keywords:** cool, fun, awesome, magical  
- **User Metadata:** `{"Testing": "Using this to test formatting"}`  
- **Data Custodian ID:** [redacted] (Harry Potter)  
- **Point of Contact:** [redacted email]

---

**AI:** ### Do you confirm this information for dataset registration?  
**You:** yeah that looks good

`[Calling: register_dataset({...})]`  
`[Server log: Dataset registered successfully with ID: [redacted]]`

**AI:** The dataset "MCP Usage" has been registered successfully!  

- **Dataset ID:** [redacted]  
- **Handle URL:** https://hdl.handle.net/[redacted]




# Sample Conversation: User Registration via MCP

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


# Sample Conversation: Dataset Template Registration via MCP

**You:** I would like to register a dataset template

**AI:** You are a Provena dataset registration specialist. The process will involve the following steps:

1. Collect required information
2. Collect optional information
3. Provide a summary
4. Confirm the details
5. Register the dataset template

Let's start by gathering the required information.

---

**AI:** 1. What is the display name for this template?
**You:** Testing MCP Dataset Template

**AI:** 2. Do you have a description of what this template is for?
**You:** Using MCP Tools to test dataset template registry

**AI:** 3. Do you want to define any resources for this dataset template?
**You:**
data/sea_temp.nc — Main temperature netCDF file — Input — false — false — {"units":"°C", "source":"satellite"}

**AI:** It seems there was a little confusion in the format for defining resources. I'll structure it properly as a JSON string:

```json
[{"path": "data/sea_temp.nc", "description": "Main temperature netCDF file", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"units": "°C", "source": "satellite"}}]
```

---

**AI:** 4. Would you like to provide any deferred resources?
**You:** This is the information I would like bias_correction_file — A model-run specific bias correction file (path determined at run time) — Input — false — false — {"format":"csv"}

**AI:** Here’s how that looks as a structured JSON:

```json
[{"key": "bias_correction_file", "description": "A model-run specific bias correction file (path determined at run time)", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"format": "csv"}}]
```

---

### Resources Summary

**Defined Resources:**

* Path: `data/sea_temp.nc`
  Description: `Main temperature netCDF file`
  Usage Type: `GENERAL_DATA`
  Optional: `false`
  Is Folder: `false`
  User Metadata: `{"units": "°C", "source": "satellite"}`

**Deferred Resources:**

* Key: `bias_correction_file`
  Description: `A model-run specific bias correction file (path determined at run time)`
  Usage Type: `GENERAL_DATA`
  Optional: `false`
  Is Folder: `false`
  User Metadata: `{"format": "csv"}`

---

**AI:** 5. Do you want to provide any additional key-value metadata?
**You:** Just testing this — author — harry potter

**AI:** Got it. User metadata:

```json
{"author": "harry potter"}
```

---

### Summary of Collected Information

* **Display Name:** Testing MCP Dataset Template
* **Description:** Using MCP Tools to test dataset template registry
* **Defined Resources:**

  ```json
  [{"path": "data/sea_temp.nc", "description": "Main temperature netCDF file", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"units": "°C", "source": "satellite"}}]
  ```
* **Deferred Resources:**

  ```json
  [{"key": "bias_correction_file", "description": "A model-run specific bias correction file (path determined at run time)", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"format": "csv"}}]
  ```
* **User Metadata:**

  ```json
  {"author": "harry potter"}
  ```

---

**AI:** Do you confirm that all of the above information is correct?
**You:** that looks good

**[Confirmation Required]**
You are about to call `create_dataset_template` with the following arguments:

```json
{
  "display_name": "Testing MCP Dataset Template",
  "description": "Using MCP Tools to test dataset template registry",
  "defined_resources": "[{\"path\": \"data/sea_temp.nc\", \"description\": \"Main temperature netCDF file\", \"usage_type\": \"GENERAL_DATA\", \"optional\": false, \"is_folder\": false, \"user_metadata\": {\"units\": \"°C\", \"source\": \"satellite\"}}]",
  "deferred_resources": "[{\"key\": \"bias_correction_file\", \"description\": \"A model-run specific bias correction file (path determined at run time)\", \"usage_type\": \"GENERAL_DATA\", \"optional\": false, \"is_folder\": false, \"user_metadata\": {\"format\": \"csv\"}}]",
  "user_metadata": "{\"author\": \"harry potter\"}"
}
```

**You:** yes

---

**AI:** The dataset template **"Testing MCP Dataset Template"** has been registered successfully!
You can access it here: [https://hdl.handle.net/[redacted]/[redacted]](https://hdl.handle.net/[redacted]/[redacted]).
