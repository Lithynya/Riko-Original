#!/usr/bin/env python3
"""
Streaming LLM with ordered MCP function calling and TTS playback.

This script ensures:
1. Text chunks and function calls are processed in order
2. Audio does not overlap
3. Functions are executed before the next audio segment when needed
4. Audio playback is synchronized with function calling
"""

import os
import time
import uuid
import json
import shutil
import yaml
from pathlib import Path
from openai import OpenAI
from queue import Queue
from threading import Thread
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import requests

# Import your existing functions
from process.tts_func.sovits_ping import sovits_gen, get_wav_duration
from process.tts_func.tts_preprocess import clean_llm_output
from process.vrm_func.vrm_ping import vrm_talk #, vrm_animate
from dotenv import load_dotenv

load_dotenv()

# ==================== Configuration ====================
CONFIG_PATH = os.path.expanduser('character_config.yaml')
CONFIG_PATH_MCP = os.path.expanduser('riko_project_mcp_config.yaml')
if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"Config not found at {CONFIG_PATH}")
if not os.path.exists(CONFIG_PATH_MCP):
    raise FileNotFoundError(f"Config not found at {CONFIG_PATH_MCP}")




with open(CONFIG_PATH, 'r', encoding="utf-8") as f:
    char_config = yaml.safe_load(f)

with open(CONFIG_PATH_MCP, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

MCP_CONFIG_PATH = Path(cfg["riko_project_mcp_location"]) / "mcp_config.json"

HISTORY_FILE = char_config['history_file']
MODEL = 'gpt-4.1'
SYSTEM_PROMPT = [{
    "role": "system",
    "content": [{"type": "input_text", "text": "You are a helpful assistant."}]
}]

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ==================== MCP Configuration ====================
def load_mcp_config():
    """Load MCP configuration from file."""
    if not MCP_CONFIG_PATH.exists():
        return None
    try:
        with open(MCP_CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

def get_all_tools_metadata() -> Optional[List[Dict[str, Any]]]:
    """
    Get complete metadata JSON for all MCP tools.
    
    Returns:
        List of tool dictionaries with all metadata, or None if failed
    """
    mcp_config = load_mcp_config()
    if not mcp_config:
        return None
    
    try:
        server_url = mcp_config["url"].rstrip("/")
        access_token = mcp_config["token"]
        mcp_endpoint = f"{server_url}/mcp/"
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
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
        
        # Parse SSE stream
        if response.headers.get('content-type', '').startswith('text/event-stream'):
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data = decoded[6:]
                        try:
                            event_data = json.loads(data)
                            if "error" in event_data:
                                return None
                            if event_data.get("jsonrpc") == "2.0" and "result" in event_data:
                                result = event_data["result"]
                                return result.get("tools", result)
                        except json.JSONDecodeError:
                            continue
        else:
            result = response.json()
            if "error" in result:
                return None
            if "result" in result:
                return result["result"].get("tools", result["result"])
            return result
    
    except Exception:
        return None


def get_metadata_field(function_name: str, field_path: str) -> Optional[Any]:
    """
    Get a specific metadata field value for a given function.
    
    Args:
        function_name: Name of the function (e.g., "play_sound_effect")
        field_path: Dot-notation path to the field (e.g., "tool_type" or "_fastmcp.tags")
    
    Returns:
        The value of the field, or None if not found
    
    Examples:
        >>> get_metadata_field("play_sound_effect", "tool_type")
        "needs_sync"
    """
    all_tools = get_all_tools_metadata()
    if not all_tools:
        return None
    
    # Find the tool
    tool = None
    for t in all_tools:
        if t.get("name") == function_name:
            tool = t
            break
    
    if not tool:
        return None
    
    # Navigate to the field using dot notation
    # Start from _meta
    meta = tool.get("_meta", {})
    
    # Split the field path and navigate
    path_parts = field_path.split(".")
    current = meta
    
    for part in path_parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    
    return current

def get_manual_mcp_response(tool_name: str, arguments: dict):
    """
    Manually call an MCP tool using the MCP protocol.
    
    Args:
        tool_name: Name of the tool to call (e.g., "play_sound_effect")
        arguments: Dictionary of arguments for the tool (e.g., {"sound_type": "bong", "manual_call": True})
    
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

# ==================== Item Types ====================
class ItemType(Enum):
    TEXT = "text"
    FUNCTION_CALL = "function_call"

@dataclass
class PlaybackItem:
    """Item to be processed in the playback queue."""
    item_type: ItemType
    content: str  # Text content or function name
    arguments: Optional[Dict] = None  # Function arguments
    audio_path: Optional[Path] = None  # Path to audio file for text items
    expression: str = "relaxed"
    duration: float = 0.0
    needs_sync: bool = False  # Whether function needs to be synced with TTS

# ==================== History Management ====================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return SYSTEM_PROMPT.copy()

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

# ==================== Playback Worker ====================
class OrderedPlaybackWorker:
    """
    Worker that processes text and function calls in strict order.
    Ensures audio doesn't overlap and functions execute at the right time.
    """
    def __init__(self):
        self.queue = Queue()
        self.thread = Thread(target=self._run, daemon=True)
        self._running = False
        self._talking = False

    def start(self):
        if not self._running:
            self._running = True
            self.thread.start()

    def enqueue(self, item: PlaybackItem):
        """Add an item to the playback queue."""
        self.queue.put(item)

    def _run(self):
        """Main playback loop - processes items in strict order."""
        while True:
            item = self.queue.get()
            if item is None:
                break

            if item.item_type == ItemType.TEXT:
                self._process_text_item(item)
            elif item.item_type == ItemType.FUNCTION_CALL:
                self._process_function_item(item)

            # Return to idle if queue is empty
            if self.queue.empty():
                try:
                    # idle_path = Path("animations/mixamo") / "Idle.fbx"
                    # vrm_animate("start_mixamo", str(idle_path))
                    self._talking = False
                except Exception as e:
                    print(f"vrm_animate (idle) failed: {e}")

    def _process_text_item(self, item: PlaybackItem):
        """Process a text item - play TTS audio."""
        try:
            # Start talking animation if not already talking
            if not self._talking:
                # anim_path = Path("animations/mixamo") / "Talking.fbx"
                # vrm_animate("start_mixamo", str(anim_path))
                self._talking = True
        except Exception as e:
            print(f"vrm_animate (start talking) failed: {e}")

        # Send audio to VRM
        try:
            vrm_talk(
                str(item.audio_path),
                item.expression,
                item.content,
                int(item.duration)
            )
        except Exception as e:
            print(f"vrm_talk failed: {e}")

        # Wait for audio duration to prevent overlap
        time.sleep(item.duration)

    def _process_function_item(self, item: PlaybackItem):
        """Process a function call item."""
        print(f"\n🔧 Processing function: {item.content}")
        print(f"   Arguments: {item.arguments}")
        print(f"   Needs sync: {item.needs_sync}")
        
        # Execute the function with manual_call=True for synced functions
        if item.needs_sync:
            # Add manual_call flag to arguments
            tool_args = item.arguments.copy()
            tool_args["manual_call"] = True
            
            print(f"   Calling manually with args: {tool_args}")
            
            # Call the function manually
            result = get_manual_mcp_response(
                tool_name=item.content,
                arguments=tool_args
            )
            print(f"✅ Function result: {result}\n")
        else:
            # For non-synced functions, they've already been executed
            # during streaming, so we just log here
            print(f"✅ Function {item.content} already executed during streaming\n")

    def stop(self):
        self.queue.put(None)
        self.thread.join()

# ==================== Streaming with Function Calls ====================
def stream_with_functions(messages):
    """
    Stream LLM response and yield items (text chunks and function calls) in order.
    
    This collects all items during streaming, then yields them in the correct order
    based on their output_index.
    
    Yields:
        Tuples of (content, type) where type is "text" or "function"
    """
    mcp_config = load_mcp_config()
    
    # Prepare streaming request with MCP tools if available
    stream_kwargs = {
        "model": MODEL,
        "input": messages,
        "temperature": 1,
        "top_p": 1,
        "max_output_tokens": 2048,
    }
    
    if mcp_config:
        stream_kwargs["tools"] = [{
            "type": "mcp",
            "server_label": mcp_config["server_name"],
            "server_url": f"{mcp_config['url']}/mcp/",
            "require_approval": "never",
        }]
    
    # Store items by output_index to maintain order
    output_items = {}  # output_index -> {"type": "text"/"mcp", "content": ...}
    text_buffers = {}  # output_index -> text buffer
    mcp_items = {}     # output_index -> item_id
    
    min_chunk_len = 30
    max_chunk_len = 120
    
    with client.responses.stream(**stream_kwargs) as stream:
        for event in stream:
            
            if event.type == "response.output_text.delta":
                # Accumulate text by output_index
                output_index = getattr(event, "output_index", None)
                
                if output_index not in text_buffers:
                    text_buffers[output_index] = ""
                
                text_buffers[output_index] += event.delta
            
            elif event.type == "response.output_text.done":
                # Text complete for this output_index
                output_index = getattr(event, "output_index", None)
                
                if output_index in text_buffers:
                    full_text = text_buffers[output_index].strip()
                    if full_text:
                        output_items[output_index] = {
                            "type": "text",
                            "content": full_text
                        }
                        print(f"[DEBUG] Text completed at index {output_index}: {full_text[:50]}...")
            
            elif event.type == "response.mcp_call.completed":
                # MCP call completed - record its output index and item_id
                output_index = getattr(event, "output_index", None)
                item_id = getattr(event, "item_id", None)
                
                if output_index is not None:
                    mcp_items[output_index] = item_id
                    print(f"[DEBUG] MCP call completed at index {output_index}, item_id {item_id}")

        # Get final response to extract MCP call details
        final_response = stream.get_final_response()
        
        # Add MCP call details to output_items
        for output_index, item_id in mcp_items.items():
            for output_item in final_response.output:
                if (hasattr(output_item, 'type') and 
                    output_item.type == 'mcp_call' and 
                    hasattr(output_item, 'id') and 
                    output_item.id == item_id):
                    
                    tool_name = getattr(output_item, 'name', None)
                    tool_args_str = getattr(output_item, 'arguments', '{}')
                    
                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    # Check if this function needs sync
                    tool_type = get_metadata_field(tool_name, "tool_type")
                    needs_sync = (tool_type == "needs_sync")
                    
                    output_items[output_index] = {
                        "type": "function",
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "needs_sync": needs_sync
                    }
                    print(f"[DEBUG] Function at index {output_index}: {tool_name}({tool_args})")
                    break
    
    # Now yield items in order by output_index
    for output_index in sorted(output_items.keys()):
        item = output_items[output_index]
        
        if item["type"] == "text":
            # Split text into chunks for TTS
            full_text = item["content"]
            
            # Split by sentences
            chunks = []
            buffer = ""
            for char in full_text:
                buffer += char
                if char in '.!?' and len(buffer) >= min_chunk_len:
                    chunks.append(buffer.strip())
                    buffer = ""
            
            # Add remaining text
            if buffer.strip():
                chunks.append(buffer.strip())
            
            # Yield each chunk
            for chunk in chunks:
                if chunk:
                    print(f"[text chunk] {chunk}")
                    yield chunk, "text"
        
        elif item["type"] == "function":
            tool_name = item["tool_name"]
            tool_args = item["tool_args"]
            needs_sync = item["needs_sync"]
            
            print(f"🔍 Yielding function call: {tool_name} with args: {tool_args}")
            print(f"🏷️  Tool metadata - needs_sync: {needs_sync}")
            
            yield (tool_name, tool_args, needs_sync), "function"

# ==================== Main Loop ====================
def main_loop():
    """Main conversation loop with ordered playback."""
    # Ensure directories exist
    Path('client/audio').mkdir(parents=True, exist_ok=True)
    Path('audio').mkdir(parents=True, exist_ok=True)
    
    # Start playback worker
    playback = OrderedPlaybackWorker()
    playback.start()
    
    while True:
        try:
            # Idle animation
            # try:
            #     idle_anim = Path("animations/mixamo") / "Idle.fbx"
            #     vrm_animate("start_mixamo", str(idle_anim))
            # except Exception:
            #     pass
            
            # Get user input
            print("\n💬 [USER INPUT] Type your message:")
            user_input = input("> ").strip()
            
            if not user_input:
                continue
            
            # Thinking animation
            # try:
            #     thinking_anim = Path("animations/mixamo") / "Thinking.fbx"
            #     vrm_animate("start_mixamo", str(thinking_anim))
            # except Exception:
            #     pass
            
            # Build messages
            messages = load_history()
            messages.append({
                "role": "user",
                "content": [{"type": "input_text", "text": user_input}]
            })
            
            print("[llm] streaming response...")
            full_assistant_text = ""
            
            # Stream and process items in order
            for item, item_type in stream_with_functions(messages):
                
                if item_type == "text":
                    # Text chunk
                    text_chunk = item
                    print(f"[text chunk] {text_chunk}")
                    
                    full_assistant_text += (text_chunk + " ")
                    
                    # Generate TTS
                    tts_text = clean_llm_output(text_chunk)
                    emotion = "relaxed"
                    expression = "relaxed"
                    
                    # Create unique audio file
                    uid = uuid.uuid4().hex
                    filename = f"output_{uid}.wav"
                    client_out = Path('client') / 'audio' / filename
                    public_out = Path('audio') / filename
                    
                    # Generate TTS audio
                    try:
                        sovits_gen(tts_text, output_wav_pth=str(client_out))
                    except TypeError:
                        sovits_gen(tts_text, str(client_out))
                    
                    # Copy to public path
                    shutil.copy2(client_out, public_out)
                    
                    # Get duration
                    try:
                        duration = get_wav_duration(public_out)
                    except Exception:
                        duration = 3.0
                    
                    # Create playback item and enqueue
                    playback_item = PlaybackItem(
                        item_type=ItemType.TEXT,
                        content=text_chunk,
                        audio_path=public_out,
                        expression=expression,
                        duration=duration
                    )
                    playback.enqueue(playback_item)
                
                elif item_type == "function":
                    # Function call
                    tool_name, tool_args, needs_sync = item
                    print(f"[function call] {tool_name}({tool_args}) needs_sync={needs_sync}")
                    
                    # Create function playback item
                    function_item = PlaybackItem(
                        item_type=ItemType.FUNCTION_CALL,
                        content=tool_name,
                        arguments=tool_args,
                        needs_sync=needs_sync
                    )
                    playback.enqueue(function_item)
            
            # Save to history
            final_text = full_assistant_text.strip()
            print(f"[llm final] {final_text}")
            
            messages.append({
                "role": "assistant",
                "content": [{"type": "output_text", "text": final_text}]
            })
            save_history(messages)
            
            # Small delay before next loop
            time.sleep(0.5)
        
        except KeyboardInterrupt:
            print("\nInterrupted by user, stopping.")
            playback.stop()
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

if __name__ == '__main__':
    main_loop()