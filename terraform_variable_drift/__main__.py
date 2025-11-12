#!/usr/bin/env python3
import sys, re, glob, json, os
from pathlib import Path

try:
    import hcl2
except ImportError:
    print("ERROR: python-hcl2 not installed. `pip install python-hcl2`", file=sys.stderr)
    sys.exit(2)

# --- Config
IGNORE_DIR_PATTERNS = ("/.terraform/", "/.git/", "/vendor/", "/third_party/")
IGNORE_FILE_PATTERNS = (".terraform",)
IGNORE_FILE_EXTS = (".tf", ".tfvars", ".json")
IGNORELIST_FILE = ".tfdriftignore"

VAR_REF_RE = re.compile(r"(?<![A-Za-z0-9_])var\.([A-Za-z0-9_]+)")

def log(msg: str):
    """Simple structured logger."""
    print(f"[LOG] {msg}")

def should_skip(path: str) -> bool:
    p = path.replace("\\", "/")
    if not p.endswith(IGNORE_FILE_EXTS): 
        log(f"⏩ Skipping non-Terraform file: {path}")
        return True
    if any(s in p for s in IGNORE_DIR_PATTERNS):
        log(f"⏩ Skipping ignored directory: {path}")
        return True
    return False

def hcl_load(path):
    with open(path, "r", encoding="utf-8") as f:
        return hcl2.load(f)

def parse_declared_vars_from_tf(path) -> set:
    declared = set()
    try:
        data = hcl_load(path)
    except Exception as e:
        log(f"⚠️  Failed to parse {path} with hcl2 ({e}); using regex fallback.")
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
        declared.update(re.findall(r'variable\s+"([A-Za-z0-9_]+)"\s*{', txt))
        return declared

    blocks = []
    if isinstance(data, dict):
        blocks.append(data)
    elif isinstance(data, list):
        blocks.extend(data)

    for blk in blocks:
        if "variable" in blk:
            for entry in blk["variable"]:
                if isinstance(entry, dict):
                    for name in entry.keys():
                        declared.add(name)
    return declared

def parse_used_vars_from_tf(path) -> set:
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    used = set(VAR_REF_RE.findall(txt))
    return used

def parse_tfvars(path) -> set:
    if path.endswith(".json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                keys = set(obj.keys())
                return keys
        except Exception as e:
            log(f"⚠️  Could not parse {path}: {e}")
            return set()
    else:
        try:
            data = hcl_load(path)
            if isinstance(data, dict):
                keys = set(data.keys())
                return keys
        except Exception as e:
            log(f"⚠️  Could not parse {path}: {e}")
            return set()
    return set()

def load_ignorelist(repo_root: Path) -> set:
    p = repo_root / IGNORELIST_FILE
    names = set()
    if p.exists():
        log(f"🧾 Loading ignore list from {p}")
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            names.add(line)
        log(f"✅ Ignored vars: {sorted(names)}")
    else:
        log("ℹ️  No .tfdriftignore file found.")
    return names

def main():
    repo_root = Path(os.getcwd())
    log(f"🚀 Starting Terraform drift analysis in {repo_root}")

    declared, used, tfvars_keys = set(), set(), set()

    # collect .tf & usage
    for path in glob.glob("**/*.tf", recursive=True):
        if should_skip(path): continue
        declared |= parse_declared_vars_from_tf(path)
        used |= parse_used_vars_from_tf(path)

    # collect .tfvars / .auto.tfvars / *.tfvars.json
    for path in glob.glob("**/*.tfvars*", recursive=True):
        if should_skip(path): continue
        tfvars_keys |= parse_tfvars(path)
    for path in glob.glob("**/*.tfvars.json", recursive=True):
        if should_skip(path): continue
        tfvars_keys |= parse_tfvars(path)

    ignore = load_ignorelist(repo_root)

    log("📊 Comparing variable sets...")
    unused = sorted((declared - used) - ignore)
    missing = sorted((used - declared) - ignore)
    tfvars_extra = sorted((tfvars_keys - declared) - ignore)

    log(f"🔸 Declared vars: {len(declared)}")
    log(f"🔸 Used vars: {len(used)}")
    log(f"🔸 tfvars vars: {len(tfvars_keys)}")
    log(f"🔸 Ignored vars: {len(ignore)}")

    if not unused and not missing and not tfvars_extra:
        log("✅ No variable drift detected.")
        return 0

    if unused:
        print(f"\n⚠️  Declared but not used: {unused}")
    if missing:
        print(f"\n❌ Used in code but not declared (check module boundaries or ignore list): {missing}")
    if tfvars_extra:
        print(f"\n⚠️  Present in tfvars but not declared: {tfvars_extra}")

    print("\n💡 Tip: add acceptable cross-module vars to .tfdriftignore (one per line).")
    return 1

if __name__ == "__main__":
    sys.exit(main())
