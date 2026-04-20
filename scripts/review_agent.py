import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from openai import OpenAI


COMMENT_MARKER = "<!-- notelet-review-agent -->"
# 下面这些常量控制 review agent 的输入规模和阻断策略，方便后续渐进调优。
MAX_DIFF_CHARS = 60000
MAX_CONTEXT_CHARS = 20000
BLOCKING_SEVERITIES = {"P0", "P1"}
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def build_parser():
    # 同一份脚本同时服务 CI 和本地 dry-run；CLI 参数主要照顾本地调试。
    parser = argparse.ArgumentParser(description="Run the Notelet PR review agent.")
    parser.add_argument("--dry-run", action="store_true", help="Print review markdown instead of posting it.")
    parser.add_argument("--base", help="Base git ref for local review, such as origin/main or a commit SHA.")
    parser.add_argument("--head", help="Head git ref for local review. Defaults to HEAD.")
    parser.add_argument("--model", help="OpenAI-compatible chat model to use.")
    parser.add_argument("--env-file", default=str(ENV_PATH), help="Path to a dotenv file. Defaults to .env.")
    return parser


def resolve_run_config(args, environ):
    # CI 用 BASE_SHA/HEAD_SHA，本地可以用 --base/--head 覆盖。
    return {
        "base_ref": args.base or environ.get("BASE_SHA"),
        "head_ref": args.head or environ.get("HEAD_SHA", "HEAD"),
        "model": args.model or environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
    }


def load_dotenv(env_path, environ=os.environ):
    path = Path(env_path)
    if not path.exists():
        return

    # 和主 CLI 一样：shell 里的临时变量优先于 .env。
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value and key not in environ:
            environ[key] = value


def normalize_openai_environment(environ=os.environ):
    # GitHub Actions 的空 variable 会变成空字符串；OpenAI SDK 会把它当成 URL。
    if "OPENAI_BASE_URL" in environ and not environ["OPENAI_BASE_URL"].strip():
        del environ["OPENAI_BASE_URL"]


def run_command(args):
    # Windows 默认编码可能是 GBK；git diff 里有 UTF-8 字符时要显式解码。
    result = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def read_text(path, max_chars=None):
    text = Path(path).read_text(encoding="utf-8")
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + "\n[truncated]\n"
    return text


def collect_diff(base_sha, head_sha):
    # 使用三点 diff，保持和 PR 相对 base branch 的语义一致。
    return run_command(["git", "diff", "--find-renames", f"{base_sha}...{head_sha}"])


def collect_changed_files(base_sha, head_sha):
    output = run_command(
        ["git", "diff", "--name-only", "--find-renames", f"{base_sha}...{head_sha}"]
    )
    return [line for line in output.splitlines() if line.strip()]


def compact_diff(diff):
    # 控制输入长度，避免大 PR 把模型上下文全部吃完。
    if len(diff) <= MAX_DIFF_CHARS:
        return diff
    return diff[:MAX_DIFF_CHARS] + "\n[diff truncated]\n"


def build_user_prompt(diff, changed_files, project_context):
    # 模型只拿到必要输入：文件列表、项目规则上下文、以及本次 PR diff。
    return "\n\n".join(
        [
            "Review this pull request for Notelet.",
            "Changed files:\n" + "\n".join(f"- {name}" for name in changed_files),
            "Project context:\n" + project_context,
            "Pull request diff:\n```diff\n" + compact_diff(diff) + "\n```",
        ]
    )


def load_project_context():
    # 只读取少量稳定上下文，让 review agent 知道项目规则但不过度扩散。
    parts = []
    for filename in ["AGENTS.md", "pyproject.toml", "README.md"]:
        path = Path(filename)
        if path.exists():
            parts.append(f"## {filename}\n{read_text(path, MAX_CONTEXT_CHARS // 3)}")
    return "\n\n".join(parts)


def strip_json_fence(text):
    # 有些模型即使被要求返回 JSON，也会包一层 ```json。
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_review_json(text):
    # 模型输出先转成结构化数据，再由本地代码决定怎么展示或是否阻断。
    data = json.loads(strip_json_fence(text))
    if not isinstance(data, dict):
        raise ValueError("Review response must be a JSON object.")

    findings = data.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings must be a list.")

    for finding in findings:
        # 严格校验输出，避免把不可行动或不可分级的结果发到 PR。
        if finding.get("severity") not in {"P0", "P1", "P2", "P3", "Info"}:
            raise ValueError(f"Invalid severity: {finding.get('severity')}")
        confidence = finding.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("finding confidence must be between 0 and 1.")
        if not finding.get("file") or not finding.get("title") or not finding.get("body"):
            raise ValueError("finding must include file, title, and body.")

    test_gaps = data.get("test_gaps", [])
    if not isinstance(test_gaps, list):
        raise ValueError("test_gaps must be a list.")

    data.setdefault("summary", "")
    data.setdefault("risk_level", "low")
    data.setdefault("release_note_needed", False)
    return data


def render_review_markdown(review):
    # GitHub PR 评论最终只是一段 Markdown；这里集中控制展示格式。
    lines = [
        COMMENT_MARKER,
        "## Review Agent",
        "",
        f"Risk: **{review.get('risk_level', 'low')}**",
    ]

    summary = review.get("summary")
    if summary:
        lines.extend(["", summary])

    findings = review.get("findings", [])
    if findings:
        lines.extend(["", "### Findings"])
        for finding in findings:
            location = finding["file"]
            if finding.get("line"):
                location = f"{location}:{finding['line']}"
            lines.extend(
                [
                    "",
                    f"#### {finding['severity']}: {finding['title']}",
                    f"`{location}` | confidence: {finding.get('confidence', 0):.2f}",
                    "",
                    finding["body"],
                ]
            )
            if finding.get("suggestion"):
                lines.extend(["", f"Suggestion: {finding['suggestion']}"])
    else:
        lines.extend(["", "No actionable findings."])

    test_gaps = review.get("test_gaps", [])
    if test_gaps:
        lines.extend(["", "### Test Gaps"])
        for gap in test_gaps:
            file_label = gap.get("file", "tests")
            lines.append(f"- `{file_label}`: {gap.get('body', '')}")

    if review.get("release_note_needed"):
        lines.extend(["", "### Release Notes", "A CHANGELOG.md update appears to be needed."])

    return "\n".join(lines).strip() + "\n"


def has_blocking_findings(review):
    # 第一版默认不阻断；即使开启阻断，也只接受高置信度 P0/P1。
    for finding in review.get("findings", []):
        if finding.get("severity") in BLOCKING_SEVERITIES and finding.get("confidence", 0) >= 0.8:
            return True
    return False


def call_model(system_prompt, user_prompt, model):
    # 这里保持 OpenAI-compatible Chat Completions 接口，和主 agent runtime 一致。
    normalize_openai_environment()
    client = OpenAI()
    request = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    if os.environ.get("REVIEW_AGENT_JSON_MODE", "true") == "true":
        # 保留开关，兼容不支持 response_format 的 OpenAI-compatible provider。
        request["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**request)
    return response.choices[0].message.content


def github_request(method, url, token, payload=None):
    # 只使用标准库发 GitHub API 请求，避免为 CI 评论功能再加依赖。
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else None


def upsert_pr_comment(repo, pr_number, token, body):
    # 用隐藏 marker 更新同一条评论，避免每次 push 都刷出一条新评论。
    base_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    comments = github_request("GET", base_url, token)
    for comment in comments:
        if COMMENT_MARKER in comment.get("body", ""):
            return github_request("PATCH", comment["url"], token, {"body": body})
    return github_request("POST", base_url, token, {"body": body})


def main():
    # 主流程：读配置 -> 收集 diff -> 调模型 -> 校验 JSON -> 输出/更新 PR 评论。
    parser = build_parser()
    args = parser.parse_args()
    load_dotenv(args.env_file)
    config = resolve_run_config(args, os.environ)

    if not config["base_ref"]:
        print("BASE_SHA or --base is required.", file=sys.stderr)
        return 2
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set; skipping review agent.")
        return 0

    system_prompt = read_text("prompts/review_agent.md")
    changed_files = collect_changed_files(config["base_ref"], config["head_ref"])
    diff = collect_diff(config["base_ref"], config["head_ref"])
    user_prompt = build_user_prompt(diff, changed_files, load_project_context())
    raw_review = call_model(system_prompt, user_prompt, config["model"])
    review = parse_review_json(raw_review)
    markdown = render_review_markdown(review)

    if args.dry_run or not os.environ.get("GITHUB_ACTIONS"):
        print(markdown)
    else:
        repo = os.environ["GITHUB_REPOSITORY"]
        pr_number = os.environ["PR_NUMBER"]
        token = os.environ["GITHUB_TOKEN"]
        upsert_pr_comment(repo, pr_number, token, markdown)

    if has_blocking_findings(review) and os.environ.get("REVIEW_AGENT_FAIL_ON_BLOCKING") == "true":
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.CalledProcessError, urllib.error.HTTPError, ValueError, json.JSONDecodeError) as error:
        print(f"review_agent failed: {error}", file=sys.stderr)
        raise SystemExit(2)
