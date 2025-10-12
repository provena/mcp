
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
