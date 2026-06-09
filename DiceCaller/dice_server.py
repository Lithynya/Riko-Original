import random
import json
import yaml
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from fastmcp.server.auth import JWTVerifier
from pyngrok import ngrok
from pathlib import Path

# ─────────────────────────────
# 🔧 Detect paths and config
# ─────────────────────────────
# Example: /home/user/riko_project_mcp/DiceCaller/dice_roller.py
current_file = Path(__file__).resolve()
module_folder = current_file.parent.name  # → "DiceCaller"
project_root = current_file.parents[1]    # → "riko_project_mcp"

config_yaml_path = project_root / "riko_mcp_config.yaml"

# Load or create YAML
if not config_yaml_path.exists():
    default_config = {"project_name": project_root.name, "port": 9000, "ngrok": True}
    with open(config_yaml_path, "w") as f:
        yaml.dump(default_config, f)
    print(f"🆕 Created default YAML config: {config_yaml_path}")

with open(config_yaml_path, "r") as f:
    config_yaml = yaml.safe_load(f)

project_name = config_yaml.get("project_name", project_root.name)
port = config_yaml.get("port", 9000)
use_ngrok = config_yaml.get("ngrok", True)

server_name = module_folder  # Automatically derived from folder

# ─────────────────────────────
# 🗂️ Credential + Config Paths
# ─────────────────────────────
config_json_path = project_root / "mcp_config.json"

# ─────────────────────────────
# 🔐 Authentication
# ─────────────────────────────
key_pair = RSAKeyPair.generate()
access_token = key_pair.create_token(audience=server_name)

auth = JWTVerifier(
    public_key=key_pair.public_key,
    audience=server_name,
)

# ─────────────────────────────
# 🌍 Ngrok Tunnel (optional)
# ─────────────────────────────
if use_ngrok:
    public_url = ngrok.connect(port, "http").public_url
else:
    public_url = f"http://localhost:{port}"

print(f"🌍 MCP Public URL: {public_url}")

# Save connection details for clients
config_data = {
    "server_name": server_name,
    "url": public_url,
    "token": access_token,
}
with open(config_json_path, "w") as f:
    json.dump(config_data, f, indent=2)
print(f"✅ Config saved to {config_json_path}")

# ─────────────────────────────
# 🧮 MCP Server Setup
# ─────────────────────────────
mcp = FastMCP(name=server_name)

# Example tool
@mcp.tool(meta={"tool_type": "can_async"}, exclude_args=["manual_call"])
def roll_dice(n_dice: int, manual_call: bool = False):
    """Roll `n_dice` 6-sided dice and return the results."""
    print(f"🎲 roll_dice called with n_dice={n_dice}")

    dice_result  = [random.randint(1, 6) for _ in range(n_dice)]
    

    if manual_call  == True:
        return f"this function was manually called"

    return dice_result

# ─────────────────────────────
# ▶️ Run Server
# ─────────────────────────────
if __name__ == "__main__":
    print(f"\n---\n🔑 {server_name} Access Token:\n{access_token}\n---\n")
    mcp.run(transport="http", port=port, stateless_http=True)
