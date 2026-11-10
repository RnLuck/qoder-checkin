#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gist 状态同步 · gist_store.py（云端签到用）
════════════════════════════════════════════════════════════
把 qoder_config.json（设备标识）+ qoder_accounts.json（token）存到一个
私有 Gist，供 GitHub Actions 每次运行时拉取/回写，解决 token 轮换持久化。

环境变量：
    GH_GIST_TOKEN  有 gist 权限的 GitHub PAT（经典 token 勾 gist；或细粒度授权 Gist 读写）
    GIST_ID        目标 gist 的 ID（init 命令会创建并打印）

用法：
    python gist_store.py init [源目录]   # 从源目录(默认 ../qoder)读取两个 json，创建私有 gist
    python gist_store.py pull            # 从 gist 拉取两个 json 到本脚本所在目录
    python gist_store.py push            # 把本目录的两个 json 回写到 gist

安全：token 只经 GitHub API 传输，绝不打印。私有 gist 凭链接可访问，
务必把 GIST_ID 放在仓库 Secret、仓库设为 private，不要泄露 gist 链接。
"""
import json
import os
import sys
import urllib.error
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com"
TOKEN = os.getenv("GH_GIST_TOKEN", "").strip()
GIST_ID = os.getenv("GIST_ID", "").strip()
FILES = ["qoder_config.json", "qoder_accounts.json"]


def _req(method, url, body=None):
    headers = {
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "qoder-checkin",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:200]
        raise SystemExit("GitHub API HTTP %s: %s" % (e.code, msg))
    except Exception as e:
        raise SystemExit("GitHub API 请求失败: %s" % e)


def pull():
    g = _req("GET", API + "/gists/" + GIST_ID)
    files = g.get("files", {})
    for name in FILES:
        f = files.get(name)
        if f and f.get("content"):
            with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
                fh.write(f["content"])
            print("  ⬇️ pull:", name)
        else:
            print("  ⚠️ gist 缺少文件:", name)


def push():
    files = {}
    for name in FILES:
        p = os.path.join(HERE, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                files[name] = {"content": fh.read()}
    if not files:
        print("  （无文件可回写）")
        return
    _req("PATCH", API + "/gists/" + GIST_ID, {"files": files})
    print("  ⬆️ push:", ", ".join(files))


def init(src):
    files = {}
    for name in FILES:
        p = os.path.join(src, name)
        if not os.path.isfile(p):
            raise SystemExit("缺少源文件 %s —— 先在本地跑过 qoder_extract.py" % p)
        with open(p, encoding="utf-8") as fh:
            files[name] = {"content": fh.read()}
    g = _req("POST", API + "/gists",
             {"description": "qoder-checkin state (private)", "public": False, "files": files})
    print("  ✅ 已创建私有 gist")
    print("  GIST_ID=" + g["id"])
    print("  URL=" + g.get("html_url", ""))
    print("  请把 GIST_ID 和 GH_GIST_TOKEN 设为仓库 Secret。")


def main():
    if not TOKEN:
        raise SystemExit("请先设置环境变量 GH_GIST_TOKEN（有 gist 权限的 PAT）")
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if cmd == "init":
        src = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "qoder"))
        print("从 %s 创建私有 gist ..." % src)
        init(src)
    elif cmd in ("pull", "push"):
        if not GIST_ID:
            raise SystemExit("请先设置环境变量 GIST_ID")
        (pull if cmd == "pull" else push)()
    else:
        raise SystemExit("用法: gist_store.py init [源目录] | pull | push")


if __name__ == "__main__":
    main()