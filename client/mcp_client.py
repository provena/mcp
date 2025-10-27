import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from fastmcp import Client

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Default to gpt-4o-mini if not set

# Debug mode flag - set to True if 'dev' is in arguments
DEBUG_MODE = "dev" in sys.argv

def requires_confirmation(tool_name: str) -> bool:
    """Any tool beginning with 'create' requires confirmation."""
    return tool_name.lower().startswith("create")

if not OPENAI_API_KEY:
    raise SystemExit("Set OPENAI_API_KEY in your .env file.")

def extract_tool_result(result):
    """Extract data from FastMCP tool result"""
    if hasattr(result, 'data'):
        return result.data
    elif hasattr(result, 'structured_content'):
        return result.structured_content
    elif hasattr(result, 'content') and result.content and hasattr(result.content[0], 'text'):
        try:
            return json.loads(result.content[0].text)
        except:
            return {"error": "Failed to parse response"}
    else:
        return {"error": f"Unknown result format: {type(result)}"}

def extract_prompt_result(result):
    """Extract content from FastMCP prompt result"""
    if hasattr(result, 'messages') and result.messages:
        # Return the content of the first message
        return result.messages[0].content.text if hasattr(result.messages[0].content, 'text') else str(result.messages[0].content)
    elif hasattr(result, 'content'):
        return result.content
    else:
        return str(result)

def safe_get_parameters(item):
    """Safely extract parameters as an object"""
    if hasattr(item, 'inputSchema'):
        schema = item.inputSchema
        if isinstance(schema, dict):
            return schema
        elif isinstance(schema, list):
            # Convert array to object format
            return {"type": "object", "properties": {}}
    elif hasattr(item, 'arguments'):
        args = item.arguments
        if isinstance(args, dict):
            return args
        elif isinstance(args, list):
            # Convert array to object format
            return {"type": "object", "properties": {}}
    
    # Default safe object
    return {"type": "object", "properties": {}}

async def check_auth_status(client):
    """Simple auth status check"""
    try:
        result = await client.call_tool("check_authentication_status", {})
        data = extract_tool_result(result)
        return data.get("authenticated", False)
    except Exception:
        return False

async def ai_chat_loop():
    async with Client("http://127.0.0.1:5000/sse") as client:
        # Get both tools and prompts
        tools = await client.list_tools()
        prompts = await client.list_prompts()
        
        # Minimal startup message only
        print(f"Provena MCP Chat Client started.")
        if DEBUG_MODE:
            print(f"Using OpenAI model: {MODEL}")

        # Convert tools to OpenAI format
        openai_tools = []
        for t in tools:
            tool_def = {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": safe_get_parameters(t)
                }
            }
            openai_tools.append(tool_def)

        # Add prompt tools (prompts become callable functions)
        for p in prompts:
            prompt_tool = {
                "type": "function", 
                "function": {
                    "name": f"get_prompt_{p.name}",
                    "description": f"Get the {p.name} prompt: {p.description or ''}",
                    "parameters": safe_get_parameters(p)
                }
            }
            openai_tools.append(prompt_tool)

        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        messages = [{
            "role": "system",
            "content": (
                "You are connected to Provena MCP tools and prompts. Use them to help the user access and search Provena data. "
                "Available prompts can be called using get_prompt_<name> to get structured workflow instructions. "
                "The user can authenticate using login_to_provena. "
                "For dataset registration, use get_prompt_dataset_registration_workflow to get the structured workflow. "
                "Autonomously chain multiple tool calls to complete tasks end-to-end without asking for another user prompt. "
                "Only request confirmation for destructive/irreversible actions. When done, return a concise final answer."
            )
        }]

        mode_indicator = " [DEBUG MODE]" if DEBUG_MODE else ""
        print(f"\nChat started!{mode_indicator}")
        if DEBUG_MODE:
            print("Debug mode is ON - showing detailed tool call info")
        print("Type your question. Use Ctrl+C to exit.\n")

        while True:
            prompt = input("You: ").strip()
            messages.append({"role": "user", "content": prompt})

            try:
                tool_rounds = 0
                while True:
                    tool_rounds += 1
                    if tool_rounds > 12:  
                        print("AI: Stopping after too many tool rounds.")
                        break

                    ai_resp = openai_client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto"
                    )

                    msg = ai_resp.choices[0].message
                    messages.append(msg)

                    if msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.function.name
                            try:
                                args = json.loads(tool_call.function.arguments or "{}")
                            except Exception:
                                args = {}
                            
                            # Show tool call - detailed in debug mode, minimal otherwise
                            if DEBUG_MODE:
                                print(f"\n[Calling: {tool_name}]")
                                print(f"Arguments: {json.dumps(args, indent=2)}")
                            else:
                                print(f"→ {tool_name}")

                            try:
                                # Check if this is a prompt call
                                if tool_name.startswith("get_prompt_"):
                                    prompt_name = tool_name.replace("get_prompt_", "")
                                    result = await client.get_prompt(prompt_name, args)
                                    prompt_content = extract_prompt_result(result)
                                    
                                    if DEBUG_MODE:
                                        print(f"[{tool_name} result]: {prompt_content}")
                                    
                                    # Add the prompt content as a tool response
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "content": prompt_content
                                    })
                                    
                                    # Also add it as a system message for ongoing context
                                    messages.append({
                                        "role": "system",
                                        "content": f"Workflow Instructions: {prompt_content}"
                                    })
                                else:
                                    # Regular tool call
                                    if requires_confirmation(tool_name):
                                        print(f"\n[Confirmation Required] You are about to call '{tool_name}' with the following arguments:")
                                        print(json.dumps(args, indent=2))
                                        confirm = input("Would you like to proceed with this action? (yes/no): ").strip().lower()
                                        if confirm not in ("yes", "y"):
                                            print(f"Cancelled call to {tool_name}.")
                                            messages.append({
                                                "role": "tool",
                                                "tool_call_id": tool_call.id,
                                                "content": json.dumps({"status": "cancelled", "message": f"User cancelled call to {tool_name}."})
                                            })
                                            continue  # Skip this tool call
                                    # Regular tool call
                                    result = await client.call_tool(tool_name, args)
                                    data = extract_tool_result(result)
                                    result_text = json.dumps(data, indent=2)
                                    
                                    if DEBUG_MODE:
                                        print(f"[{tool_name} result]: {result_text}")

                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "content": result_text
                                    })
                            except Exception as e:
                                error_msg = {"status": "error", "message": str(e)}
                                if DEBUG_MODE:
                                    print(f"Tool error: {error_msg}")
                                else:
                                    print(f"✗ Error in {tool_name}: {str(e)}")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": json.dumps(error_msg)
                                })
                        continue

                    print("AI:", msg.content)
                    break
                    
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(ai_chat_loop())