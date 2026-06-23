"""E2E 组卷驱动：往年卷 → interact 出方案 → 教师选 → handoff → pipeline。

分阶段驱动 interact v2 API（端口 3001）。每阶段把状态写到 /tmp/e2e_state.json。

用法:
  python scripts/e2e_paper_drive.py turn1     # 建 session + 发往年卷 + 出方案
  python scripts/e2e_paper_drive.py draft     # 取当前草案
  python scripts/e2e_paper_drive.py turn --msg "..." [--intent discuss|request_revision|confirm_handoff]
  python scripts/e2e_paper_drive.py progress  # pipeline 进度
  python scripts/e2e_paper_drive.py result    # display-result
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

BASE = f"http://127.0.0.1:{os.getenv('E2E_PORT', '3001')}/api/v2/interact"
STATE = "/tmp/e2e_state.json"
USER_ID = "e2e_paper"
PROVIDER = os.getenv("E2E_PROVIDER", "glm5.2_anthropic")
PAPER = "/zhaoshu/llm_eduated_code_as_truth/data/期末A卷_参考.md"


def _req(method, path, body=None, timeout=600):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:500]}
    except Exception as e:
        return {"_error": str(e)}


def _load():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def _save(d):
    json.dump(d, open(STATE, "w"), ensure_ascii=False, indent=2)


def cmd_turn1():
    s = _load()
    if "session_id" not in s:
        print("=== create session ===")
        c = _req("POST", "/sessions", {"provider": PROVIDER, "thinking": True,
                                         "ui_mode": "api", "user_id": USER_ID})
        print(json.dumps(c, ensure_ascii=False)[:300])
        sid = c.get("session_id") or c.get("id")
        if not sid:
            print("CREATE FAILED:", c); sys.exit(1)
        s["session_id"] = sid
        _save(s)
    sid = s["session_id"]
    paper = open(PAPER, encoding="utf-8").read()
    msg = (
        "我想出一套【数据结构】期末考试 A 卷（闭卷 120 分钟，满分 100）。"
        "请先 read_file 读取参考往年卷（路径 data/期末A卷_参考.md，内容也见下方），"
        "参考它的题型结构与难度分布（选择 20 / 应用 40 / 算法分析 10 / 算法设计 30），"
        "**但具体考点必须重组、不得照搬原卷**。生成 2-3 套知识点组合方案（方案已到考法级），"
        "我会在每套方案里为每个题位选一个考察方向。\n\n"
        f"=== 参考往年卷（数据结构期末 A 卷）===\n{paper}"
    )
    print(f"=== turn1: send paper + request (session {sid}) ===")
    t0 = time.time()
    r = _req("POST", f"/sessions/{sid}/turn", {"message": msg, "intent": "discuss"}, timeout=900)
    dt = time.time() - t0
    s["turn1"] = {"dt": dt, "resp": r}
    _save(s)
    print(f"turn1 done in {dt:.0f}s | has_draft={r.get('has_draft')} has_result={r.get('has_result')}")
    print("--- response_text ---")
    print((r.get("response_text") or "")[:1500])


def cmd_draft():
    s = _load()
    sid = s.get("session_id")
    if not sid:
        print("no session; run turn1 first"); sys.exit(1)
    d = _req("GET", f"/sessions/{sid}/draft")
    print(json.dumps(d, ensure_ascii=False, indent=2)[:4000])


def cmd_turn(msg, intent):
    s = _load()
    sid = s.get("session_id")
    r = _req("POST", f"/sessions/{sid}/turn", {"message": msg, "intent": intent}, timeout=900)
    s.setdefault("turns", []).append({"msg": msg[:120], "intent": intent, "resp_keys": list(r.keys())})
    _save(s)
    print(f"turn (intent={intent}) has_draft={r.get('has_draft')} has_result={r.get('has_result')}")
    print((r.get("response_text") or "")[:1500])


def cmd_progress():
    s = _load()
    sid = s.get("session_id")
    print(json.dumps(_req("GET", f"/sessions/{sid}/pipeline-progress"), ensure_ascii=False)[:1500])


def cmd_result():
    s = _load()
    sid = s.get("session_id")
    r = _req("GET", f"/sessions/{sid}/display-result")
    out = json.dumps(r, ensure_ascii=False)
    print(out[:6000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("turn1")
    sub.add_parser("draft")
    t = sub.add_parser("turn")
    t.add_argument("--msg", required=True)
    t.add_argument("--intent", default="discuss")
    sub.add_parser("progress")
    sub.add_parser("result")
    a = ap.parse_args()
    {"turn1": cmd_turn1, "draft": cmd_draft, "turn": lambda: cmd_turn(a.msg, a.intent),
     "progress": cmd_progress, "result": cmd_result}[a.cmd]()
