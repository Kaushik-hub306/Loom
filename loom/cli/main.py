"""Loom CLI — one-shot setup and health checks."""

import json
import os
import sys
import shutil
from pathlib import Path


def _python_path() -> str:
    """Return the full path to the current Python interpreter."""
    return sys.executable


def _is_windows() -> bool:
    return sys.platform == "win32"


def cmd_setup(args=None):
    """Generate a ready-to-paste MCP config for Claude Desktop."""
    project_root = os.environ.get(
        "LOOM_PROJECT_ROOT",
        str(Path.home() / "loom-memory"),
    )

    # Auto-create the directory
    Path(project_root).mkdir(parents=True, exist_ok=True)

    python = _python_path()
    is_mac = sys.platform == "darwin"
    is_win = _is_windows()

    if is_mac:
        config_path = "~/Library/Application Support/Claude/claude_desktop_config.json"
    elif is_win:
        config_path = "%APPDATA%\\Claude\\claude_desktop_config.json"
    else:
        config_path = "~/.config/Claude/claude_desktop_config.json"

    print("=" * 60)
    print("  Loom MCP Server — One-Shot Setup")
    print("=" * 60)
    print()
    print(f"  Project root : {project_root}")
    print(f"  Python       : {python}")
    print(f"  Config file  : {config_path}")
    print()

    # Base config (no API key)
    base_config = {
        "mcpServers": {
            "loom": {
                "command": python,
                "args": ["-m", "loom.mcp"],
                "env": {
                    "LOOM_PROJECT_ROOT": project_root,
                },
            }
        }
    }

    print("── Paste this into your Claude config file: ──")
    print()
    print(json.dumps(base_config, indent=2))
    print()

    # API key options
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_deepseek = bool(os.environ.get("LOOM_DEEPSEEK_API_KEY"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))

    if has_anthropic or has_deepseek or has_gemini:
        print("── Detected API keys in your environment ──")
        print()
        for name, key, env_var in [
            ("Anthropic", has_anthropic, "ANTHROPIC_API_KEY"),
            ("DeepSeek", has_deepseek, "LOOM_DEEPSEEK_API_KEY"),
            ("Gemini", has_gemini, "GEMINI_API_KEY"),
        ]:
            if key:
                masked = os.environ[env_var][:7] + "..." if os.environ[env_var] else ""
                print(f"  {name}: {masked} (from ${env_var})")
        print()
        print("  These keys were auto-detected and will be used if you")
        print("  paste the config above. No extra config needed.")
    else:
        print("── Optional: Add an LLM for smarter extraction ──")
        print()
        print("  Copy one of these into the \"env\" block above:")
        print()
        print('  "ANTHROPIC_API_KEY": "sk-ant-..."')
        print('  or')
        print('  "LOOM_LLM_PROVIDER": "deepseek",')
        print('  "LOOM_DEEPSEEK_API_KEY": "sk-..."')
        print('  or')
        print('  "LOOM_LLM_PROVIDER": "gemini",')
        print('  "GEMINI_API_KEY": "..."')
        print()
        print("  Without a key, Loom uses free keyword extraction.")

    print()
    print("── Next steps ──")
    print()
    print(f"  1. Paste the JSON above into {config_path}")
    print("  2. Restart Claude Desktop")
    print("  3. Run: loom doctor")
    print()


def cmd_doctor(args=None):
    """Check everything is working."""
    print("=" * 60)
    print("  Loom Doctor — System Check")
    print("=" * 60)
    print()

    checks = []

    # 1. Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    checks.append(("Python 3.11+", py_ok, f"Python {py_version}"))

    # 2. Loom importable
    try:
        import loom
        loom_ok = True
        loom_msg = f"Loom v{loom.__version__}"
    except ImportError:
        loom_ok = False
        loom_msg = "Loom not installed — run: pip install -e ."
    checks.append(("Loom installed", loom_ok, loom_msg))

    # 3. Project root exists and is writable
    project_root = Path(os.environ.get("LOOM_PROJECT_ROOT", os.getcwd()))
    root_exists = project_root.exists()
    root_writable = os.access(project_root, os.W_OK) if root_exists else False
    checks.append(("Project directory", root_exists, str(project_root)))
    checks.append(("Directory writable", root_writable,
                   "writable" if root_writable else f"not writable: {project_root}"))

    # 4. .loom/ directory
    loom_dir = project_root / ".loom"
    loom_dir_ok = loom_dir.exists()
    checks.append((".loom/ exists", loom_dir_ok,
                   str(loom_dir) if loom_dir_ok else "will be created on first use"))

    # 5. Rules and timeline
    if loom_dir_ok:
        rules_file = loom_dir / "rules.json"
        if rules_file.exists():
            try:
                data = json.loads(rules_file.read_text())
                rule_count = len(data.get("rules", []))
                checks.append(("Rules stored", True, f"{rule_count} rules"))
            except Exception:
                checks.append(("Rules stored", False, "rules.json corrupted"))
        else:
            checks.append(("Rules stored", True, "no rules yet (fresh install)"))

        timeline = loom_dir / "timeline.jsonl"
        if timeline.exists():
            entries = timeline.read_text().strip().splitlines()
            checks.append(("Timeline", True, f"{len(entries)} entries"))
        else:
            checks.append(("Timeline", True, "no entries yet"))

    # 6. Domain configs
    domains_dir = loom_dir / "domains" if loom_dir_ok else None
    if domains_dir and domains_dir.exists():
        configs = list(domains_dir.glob("*.yml"))
        checks.append(("Domain configs", True, f"{len(configs)} domains"))
    else:
        checks.append(("Domain configs", True, "created on first use"))

    # 7. LLM Provider
    from loom.llm.factory import get_provider
    provider = get_provider()
    if provider:
        sdk_ok = False
        if provider.provider_name == "anthropic":
            try:
                import anthropic
                sdk_ok = True
            except ImportError:
                pass
        elif provider.provider_name == "deepseek":
            try:
                import openai
                sdk_ok = True
            except ImportError:
                pass
        elif provider.provider_name == "gemini":
            try:
                import google.generativeai
                sdk_ok = True
            except ImportError:
                pass

        sdk_msg = f"{provider.provider_name} (SDK: {'installed' if sdk_ok else 'MISSING — pip install loom-agent[{provider.provider_name}]'})"
        checks.append(("LLM extraction", sdk_ok, sdk_msg))
    else:
        checks.append(("LLM extraction", True, "keyword only (free, no API key)"))

    # 8. MCP protocol check
    try:
        from mcp.server.fastmcp import FastMCP
        mcp_ok = True
        mcp_msg = "FastMCP available"
    except ImportError:
        mcp_ok = False
        mcp_msg = "mcp package not installed"
    checks.append(("MCP protocol", mcp_ok, mcp_msg))

    # Print results
    all_ok = True
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status}] {name}")
        if detail:
            print(f"         {detail}")

    print()
    if all_ok:
        print("  All checks passed. Loom is ready.")
    else:
        print("  Some checks failed. Fix the FAIL items above.")
        print()
        print("  Quick fixes:")
        print("    pip install -e .              # install Loom")
        print("    pip install openai            # for DeepSeek")
        print("    pip install anthropic         # for Anthropic")
        print("    pip install google-generativeai  # for Gemini")
        print("    export LOOM_PROJECT_ROOT=/path/to/your/project")

    print()
    return 0 if all_ok else 1


def main():
    if len(sys.argv) < 2:
        print("Usage: loom <command>")
        print()
        print("Commands:")
        print("  setup    Generate Claude Desktop config")
        print("  doctor   Check everything is working")
        print()
        print("Quick start:")
        print("  1. loom setup   — paste the output into Claude config")
        print("  2. restart Claude Desktop")
        print("  3. loom doctor  — verify everything is green")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "setup":
        cmd_setup()
    elif cmd == "doctor":
        sys.exit(cmd_doctor())
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'loom' without arguments to see available commands.")
        sys.exit(1)


if __name__ == "__main__":
    main()
