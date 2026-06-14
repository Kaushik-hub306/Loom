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
    if loom_dir_ok:
        checks.append((".loom/ exists", True, str(loom_dir)))
    else:
        checks.append((".loom/ exists", True, "will be created when MCP server starts"))

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


def _claude_config_path() -> Path | None:
    """Return the OS-specific Claude Desktop config path, or None."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    else:
        return home / ".config" / "Claude" / "claude_desktop_config.json"


def cmd_preflight(config_path: str | None = None):
    """Validate that Loom will work when Claude Desktop launches it.

    Parses the Claude Desktop config, checks the Python path, verifies
    Loom is importable, and validates the MCP transport chain.
    """
    import subprocess

    print("=" * 60)
    print("  Loom Preflight — MCP Chain Validation")
    print("=" * 60)
    print()

    # Resolve config path
    if config_path:
        cfg = Path(config_path).expanduser()
    else:
        cfg = _claude_config_path()

    print(f"  Config: {cfg}")
    print()

    checks = []
    all_ok = True

    # 1. Config file exists and is valid JSON
    if not cfg.exists():
        print(f"  [FAIL] Config file not found: {cfg}")
        print(f"         Run 'loom setup' first, or use --config-path to specify")
        print()
        return 1
    else:
        try:
            config_data = json.loads(cfg.read_text())
            checks.append(("Config file", True, "found and valid JSON"))
        except json.JSONDecodeError as e:
            print(f"  [FAIL] Config file is not valid JSON: {e}")
            print()
            return 1

    # 2. Find Loom in the mcpServers block
    mcp_servers = config_data.get("mcpServers", {})
    loom_config = mcp_servers.get("loom")
    if not loom_config:
        print(f"  [FAIL] No 'loom' entry found in mcpServers")
        print(f"         Run 'loom setup' and paste its output into the config.")
        print()
        return 1

    command = loom_config.get("command", "")
    args_list = loom_config.get("args", [])
    env_vars = loom_config.get("env", {})

    # 3. Python executable exists and is executable
    python_exe = command
    if not python_exe:
        python_exe = shutil.which("python3") or shutil.which("python") or ""
    if not python_exe:
        print(f"  [FAIL] No Python command found in config")
        print(f"         Set 'command' to your Python path (e.g., which python3)")
        print()
        return 1

    exe_path = Path(python_exe)
    if not exe_path.is_file() and not shutil.which(python_exe):
        print(f"  [FAIL] Python not found: {python_exe}")
        print(f"         Full path or install Python 3.10+ and retry.")
        print()
        return 1
    checks.append(("Python path", True, str(python_exe)))

    # 4. Loom is importable
    try:
        result = subprocess.run(
            [python_exe, "-c", "import loom"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            checks.append(("Loom import", True, "loom package found"))
        else:
            print(f"  [FAIL] Loom package not importable from {python_exe}")
            print(f"         {result.stderr.strip()}")
            print(f"         Run: {python_exe} -m pip install loom-agent")
            print()
            return 1
    except subprocess.TimeoutExpired:
        print(f"  [FAIL] Python import check timed out after 10s")
        print()
        return 1
    except Exception as e:
        print(f"  [FAIL] Cannot run Python: {e}")
        print()
        return 1

    # 5. Storage path is writable (if configured)
    project_root = env_vars.get("LOOM_PROJECT_ROOT", "")
    if project_root:
        pr = Path(project_root).expanduser()
        if pr.exists():
            if os.access(pr, os.W_OK):
                checks.append(("Storage path", True, f"{pr} (writable)"))
            else:
                checks.append(("Storage path", False, f"{pr} (NOT writable — check permissions)"))
                all_ok = False
        else:
            try:
                pr.mkdir(parents=True, exist_ok=True)
                checks.append(("Storage path", True, f"{pr} (created)"))
            except Exception as e:
                checks.append(("Storage path", False, f"{pr} (cannot create: {e})"))
                all_ok = False
    else:
        checks.append(("Storage path", True, "not set (defaults to $PWD at runtime)"))

    # 6. MCP module loads
    try:
        result = subprocess.run(
            [python_exe, "-c", "from loom.mcp.server import LoomMCPServer"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            checks.append(("MCP module", True, "loom.mcp.server loads"))
        else:
            print(f"  [FAIL] loom.mcp.server failed to load")
            print(f"         {result.stderr.strip()}")
            print()
            return 1
    except subprocess.TimeoutExpired:
        print(f"  [FAIL] MCP module load check timed out after 10s")
        print()
        return 1

    # Print results
    print()
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status}] {name}")
        if detail:
            print(f"         {detail}")

    print()
    if all_ok:
        print("  All preflight checks passed. Ready to restart Claude Desktop.")
    else:
        print("  Some checks failed. Fix the FAIL items above.")
    print()
    return 0 if all_ok else 1


def cmd_cloud_setup(args=None):
    """Create a Supabase-backed shared Loom database and print config."""
    import urllib.request
    import urllib.error

    print("=" * 60)
    print("  Loom Cloud Setup — Shared Team Memory")
    print("=" * 60)
    print()
    print("  This creates a shared database so your entire team")
    print("  shares the same conventions in real-time.")
    print()

    # Get Supabase credentials
    supabase_url = input("  Supabase URL (e.g. https://xyz.supabase.co): ").strip()
    if not supabase_url:
        print("  URL is required.")
        return

    supabase_key = input("  Supabase service_role key (sbp_...): ").strip()
    if not supabase_key:
        print("  Key is required.")
        return

    project_name = input("  Project name [default: loom-shared]: ").strip()
    if not project_name:
        project_name = "loom-shared"

    print()
    print("  Creating database...")

    # Build the Postgres connection URL from Supabase params
    # Supabase URL: https://[ref].supabase.co
    # DB URL: postgresql://postgres:[key]@db.[ref].supabase.co:5432/postgres
    try:
        ref = supabase_url.replace("https://", "").replace(".supabase.co", "").strip("/")
        db_url = f"postgresql://postgres:{supabase_key}@db.{ref}.supabase.co:5432/postgres"
    except Exception:
        print("  Invalid Supabase URL format. Expected: https://[ref].supabase.co")
        return

    # Run migrations
    try:
        from loom.storage.postgres_store import PostgresStore
        from loom.config import StorageConfig

        config = StorageConfig(
            backend="postgres",
            database_url=db_url,
        )
        store = PostgresStore(config)
        store.initialize()

        if store.health_check():
            print("  Database: connected")
        else:
            print("  Database: connection failed — check your URL and key")
            return
    except ImportError:
        print("  psycopg2 not installed. Run: pip install loom-agent[cloud]")
        return
    except Exception as e:
        print(f"  Error: {e}")
        return

    # Generate API key
    import secrets
    import hashlib
    api_key = "loom_sk_" + secrets.token_hex(24)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    try:
        with store._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO api_keys (key_hash, key_prefix, project_id, role) "
                    "VALUES (%s, %s, %s, %s)",
                    (key_hash, api_key[:10] + "...", project_name, "admin"),
                )
                conn.commit()
    except Exception:
        pass  # key storage is best-effort

    # Generate config
    python_path = sys.executable
    config = {
        "mcpServers": {
            "loom": {
                "command": python_path,
                "args": ["-m", "loom.mcp"],
                "env": {
                    "LOOM_STORAGE_BACKEND": "postgres",
                    "LOOM_DATABASE_URL": db_url,
                },
            }
        }
    }

    print()
    print("=" * 60)
    print("  Paste this into your Claude Desktop config:")
    print("=" * 60)
    print()
    print(json.dumps(config, indent=2))
    print()
    print("  Share this config with your team.")
    print("  Everyone connects to the same memory.")
    print()
    print("  ⚠️  SECURITY: This config contains database credentials.")
    print("     Restrict file permissions: chmod 600 ~/Library/Application\\\\")
    print("     Support/Claude/claude_desktop_config.json")
    print("     Do not commit this file to git — it contains your Supabase")
    print("     service_role key which has full database access.")
    print()
    print("  API key (for SaaS later): " + api_key)
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: loom <command>")
        print()
        print("Commands:")
        print("  setup        Generate local Claude Desktop config")
        print("  init         Same as setup — initialize Loom in this project")
        print("  cloud setup  Create a shared Supabase database for your team")
        print("  doctor       Check everything is working")
        print("  doctor --preflight  Validate MCP config before restart")
        print()
        print("Quick start (local):")
        print("  1. loom setup       — paste into Claude config")
        print("  2. restart Claude Desktop")
        print("  3. loom doctor      — verify everything is green")
        print()
        print("Quick start (team):")
        print("  1. loom cloud setup — paste Supabase URL + key")
        print("  2. share the config with your team")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "setup":
        cmd_setup()
    elif cmd == "cloud" and len(sys.argv) > 2 and sys.argv[2] == "setup":
        cmd_cloud_setup()
    elif cmd == "doctor":
        if "--preflight" in sys.argv:
            # Extract optional --config-path argument
            cp_idx = None
            try:
                cp_idx = sys.argv.index("--config-path")
            except ValueError:
                pass
            config_path = sys.argv[cp_idx + 1] if cp_idx and cp_idx + 1 < len(sys.argv) else None
            sys.exit(cmd_preflight(config_path))
        else:
            sys.exit(cmd_doctor())
    elif cmd == "init":
        cmd_setup()
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'loom' without arguments to see available commands.")
        sys.exit(1)


if __name__ == "__main__":
    main()
