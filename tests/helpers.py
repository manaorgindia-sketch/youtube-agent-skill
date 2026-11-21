"""Shared test plumbing: paths, importing a tool by file path, running a tool as a subprocess."""
import importlib.util, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
FIX = os.path.join(ROOT, "tests", "fixtures")
sys.path.insert(0, os.path.join(SKILLS, "_shared"))

TOOLS = {
    "deadair": os.path.join(SKILLS, "yt-edit", "deadair.py"),
    "chapters": os.path.join(SKILLS, "yt-chapters", "chapters.py"),
    "retention": os.path.join(SKILLS, "yt-retention", "retention.py"),
    "hookscore": os.path.join(SKILLS, "yt-script", "hookscore.py"),
    "title": os.path.join(SKILLS, "yt-package", "title.py"),
    "swipe": os.path.join(SKILLS, "yt-viral", "swipe.py"),
}

def fx(*parts):
    return os.path.join(FIX, *parts)

def tool(name):
    """Import a tool module from its path (the skill folders have hyphens, so no plain import)."""
    spec = importlib.util.spec_from_file_location(f"yt_{name}", TOOLS[name])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run(name, *args, env=None, script=None):
    """Run a tool; returns CompletedProcess with text decoded as UTF-8."""
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    e.pop("PYTHONIOENCODING", None)
    if env: e.update(env)
    return subprocess.run([sys.executable, script or TOOLS[name], *args], capture_output=True,
                          env=e, cwd=ROOT, timeout=60, encoding="utf-8", errors="replace")

def run_json(name, *args, **kw):
    p = run(name, *args, "--json", **kw)
    assert p.returncode == 0, p.stderr or p.stdout
    return json.loads(p.stdout)
