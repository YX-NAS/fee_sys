#!/usr/bin/env python3
"""
add_github_secret.py — 通过 GitHub API 添加 Actions Secret

使用方式:
  python3 add_github_secret.py <token> <owner> <repo> <secret_name> <secret_value>

依赖: pynacl (会自动安装)
"""
import sys
import json
import base64
import urllib.request
import urllib.error
import subprocess

# 自动安装 pynacl
try:
    from nacl import public, encoding
except ImportError:
    print("  安装 pynacl...", file=sys.stderr)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--user", "--quiet", "pynacl"],
        stderr=subprocess.DEVNULL,
    )
    from nacl import public, encoding


def api_request(url, token, method="GET", data=None):
    """发送 GitHub API 请求"""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 204:
                return None
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"GitHub API 错误 {e.code}: {error_body}") from e


def add_secret(token, owner, repo, secret_name, secret_value):
    """添加一个 GitHub Actions Secret"""
    api_base = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets"

    # 1. 获取仓库公钥
    key_data = api_request(f"{api_base}/public-key", token)
    public_key = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)

    # 2. 加密 secret 值
    encrypted = sealed_box.encrypt(secret_value.encode())
    encrypted_b64 = base64.b64encode(encrypted).decode()

    # 3. PUT secret
    result = api_request(
        f"{api_base}/{secret_name}",
        token,
        method="PUT",
        data={"encrypted_value": encrypted_b64, "key_id": key_data["key_id"]},
    )

    # PUT 返回 201=新建 或 204=更新
    print(f"  ✅ {secret_name} 已设置")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(f"用法: {sys.argv[0]} <token> <owner> <repo> <secret_name> <secret_value>")
        sys.exit(1)

    token, owner, repo, name, value = sys.argv[1:6]

    try:
        add_secret(token, owner, repo, name, value)
    except Exception as e:
        print(f"  ❌ 失败: {e}", file=sys.stderr)
        sys.exit(1)
