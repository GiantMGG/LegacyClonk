#!/usr/bin/env python3
"""playtest_vision.py -- Tier-2 playtest vision judge harness (cycle 108).

Spawns the console engine with --screenshot-at/--shot-size, deterministically
validates the PNG + SceneTruth sidecar (judge-independent RED layer: artifact
faults print "FAIL: artifact ..." and exit 1 before any judge contact), then
runs an ollama scene-judge battery behind oracle controls (photo positive +
flat-frame negatives). Stdlib only; imports the shared helpers from vision_qa.
SKIP-exit-0 without ollama keeps CI green.

Gate modes: advisory = record-only exit 0; feature = RED only on truth
contradictions (cross-check); full = contradictions RED + an unreadable
battery majority fails. Verdicts: GATE PASS / GATE FAIL / ADVISORY / SKIP /
ORACLE FAIL (ORACLE FAIL exits 0 -- a broken instrument never REDs, spec
s5 G4). Exit codes: 0 pass/skip/advisory, 1 fail/artifact, 2 usage/write.
"""
import argparse, base64, json, os, re, subprocess, sys, tempfile, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision_qa import (DEFAULT_HOST, DEFAULT_MODEL, FIXTURE_JPG, FLAT_RGB,
                       FLAT_H, FLAT_W, JudgeError, make_ask, majority,
                       png_decode, render_b64, strip_think, yes_first)

FRAME_RATE_CAP, SMOKE_TICKS, TAGS_TIMEOUT, FLAT_SCALE = 1000, 350, 5, 8
SIDECAR_KEYS = {"tick", "frame_counter", "view", "camera_source", "players",
                "objects", "capture"}  # full P5 key set (spec s1)
# Sky wording accepts black sky/space: above terrain the composed sky
# renders black (Surface32 palette[0], engine-inherent -- Task 3 finding).
SCENE_QUESTION = ("You are judging a diagnostic screenshot from a 2D "
                  "side-scrolling game. Look at the image and answer three "
                  "questions with factual observation only.\n"
                  "1. terrain: Is any terrain material (ground, rock, sand, "
                  "soil, grass) visible in the image?\n"
                  "2. figures: How many distinct small figures/objects "
                  "(characters, creatures, pickups, animals) are visible? "
                  "Count them.\n"
                  "3. sky: Is the upper region of the image empty sky/space "
                  "(open black or sky-colored space) with no terrain and no "
                  "objects in the upper part?\n"
                  'Return ONLY the JSON object {"terrain": bool, '
                  '"figures": int, "sky": bool}.')
SCENE_SCHEMA = {"type": "object",
                "properties": {"terrain": {"type": "boolean"},
                               "figures": {"type": "integer"},
                               "sky": {"type": "boolean"}},
                "required": ["terrain", "figures", "sky"]}

# -- engine capture (run_scenario idiom verbatim from playtest_sweep) --------
def run_capture(engine, scenario, shot_path, wdt, hgt, tick, timeout):
    """Spawn the engine once; returns (rc, log_text). stdin=DEVNULL is
    MANDATORY (an inherited piped stdin hangs the console engine)."""
    cmd = [engine, "--console", "--smoke-run", str(SMOKE_TICKS),
           "--frame-rate-cap", str(FRAME_RATE_CAP),
           "--screenshot-at", f"{tick}:{shot_path}",
           "--shot-size", f"{wdt}x{hgt}", "-s", scenario]
    grant = None
    passwords = []
    txt = os.path.join(os.path.dirname(scenario), "Scenario.txt")
    if os.path.isfile(txt):
        with open(txt, encoding="utf-8", errors="replace") as f:
            for line in f:
                key, sep, val = line.partition("=")
                if sep and key.strip().lower() == "missionaccess" and val.strip():
                    passwords.append(val.strip())
    if passwords:
        fd, grant = tempfile.mkstemp(suffix="_ptv_grant.cfg")
        os.close(fd)
        with open(grant, "w") as f:  # MUST be quoted; unquoted falls back ""
            f.write('[General]\nMissionAccess="' + ";".join(passwords) + '"\n')
        cmd.insert(-1, f"/config:{grant}")
    log = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    try:
        proc = subprocess.Popen(cmd, cwd=os.path.dirname(engine),
                                stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT)
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            rc = None
    except OSError as e:
        log.close()
        os.unlink(log.name)
        if grant:
            os.unlink(grant)
        raise JudgeError(f"cannot spawn engine {engine}: {e}")
    log.close()
    with open(log.name, encoding="utf-8", errors="replace") as f:
        log_text = f.read()
    os.unlink(log.name)
    if grant:
        os.unlink(grant)
    return rc, log_text

# -- deterministic artifact validation (judge-independent RED layer) --------
def parse_shot_size(s):
    """--shot-size WxH|W:H -> (w, h) argparse type."""
    m = re.match(r"^(\d+)[x:](\d+)$", s)
    if not m:
        raise argparse.ArgumentTypeError("--shot-size must be WxH or W:H")
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("--shot-size needs positive dims")
    return w, h

def validate_artifacts(png_path, sidecar_path, wdt, hgt, tick):
    """(ok, detail): PNG signature + IHDR dims + full key set + tick."""
    try:
        pw, ph, _ = png_decode(open(png_path, "rb").read())
    except OSError as e:
        return False, f"missing PNG {png_path}: {e}"
    except ValueError as e:
        return False, f"PNG decode failed: {e}"
    if (pw, ph) != (wdt, hgt):
        return False, f"PNG dims {pw}x{ph} != requested {wdt}x{hgt}"
    try:
        sidecar = json.load(open(sidecar_path, encoding="utf-8"))
    except OSError as e:
        return False, f"missing sidecar {sidecar_path}: {e}"
    except ValueError as e:
        return False, f"sidecar is not valid JSON: {e}"
    if not isinstance(sidecar, dict):
        return False, "sidecar is not a JSON object"
    missing = SIDECAR_KEYS - set(sidecar)
    if missing:
        return False, f"missing sidecar key(s): {sorted(missing)}"
    if not isinstance(sidecar.get("view"), dict):
        return False, "sidecar view is not an object"
    if sidecar.get("tick") != tick:
        return False, f"sidecar tick {sidecar.get('tick')} != requested {tick}"
    return True, sidecar

# -- ollama judge: SKIP probe, structured format ask, tolerant parse --------
def judge_reachable(host, model):
    """Probe /api/tags; prints SKIP and returns False when judge/model absent."""
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags",
                                    timeout=TAGS_TIMEOUT) as r:
            tags = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"SKIP: judge reachability check failed (HTTP {e.code})",
              flush=True)
        return False
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"SKIP: ollama unreachable ({getattr(e, 'reason', e)})",
              flush=True)
        return False
    names = [m.get("name", "") for m in tags.get("models", [])]
    if model not in names and model.lower() not in (n.lower() for n in names):
        print(f"SKIP: model '{model}' not present in ollama tags", flush=True)
        return False
    return True

def make_ask3(host, model, timeout):
    """ask3(image_b64) -> (parsed, raw, used_fallback). Sends the JSON-schema
    `format` body; on rejection retries plain-text via make_ask and parses."""
    plain = make_ask(host, model)  # internally uses its own CHAT_TIMEOUT
    body0 = {"model": model, "stream": False, "think": "high",
             "format": SCENE_SCHEMA, "options": {"temperature": 0}}
    def ask3(image_b64):
        body = dict(body0, messages=[{"role": "user", "content": SCENE_QUESTION,
                                      "images": [image_b64]}])
        req = urllib.request.Request(
            host.rstrip("/") + "/api/chat", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read())
            raw = strip_think((resp.get("message") or {}).get("content", ""))
            return parse_answer(raw), raw, False
        except urllib.error.HTTPError as e:
            print(f"[judge] structured format rejected (HTTP {e.code}) -- "
                  f"falling back to plain-text ask", flush=True)
            raw = plain(image_b64)
            return parse_answer(raw), raw, True
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise JudgeError(f"ollama /api/chat failed: {e}") from e
    return ask3

def _tf(v):
    """Coerce a judge field to True/False/None."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        low = v.strip().lower().strip(".,;:!?\"'()_*`")
        if low in ("yes", "y", "true"):
            return True
        if low in ("no", "n", "false"):
            return False
    return None

def parse_answer(raw):
    """Tolerant parse -> {terrain, figures, sky}; None = unreadable."""
    out = {"terrain": None, "figures": None, "sky": None}
    if not isinstance(raw, str) or not raw.strip():
        return out
    text = raw.strip()
    d = None
    try:
        d = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                d = json.loads(m.group(0))
            except ValueError:
                d = None
    if isinstance(d, dict):
        figs = d.get("figures")
        if isinstance(figs, str):
            mm = re.search(r"\d+", figs)
            figs = int(mm.group(0)) if mm else None
        elif isinstance(figs, (int, float)) and not isinstance(figs, bool):
            figs = int(figs)
        elif not isinstance(figs, bool):
            figs = None
        return {"terrain": _tf(d.get("terrain")), "figures": figs,
                "sky": _tf(d.get("sky"))}
    low = re.sub(r"\s+", " ", text.lower())
    m = re.search(r"\bterrain\b.{0,60}?\b(yes|no)\b", low)
    out["terrain"] = m.group(1) == "yes" if m else None
    m = re.search(r"\b(?:sky|upper region)\b.{0,60}?\b(yes|no)\b", low)
    out["sky"] = m.group(1) == "yes" if m else None
    if out["terrain"] is None or out["sky"] is None:
        first = (low.split() or [""])[0].strip(".,;:!?\"'()_*`")
        if first in ("yes", "y") or yes_first(text):
            out["terrain"] = True if out["terrain"] is None else out["terrain"]
            out["sky"] = True if out["sky"] is None else out["sky"]
        elif first in ("no", "n"):
            out["terrain"] = False if out["terrain"] is None else out["terrain"]
            out["sky"] = False if out["sky"] is None else out["sky"]
    mm = re.search(r"\d+", low)
    if mm:
        out["figures"] = int(mm.group(0))
    return out

def majority_count(counts):
    """Most frequent non-None value; None on tie or when none readable."""
    ranks = {}
    for v in (c for c in counts if c is not None):
        ranks[v] = ranks.get(v, 0) + 1
    if not ranks:
        return None
    best = max(ranks.values())
    winners = [v for v, n in ranks.items() if n == best]
    return None if len(winners) > 1 else winners[0]

# -- oracle controls (gated BEFORE any prompt verdict is trusted) -----------
def run_oracle(ask3, record):
    """Photo positive + flat-frame negatives; returns (ok, failure detail)."""
    try:
        photo = base64.b64encode(open(FIXTURE_JPG, "rb").read()).decode()
    except OSError as e:
        return False, f"cannot read photo fixture {FIXTURE_JPG}: {e}"
    parsed, raw, fb = ask3(photo)
    print(f"[oracle 1] photo: {raw}", flush=True)
    photo_ok = (parsed.get("terrain") is True and parsed.get("figures")
                is not None and parsed["figures"] >= 1
                and parsed.get("sky") is False)
    record["photo"] = {"answer": parsed, "raw": raw, "pass": photo_ok,
                       "format_fallback": fb}
    fail = None if photo_ok else (f"photo control: expected terrain=True "
        f"figures>=1 sky=False, got {parsed}")
    flat = [[(*FLAT_RGB, 255)] * FLAT_W for _ in range(FLAT_H)]
    parsed, raw, fb = ask3(render_b64(flat, FLAT_SCALE))
    print(f"[oracle 2] flat: {raw}", flush=True)
    flat_ok = (parsed.get("terrain") is False and parsed.get("figures") == 0
               and parsed.get("sky") is False)
    record["flat"] = {"answer": parsed, "raw": raw, "pass": flat_ok,
                      "format_fallback": fb}
    if not flat_ok:
        fail = (f"flat negative control: expected terrain=False figures=0 "
                f"sky=False, got {parsed}")
    record["pass"] = photo_ok and flat_ok
    record["failure"] = fail
    return record["pass"], fail

# -- judge battery + truth cross-check --------------------------------------
def run_battery(ask3, frame_b64, runs, record):
    """Structured runs on the captured frame; fills record['battery']."""
    cols = {k: [] for k in ("terrain", "figures", "sky")}
    for r in range(runs):
        parsed, raw, _ = ask3(frame_b64)
        print(f"[battery] run {r + 1}/{runs}: {raw}", flush=True)
        for k in cols:
            cols[k].append(parsed.get(k))
    b = {}
    for k, vals in cols.items():
        maj = (majority_count(vals) if k == "figures" else
               majority(vals) if all(v is not None for v in vals) else None)
        b[k] = {"answers": vals, "majority": maj, "abstention": maj is None}
    record["battery"] = b

def cross_check(battery, sidecar, shot_hgt):
    """Only truth CONTRADICTIONS can RED; abstentions are ADVISORY notes.
    -> (contradictions, notes)."""
    contr, notes = [], []
    view = sidecar.get("view") or {}
    vy = view.get("y", 0)
    objs = sidecar.get("objects") or []
    objs = objs if isinstance(objs, list) else []
    top = [o for o in objs if isinstance(o, dict)
           and isinstance(o.get("y"), (int, float))
           and 0 <= o["y"] - vy < shot_hgt // 4]
    t = battery["terrain"]["majority"]
    f = battery["figures"]["majority"]
    s = battery["sky"]["majority"]
    cap_ok = sidecar.get("capture") == "ok"
    if cap_ok:
        if t is False:
            contr.append("model says no terrain while sidecar capture=ok")
        elif t is None:
            notes.append("terrain answer unreadable (abstention)")
    if f is None:
        notes.append("figure count unreadable (abstention)")
    elif f < len(objs):
        contr.append(f"model counts {f} figures, sidecar has {len(objs)} "
                     "in-view object(s)")
    if s is None:
        notes.append("sky answer unreadable (abstention)")
    elif s is True and top:
        contr.append("model says empty sky/space while sidecar places "
                     "object(s) in the upper quarter of the frame")
    elif s is False and vy == 0 and cap_ok and not top:
        contr.append("model says no sky while sidecar view.y==0 (world "
                     "top = sky by composition)")
    return contr, notes

# -- main -------------------------------------------------------------------
def write_record(record, json_out, exit_code):
    """Shared --json-out writer; write failure still returns 2."""
    try:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
            f.write("\n")
    except OSError as e:
        print(f"ERROR: cannot write JSON record to {json_out}: {e}",
              file=sys.stderr)
        return 2
    return exit_code

def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", required=True, help="clonk binary")
    ap.add_argument("--scenario", required=True, help=".c4s scenario dir")
    ap.add_argument("--tick", type=int, default=120, help="capture tick")
    ap.add_argument("--shot-size", type=parse_shot_size, default="320x240",
                    help="WxH output dims")
    ap.add_argument("--work-dir", default="./ptv", help="artifact dir")
    ap.add_argument("--gate-mode", choices=["full", "feature", "advisory"],
                    default="advisory", help="gate strictness")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--runs", type=int, default=3,
                    help="judge runs per battery")
    ap.add_argument("--timeout", type=int, default=240,
                    help="per-call timeout; engine spawn + judge")
    ap.add_argument("--json-out", default=None,
                    help="record path (default: <work-dir>/record.json)")
    args = ap.parse_args()
    if args.runs < 1 or args.timeout < 1:
        print("ERROR: --runs and --timeout must be >= 1", file=sys.stderr)
        return 2
    engine = os.path.abspath(args.engine)
    scenario = os.path.abspath(args.scenario)
    wdt, hgt = args.shot_size
    work_dir = os.path.abspath(args.work_dir)
    shot_path = os.path.join(work_dir, "shot.png")
    sidecar_path = os.path.join(work_dir, "shot.json")
    json_out = args.json_out or os.path.join(work_dir, "record.json")
    record = {"engine": engine, "scenario": scenario, "tick": args.tick,
              "shot_size": f"{wdt}x{hgt}", "host": args.host,
              "model": args.model, "gate_mode": args.gate_mode,
              "runs": args.runs}

    # Capture stage FIRST (engine exercise happens even without a judge).
    try:
        os.makedirs(work_dir, exist_ok=True)
        rc, log_text = run_capture(engine, scenario, shot_path, wdt, hgt,
                                   args.tick, args.timeout)
    except OSError as e:
        print(f"FAIL: artifact cannot use work-dir {work_dir}: {e}",
              flush=True)
        return 1
    except JudgeError as e:
        print(f"FAIL: artifact {e}", flush=True)
        return 1
    record["capture"] = {"exit_code": rc, "log_tail": log_text[-400:]}

    # Deterministic artifact validation (RED layer, judge-independent).
    ok, detail = validate_artifacts(shot_path, sidecar_path, wdt, hgt, args.tick)
    if not ok:
        print(f"FAIL: artifact {detail}", flush=True)
        return 1
    sidecar = detail
    objs = sidecar.get("objects") if isinstance(sidecar.get("objects"), list) else []
    print(f"shot.png {wdt}x{hgt} objects={len(objs)} "
          f"capture={sidecar.get('capture')}", flush=True)
    record["sidecar"] = {k: sidecar.get(k) for k in SIDECAR_KEYS}

    # SKIP path (exit 0): judge unreachable or model absent.
    if not judge_reachable(args.host, args.model):
        record["verdict"] = "SKIP"
        return write_record(record, json_out, 0)
    try:
        ask3 = make_ask3(args.host, args.model, args.timeout)
    except JudgeError as e:
        print(f"SKIP: ollama unreachable ({e})", flush=True)
        record["verdict"] = "SKIP"
        return write_record(record, json_out, 0)

    # Oracle controls gate every prompt verdict.
    oracle_rec = {}
    try:
        oracle_ok, oracle_fail = run_oracle(ask3, oracle_rec)
    except JudgeError as e:
        print(f"SKIP: judge failed during oracle ({e})", flush=True)
        record["verdict"] = "SKIP"
        return write_record(record, json_out, 0)
    record["oracle"] = oracle_rec
    if not oracle_ok:
        print(f"ORACLE FAIL: {oracle_fail}", flush=True)
        print("ORACLE FAIL: verdict not trusted (broken instrument)",
              flush=True)

    frame_b64 = base64.b64encode(open(shot_path, "rb").read()).decode()
    battery_rec = {}
    try:
        run_battery(ask3, frame_b64, args.runs, battery_rec)
        contr, notes = cross_check(battery_rec["battery"], sidecar, hgt)
    except JudgeError as e:
        print(f"SKIP: judge failed mid-battery ({e})", flush=True)
        record["verdict"] = "SKIP"
        return write_record(record, json_out, 0)
    record["battery"] = battery_rec["battery"]
    record["cross_check"] = {"contradictions": contr, "notes": notes,
                             "sidecar_object_count": len(objs)}
    for n in notes:
        print(f"[note] {n}", flush=True)
    for c in contr:
        print(f"[contr] {c}", flush=True)

    # Only truth contradictions can RED (feature/full); full also fails on
    # an unreadable battery majority.
    if not oracle_ok:
        verdict, code = "ORACLE FAIL", 0
    elif args.gate_mode == "advisory":
        verdict, code = "ADVISORY", 0
    elif contr:
        verdict, code = "GATE FAIL", 1
    elif args.gate_mode == "full" and any(
            battery_rec["battery"][k]["abstention"]
            for k in ("terrain", "figures", "sky")):
        verdict, code = "GATE FAIL", 1
    else:
        verdict, code = "GATE PASS", 0
    print(verdict, flush=True)
    record["verdict"] = verdict
    return write_record(record, json_out, code)

if __name__ == "__main__":
    sys.exit(main())
