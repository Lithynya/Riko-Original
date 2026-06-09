import requests
import json
from pathlib import Path
import yaml 
# ─────────────────────────────
# 🗂️ Credential + Config Paths
# ─────────────────────────────


def load_mcp_config():
    """Load MCP configuration from file located in the same directory as this script."""
    # Always use the current script’s directory
    script_dir = Path(__file__).resolve().parent
    mcp_config_path = script_dir / "mcp_config.json"

    if not mcp_config_path.exists():
        print(f"⚠️ MCP config not found at {mcp_config_path}")
        return None

    try:
        with open(mcp_config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ Failed to load MCP config: {e}")
        return None


def get_mcp_tools_metadata():
    """
    Get metadata for all available MCP tools.
    
    Returns:
        List of tool metadata dictionaries, or None if failed
    """
    mcp_config = load_mcp_config()
    if not mcp_config:
        print("⚠️ MCP config unavailable")
        return None
    
    try:
        server_url = mcp_config["url"].rstrip("/")
        access_token = mcp_config["token"]
        
        # MCP protocol endpoint
        mcp_endpoint = f"{server_url}/mcp/"
        
        # Construct MCP JSON-RPC call to list tools
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        # Make the request with SSE support
        response = requests.post(
            mcp_endpoint,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            json=payload,
            timeout=10,
            stream=True
        )
        
        response.raise_for_status()
        
        # Handle SSE stream response
        if response.headers.get('content-type', '').startswith('text/event-stream'):
            # Parse SSE stream
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data = decoded[6:]  # Remove 'data: ' prefix
                        try:
                            event_data = json.loads(data)
                            
                            # Check for JSON-RPC error
                            if "error" in event_data:
                                print(f"⚠️ MCP error: {event_data['error']}")
                                return None
                            
                            # Return the tools list when found
                            if event_data.get("jsonrpc") == "2.0" and "result" in event_data:
                                result = event_data["result"]
                                # The result contains a "tools" array
                                if "tools" in result:
                                    return result["tools"]
                                return result
                        except json.JSONDecodeError:
                            continue
            return None
        else:
            # Handle regular JSON response (fallback)
            result = response.json()
            
            # Check for JSON-RPC error
            if "error" in result:
                print(f"⚠️ MCP error: {result['error']}")
                return None
                
            # Return the tools list
            if "result" in result:
                if "tools" in result["result"]:
                    return result["result"]["tools"]
                return result["result"]
            
            return result
    
    except requests.exceptions.RequestException as e:
        print(f"⚠️ MCP call failed: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
        return None


def print_tools_metadata(tools):
    """Pretty print tools metadata."""
    if not tools:
        print("No tools found")
        return
    
    print(f"\n📋 Found {len(tools)} tool(s):\n")
    for i, tool in enumerate(tools, 1):
        print(f"{'='*60}")
        print(f"Tool #{i}: {tool.get('name', 'Unknown')}")
        print(f"{'='*60}")
        print(f"Description: {tool.get('description', 'No description')}")
        
        # Print input schema
        if 'inputSchema' in tool or 'input_schema' in tool:
            schema = tool.get('inputSchema') or tool.get('input_schema')
            print(f"\n📝 Input Schema:")
            print(f"  Type: {schema.get('type', 'N/A')}")
            
            if 'properties' in schema:
                print(f"  Properties:")
                for prop_name, prop_info in schema['properties'].items():
                    prop_type = prop_info.get('type', 'unknown')
                    prop_title = prop_info.get('title', prop_name)
                    print(f"    - {prop_name} ({prop_type}): {prop_title}")
            
            if 'required' in schema:
                print(f"  Required: {', '.join(schema['required'])}")
        
        # Print metadata (your custom meta field)
        if 'meta' in tool:
            print(f"\n🏷️  Metadata:")
            for key, value in tool['meta'].items():
                print(f"    {key}: {value}")
        
        # Print annotations
        if 'annotations' in tool:
            print(f"\n🔖 Annotations:")
            for key, value in tool['annotations'].items():
                print(f"    {key}: {value}")
        
        print()



def get_manual_mcp_response(tool_name: str, arguments: dict):
    """
    Manually call an MCP tool using the MCP protocol.
    
    Args:
        tool_name: Name of the tool to call (e.g., "play_sound_effect")
        arguments: Dictionary of arguments for the tool (e.g., {"sound_type": "bong"})
    
    Returns:
        The tool result or None if failed
    """
    mcp_config = load_mcp_config()
    if not mcp_config:
        print("⚠️ MCP config unavailable")
        return None
    
    try:
        server_url = mcp_config["url"].rstrip("/")
        access_token = mcp_config["token"]
        
        # MCP protocol endpoint
        mcp_endpoint = f"{server_url}/mcp/"
        
        # Construct MCP JSON-RPC call
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        # Make the request with SSE support
        response = requests.post(
            mcp_endpoint,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            json=payload,
            timeout=10,
            stream=True  # Important for SSE
        )
        
        response.raise_for_status()
        
        # Handle SSE stream response
        if response.headers.get('content-type', '').startswith('text/event-stream'):
            # Parse SSE stream
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data = decoded[6:]  # Remove 'data: ' prefix
                        try:
                            event_data = json.loads(data)
                            
                            # Check for JSON-RPC error
                            if "error" in event_data:
                                print(f"⚠️ MCP error: {event_data['error']}")
                                return None
                            
                            # Return the result when found
                            if event_data.get("jsonrpc") == "2.0" and "result" in event_data:
                                return event_data["result"]
                        except json.JSONDecodeError:
                            continue
            return None
        else:
            # Handle regular JSON response (fallback)
            result = response.json()
            
            # Check for JSON-RPC error
            if "error" in result:
                print(f"⚠️ MCP error: {result['error']}")
                return None
                
            # Return the actual result
            if "result" in result:
                return result["result"]
            
            return result
    
    except requests.exceptions.RequestException as e:
        print(f"⚠️ MCP call failed: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
        return None




# Example usage
if __name__ == "__main__":
    print("🔍 Fetching MCP tools metadata...")
    tools = get_mcp_tools_metadata()
    
    if tools:
        print_tools_metadata(tools)
        
        # Also print raw JSON for inspection
        print("\n" + "="*60)
        print("📦 Raw JSON Response:")
        print("="*60)
        print(json.dumps(tools, indent=2))
    else:
        print("❌ Failed to fetch tools metadata")


    result = get_manual_mcp_response(
        tool_name="roll_dice",
        arguments={"n_dice": 3}, 
    )
    print("Result:", result)

    # manual call argument
    result = get_manual_mcp_response(
        tool_name="roll_dice",
        arguments={"n_dice": 3, "manual_call": True}, 
    )
    print("Manually called Result:", result)
