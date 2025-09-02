import os
import json
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from fastmcp import Client

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

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
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        print("Available Tools:", tool_names)

        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": getattr(t, "inputSchema", {"type": "object", "properties": {}})
                }
            })

        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        messages = [{"role": "system", "content": "You are connected to Provena MCP tools. Use them to help the user access and search Provena data. The user can authenticate using login_to_provena."}]

        print("\nChat started! Commands: 'quit', 'exit'")
        print("Ask me anything about Provena data!\n")

        while True:
            prompt = input("You: ").strip()
            if prompt.lower() in ("quit", "exit"):
                break

            messages.append({"role": "user", "content": prompt})

            try:
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
                        args = json.loads(tool_call.function.arguments)
                        print(f"[Calling: {tool_name}({args})]")
                        
                        try:
                            result = await client.call_tool(tool_name, args)
                            data = extract_tool_result(result)
                            result_text = json.dumps(data, indent=2)
                            print(f"📋 [{tool_name} result]: {result_text}")
                            
                            messages.append({
                                "role": "tool", 
                                "tool_call_id": tool_call.id, 
                                "content": result_text
                            })
                        except Exception as e:
                            error_msg = f"Tool error: {str(e)}"
                            print(f"{error_msg}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": error_msg
                            })
                            
                    final_resp = openai_client.chat.completions.create(
                        model=MODEL,
                        messages=messages
                    )
                    final_msg = final_resp.choices[0].message
                    print("AI:", final_msg.content)
                    messages.append(final_msg)
                else:
                    print("AI:", msg.content)
                    
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(ai_chat_loop())
