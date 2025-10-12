
# Sample Conversation: Model Run Workflow Template Registration via MCP - Using exising templates and models

**You:** I want to register a model run workflow template

---

**AI:** It looks like you're not currently logged in to Provena. You'll need to log in to proceed with registering a Model Run Workflow Template.

Would you like me to help you with the login process?

**You:** login

**AI:** You're now logged in successfully!

I'll help you register a Model Run Workflow Template.

A workflow template defines the inputs, outputs, and structure for model run activities. The process involves identifying or creating a model, identifying or creating dataset templates, defining annotations, and then moving to summary, confirmation, and registration.

First, do you have an existing model registered, or do you need to create a new one?

**You:** Existing one

**AI:** Could you please provide the model name or any relevant keywords so I can search for the existing model?

**You:** MCP testing

**AI:** I found several existing models related to your search for "MCP testing." Here are the details:

1. **MCP Model**

   * ID: [redacted]
   * Description: This model is being made to test MCP tools.
   * Documentation: [Link](http://example.com/)

2. **MCP Model Run Model**

   * ID: [redacted]
   * Description: This model is for testing MCP model run.
   * Documentation: [Link](http://example.com/documentation)

3. **Test Model for MCP Model Run**

   * ID: [redacted]
   * Description: This model is for testing the MCP model run template tool.
   * Documentation: [Link](https://example.com/documentation)

4. **MCP Test Model**

   * ID: [redacted]
   * Description: This model is for testing MCP.
   * Documentation: [Link](http://example.com/)

5. **MCP Model for Model Run**

   * ID: [redacted]
   * Description: Testing MCP tools to create a model run workflow template.
   * Documentation: [Link](https://example.com/)

Please select one of the models by specifying its ID, or let me know if you need more information on any of them.

**You:** do model 1 please

**AI:** You've selected the following model for your workflow template:

* **Model Name:** Testing MCP Model
* **Display Name:** MCP Model
* **ID:** [redacted]
* **Description:** This model is being made to test MCP tools.
* **Documentation:** [Link](http://example.com/)

Next, do you need to specify input datasets for your model? If yes, I will guide you through identifying or creating input dataset templates. Would you like to proceed?

**You:** yes please - use an existing one

**AI:** Do you have a specific name or keywords for the input dataset template you're looking for, or should I search for any existing dataset templates?

**You:** MCP

**AI:** I found one existing dataset template related to your search for "MCP":

* **Display Name:** Testing MCP Dataset Template
* **ID:** [redacted]
* **Description:** Using MCP Tools to test dataset template registry.
* **Defined Resources:**

  * **Path:** data/sea_temp.nc

    * **Description:** Main temperature netCDF file
    * **Usage Type:** General Data
    * **Optional:** No
* **Deferred Resources:**

  * **Key:** bias_correction_file

    * **Description:** A model-run specific bias correction file (path determined at run time)
    * **Optional:** No

Would you like to proceed with this dataset template as an input for your workflow template?

**You:** yes please

**AI:** You've chosen the following dataset template for your workflow:

* **Dataset Template Name:** Testing MCP Dataset Template
* **ID:** [redacted]
* **Description:** Using MCP Tools to test dataset template registry.
* **Defined Resources:**

  * **Path:** data/sea_temp.nc

    * **Description:** Main temperature netCDF file
    * **Usage Type:** General Data
    * **Optional:** No
* **Deferred Resources:**

  * **Key:** bias_correction_file

    * **Description:** A model-run specific bias correction file (path determined at run time)
    * **Optional:** No

Next, do you want to specify any additional output datasets from your model? If so, I can help you identify or create output dataset templates as needed. Would you like to proceed?

**You:** yes please, an existing one

**AI:** Do you have a specific name or keywords for the output dataset template you're looking for, or should I search for any existing output dataset templates?

**You:** MCP

**AI:** It appears that the same dataset template, "Testing MCP Dataset Template," is listed for both inputs and outputs. Here are the details again:

* **Dataset Template Name:** Testing MCP Dataset Template
* **ID:** [redacted]
* **Description:** Using MCP Tools to test dataset template registry.
* **Defined Resources:**

  * **Path:** data/sea_temp.nc

    * **Description:** Main temperature netCDF file
    * **Usage Type:** General Data
    * **Optional:** No
* **Deferred Resources:**

  * **Key:** bias_correction_file

    * **Description:** A model-run specific bias correction file (path determined at run time)
    * **Optional:** No

Would you like to use this same dataset template for the output as well?

**You:** yes

**AI:** You have chosen to use the same dataset template for both input and output in your workflow. Here are the details:

### Input Dataset Template

* **Dataset Template Name:** Testing MCP Dataset Template
* **ID:** [redacted]
* **Description:** Using MCP Tools to test dataset template registry.
* **Defined Resources:**

  * **Path:** data/sea_temp.nc

    * **Description:** Main temperature netCDF file
    * **Usage Type:** General Data
    * **Optional:** No
* **Deferred Resources:**

  * **Key:** bias_correction_file

    * **Description:** A model-run specific bias correction file (path determined at run time)
    * **Optional:** No

### Output Dataset Template

* **Dataset Template Name:** Testing MCP Dataset Template
* **ID:** [redacted]
* **Description:** Using MCP Tools to test dataset template registry.
* **Defined Resources:**

  * **Path:** data/sea_temp.nc

    * **Description:** Main temperature netCDF file
    * **Usage Type:** General Data
    * **Optional:** No
* **Deferred Resources:**

  * **Key:** bias_correction_file

    * **Description:** A model-run specific bias correction file (path determined at run time)
    * **Optional:** No

Next, do you want to specify any required annotations for model runs? Required annotations are metadata keys that MUST be provided when someone registers a model run using this template. Would you like to add any?

**You:** Yes please

**AI:** Please provide the required annotation keys as a comma-separated list (e.g., "experiment_id, run_configuration"). These annotations will be mandatory for anyone registering a model run using this template.

**You:** experiment_id

**AI:** You have specified the following required annotation:

* **Required Annotation Key:** experiment_id

Next, would you like to specify any optional annotations as well? Optional annotations are metadata keys that MAY be provided when someone registers a model run. Would you like to add any?

**You:** same as before

**AI:** Please provide the optional annotation keys as a comma-separated list. These will be optional metadata keys for anyone registering a model run using this template. If you want the same as before, please confirm the key to use, or provide new ones if necessary.

**You:** just use experiment_optional_id

**AI:** You have specified the following optional annotation:

* **Optional Annotation Key:** experiment_optional_id

Now, do you want to add any custom metadata to this workflow template? If yes, please provide it in a JSON object format. If not, let me know, and I can proceed to summarize all the information collected so far.

**You:** yeah - just do test metadata as testing

**AI:** You have added the following custom metadata:

```json
{
  "test": "testing"
}
```

---

### Summary of Collected Information

* **Display Name:** Model Run Workflow Template
* **Model ID:** [redacted] (Testing MCP Model)
* **Input Template:**

  * **ID:** [redacted] (Testing MCP Dataset Template, Optional: No)
* **Output Template:**

  * **ID:** [redacted] (Testing MCP Dataset Template, Optional: No)
* **Required Annotations:** experiment_id
* **Optional Annotations:** experiment_optional_id
* **Custom Metadata:** {"test": "testing"}

---

**AI:** Does this look correct? Please confirm by typing 'yes' to proceed with the registration, or let me know if you need to make any changes.

**You:** That looks good

**AI:** Your Model Run Workflow Template has been registered successfully! Here are the details:

* **Display Name:** Model Run Workflow Template
* **Model ID:** [redacted] (Testing MCP Model)
* **Input Templates Count:** 1
* **Output Templates Count:** 1
* **Has Annotations:** Yes

You can access the registered workflow template using the following link: [Model Run Workflow Template](https://hdl.handle.net/[redacted]).

If you need any further assistance or have other tasks, feel free to ask.

Here’s the conversation formatted into **Markdown** for documentation (same style as the previous one):

---

# Sample Conversation: Model Run Workflow Template Registration via MCP

**You:** I want to register a new model run workflow template

**AI:** You're authenticated and ready to proceed with registering a Model Run Workflow Template!

A workflow template defines the inputs, outputs, and structure for model run activities. The process will involve identifying or creating a model, identifying or creating dataset templates, defining annotations, and finally registering the workflow template.

Now, let's begin.

**Do you have an existing model registered, or do you need to create a new one?**

**You:** create one

**AI:** Let's create the model! I'll need to collect some information first.

1. **What is the name of the model?**

**You:** MCP Test Model v2

**AI:** Great! The name of the model is "MCP Test Model v2."

Next, could you please provide a **description of the model**?

**You:** This model is for testing the model run workflow template tool

**AI:** Thank you! The description of the model is: "This model is for testing the model run workflow template tool."

Now, could you provide the **documentation URL for the model**?

**You:** [https://example.com](https://example.com)

**AI:** Got it! The documentation URL is: [https://example.com](https://example.com).

Next, please provide the **source URL for the model**.

**You:** [https://example.com](https://example.com)

**AI:** Thank you! The source URL is: [https://example.com](https://example.com).

Next, do you have a **display name** that you'd like to set for the model? (This is optional and will default to the model's name if not provided.)

**You:** MCP Model V2

**AI:** The display name for the model is set to "MCP Model V2."

Lastly, do you have any **user metadata** to add in JSON format? (This is also optional.)

**You:** no thank you

**AI:** No user metadata will be added.

Here's a summary of the information collected for the model:

* **Name:** MCP Test Model v2
* **Description:** This model is for testing the model run workflow template tool.
* **Documentation URL:** [https://example.com](https://example.com)
* **Source URL:** [https://example.com](https://example.com)
* **Display Name:** MCP Model V2

**Does this look correct?**

**You:** looks good

**[Confirmation Required]**
You are about to call `create_model` with the following arguments:

```json
{
  "name": "MCP Test Model v2",
  "description": "This model is for testing the model run workflow template tool.",
  "documentation_url": "https://example.com",
  "source_url": "https://example.com",
  "display_name": "MCP Model V2"
}
```

**You:** yes

**AI:** The model "MCP Test Model v2" has been registered successfully!

* **Model ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])

---

**AI:** Now that the model is created, we'll proceed with the workflow template registration.

**Does your model require input datasets?**

**You:** Yes

**AI:** For each input dataset, I need to know whether you have an existing dataset template or if you need to create a new one.

**Do you have an existing dataset template, or do you want to create a new one?**

**You:** Create one

**AI:** Let's create the dataset template!

1. **What is the display name for the dataset template?**

**You:** MCP Input Template v2

**AI:** The display name for the dataset template is "MCP Input Template v2."

**(Optional) Would you like to provide a description for this dataset template?**

**You:** This template is for creating an input template for the model run workflow template tool

**AI:** Thank you! The description of the dataset template is: "This template is for creating an input template for the model run workflow template tool."

Now, let's define the resources for the dataset. Please provide the first resource with the following details:

**You:** [{"path": "data/sea_temp.nc", "description": "Main temperature netCDF file", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"units": "°C", "source": "satellite"}}]

**AI:** Here's the first resource:

* **Path:** data/sea_temp.nc
* **Description:** Main temperature netCDF file
* **Usage Type:** GENERAL_DATA
* **Optional:** false
* **Is Folder:** false
* **User Metadata:**

  * Units: °C
  * Source: satellite

Would you like to add another resource?

**You:** no

**AI:** No additional resources will be added.

Now, let's move on to the **deferred resources**.

**You:** [{"key": "bias_correction_file", "description": "A model-run specific bias correction file (path determined at run time)", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"format": "csv"}}]

**AI:** Deferred resource details:

* **Key:** bias_correction_file
* **Description:** A model-run specific bias correction file (path determined at run time)
* **Usage Type:** GENERAL_DATA
* **Optional:** false
* **Is Folder:** false
* **User Metadata:**

  * Format: csv

Would you like to add another deferred resource?

**You:** no

**AI:** No additional deferred resources will be added.

Do you want to add any custom metadata?

**You:** no

**AI:** No custom metadata will be added.

Here's a complete summary of the input dataset template:

* **Display Name:** MCP Input Template v2
* **Description:** This template is for creating an input template for the model run workflow template tool.
* **Defined Resources:**

  * **Path:** data/sea_temp.nc
  * **Description:** Main temperature netCDF file
  * **Usage Type:** GENERAL_DATA
  * **Optional:** false
  * **Is Folder:** false
  * **User Metadata:**

    * Units: °C
    * Source: satellite
* **Deferred Resources:**

  * **Key:** bias_correction_file
  * **Description:** A model-run specific bias correction file
  * **Usage Type:** GENERAL_DATA
  * **Optional:** false
  * **Is Folder:** false
  * **User Metadata:**

    * Format: csv

**Does this look correct?**

**You:** yes

**[Confirmation Required]**
You are about to call `create_dataset_template` with the following arguments:

```json
{
  "display_name": "MCP Input Template v2",
  "description": "This template is for creating an input template for the model run workflow template tool.",
  "defined_resources": "[{\"path\": \"data/sea_temp.nc\", \"description\": \"Main temperature netCDF file\", \"usage_type\": \"GENERAL_DATA\", \"optional\": false, \"is_folder\": false, \"user_metadata\": {\"units\": \"°C\", \"source\": \"satellite\"}}]",
  "deferred_resources": "[{\"key\": \"bias_correction_file\", \"description\": \"A model-run specific bias correction file (path determined at run time)\", \"usage_type\": \"GENERAL_DATA\", \"optional\": false, \"is_folder\": false, \"user_metadata\": {\"format\": \"csv\"}}]"
}
```

**You:** yes

**AI:** The dataset template "MCP Input Template v2" has been registered successfully!

* **Template ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])

---

**AI:** Does your model require any output datasets?

**You:** Yes

**AI:** Do you have an existing dataset template for the output, or do you want to create a new one?

**You:** Create a new one

**AI:** Let's create the output dataset template!

1. **What is the display name for the dataset template?**

**You:** MCP Output Template v2

**AI:** Display name set to "MCP Output Template v2."

**(Optional) Description?**

**You:** This template is for the output template to test the model run workflow template MCP tool

**AI:** Description set.

Define output resources:

**You:** [{"path": "data/sea_temp.nc", "description": "Main temperature netCDF file", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"units": "°C", "source": "satellite"}}]

**AI:** Output resource details:

* **Path:** data/sea_temp.nc
* **Description:** Main temperature netCDF file
* **Usage Type:** GENERAL_DATA
* **Optional:** false
* **Is Folder:** false
* **User Metadata:**

  * Units: °C
  * Source: satellite

**You:** no

**AI:** No additional resources will be added.

Deferred output resources:

**You:** [{"key": "bias_correction_file", "description": "A model-run specific bias correction file (path determined at run time)", "usage_type": "GENERAL_DATA", "optional": false, "is_folder": false, "user_metadata": {"format": "csv"}}]

**AI:** Deferred resource details:

* **Key:** bias_correction_file
* **Description:** A model-run specific bias correction file
* **Usage Type:** GENERAL_DATA
* **Optional:** false
* **Is Folder:** false
* **User Metadata:**

  * Format: csv

**You:** no

**AI:** No additional deferred resources will be added.

Custom metadata?

**You:** no

**AI:** None added.

Complete summary of output dataset template:

* **Display Name:** MCP Output Template v2
* **Description:** This template is for the output template to test the model run workflow template MCP tool.
* **Defined Resources:**

  * **Path:** data/sea_temp.nc
  * **Description:** Main temperature netCDF file
  * **Usage Type:** GENERAL_DATA
  * **Optional:** false
  * **Is Folder:** false
  * **User Metadata:**

    * Units: °C
    * Source: satellite
* **Deferred Resources:**

  * **Key:** bias_correction_file
  * **Description:** A model-run specific bias correction file
  * **Usage Type:** GENERAL_DATA
  * **Optional:** false
  * **Is Folder:** false
  * **User Metadata:**

    * Format: csv

**Does this look correct?**

**You:** looks good

**[Confirmation Required]**
You are about to call `create_dataset_template` with the following arguments:

```json
{
  "display_name": "MCP Output Template v2",
  "description": "This template is for the output template to test the model run workflow template MCP tool.",
  "defined_resources": "[{\"path\": \"data/sea_temp.nc\", \"description\": \"Main temperature netCDF file\", \"usage_type\": \"GENERAL_DATA\", \"optional\": false, \"is_folder\": false, \"user_metadata\": {\"units\": \"°C\", \"source\": \"satellite\"}}]",
  "deferred_resources": "[{\"key\": \"bias_correction_file\", \"description\": \"A model-run specific bias correction file (path determined at run time)\", \"usage_type\": \"GENERAL_DATA\", \"optional\": false, \"is_folder\": false, \"user_metadata\": {\"format\": \"csv\"}}]"
}
```

**You:** yes

**AI:** Dataset template "MCP Output Template v2" registered successfully!

* **Template ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])

---

**AI:** To recap:

* **Model ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])
* **Input Template ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])
* **Output Template ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])

**Do you want to specify required annotations for model runs?**

**You:** experiment_test_id

**AI:** Required annotation set to **experiment_test_id**.

Optional annotations?

**You:** use experiment_optional_test_id

**AI:** Optional annotation set to **experiment_optional_test_id**.

Custom metadata?

**You:** no

**AI:** None added.

Complete summary of Model Run Workflow Template:

* **Display Name:** MCP Model V2 Workflow
* **Model ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])
* **Input Template ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])
* **Output Template ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])
* **Required Annotations:** experiment_test_id
* **Optional Annotations:** experiment_optional_test_id

**Does this look correct?**

**You:** yes

**[Confirmation Required]**
You are about to call `create_model_run_workflow_template` with the following arguments:

```json
{
  "display_name": "MCP Model V2 Workflow",
  "model_id": "[redacted]",
  "input_template_ids": "[{\"template_id\": \"[redacted]", \"optional\": false}]",
  "output_template_ids": "[{\"template_id\": \"[redacted]\", \"optional\": false}]",
  "required_annotations": "experiment_test_id",
  "optional_annotations": "experiment_optional_test_id",
  "user_metadata": null
}
```

**You:** yes

**AI:** Model Run Workflow Template "MCP Model V2 Workflow" has been registered successfully!

* **Workflow Template ID:** [https://hdl.handle.net/[redacted]](https://hdl.handle.net/[redacted])
* **Input Templates Count:** 1
* **Output Templates Count:** 1
* **Required Annotations:** experiment_test_id
* **Optional Annotations:** experiment_optional_test_id

---
=