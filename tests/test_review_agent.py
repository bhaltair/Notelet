import json

import pytest

from scripts import review_agent


def test_resolve_run_config_prefers_cli_args_over_environment():
    # 本地 dry-run 时，命令行参数应该覆盖 CI 注入的环境变量。
    parser = review_agent.build_parser()
    args = parser.parse_args(["--base", "origin/main", "--head", "HEAD~1", "--model", "review-model"])

    config = review_agent.resolve_run_config(
        args,
        {
            "BASE_SHA": "env-base",
            "HEAD_SHA": "env-head",
            "OPENAI_MODEL": "env-model",
        },
    )

    assert config == {
        "base_ref": "origin/main",
        "head_ref": "HEAD~1",
        "model": "review-model",
    }


def test_resolve_run_config_uses_environment_defaults():
    # CI 路径主要依赖环境变量；未传 --head/--model 时使用脚本默认值。
    parser = review_agent.build_parser()
    args = parser.parse_args([])

    config = review_agent.resolve_run_config(args, {"BASE_SHA": "base-sha"})

    assert config == {
        "base_ref": "base-sha",
        "head_ref": "HEAD",
        "model": "gpt-5.4-mini",
    }


def test_load_dotenv_sets_missing_values_without_overrides(tmp_path):
    # 本地运行 review agent 时应能读取 .env，但不能覆盖 shell 临时设置。
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=dotenv-key",
                "OPENAI_MODEL=dotenv-model",
                "OPENAI_BASE_URL=https://example.test",
            ]
        ),
        encoding="utf-8",
    )
    environ = {"OPENAI_MODEL": "shell-model"}

    review_agent.load_dotenv(env_path, environ)

    assert environ == {
        "OPENAI_API_KEY": "dotenv-key",
        "OPENAI_MODEL": "shell-model",
        "OPENAI_BASE_URL": "https://example.test",
    }


def test_load_dotenv_ignores_missing_blank_and_comment_lines(tmp_path):
    # 空值和注释不应该污染环境变量。
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(["# comment", "OPENAI_API_KEY=", "MALFORMED", "OPENAI_MODEL='quoted-model'"]),
        encoding="utf-8",
    )
    environ = {}

    review_agent.load_dotenv(env_path, environ)
    review_agent.load_dotenv(tmp_path / "missing.env", environ)

    assert environ == {"OPENAI_MODEL": "quoted-model"}


def test_parse_review_json_accepts_fenced_json():
    # 兼容模型偶尔返回 ```json fenced block 的情况。
    payload = {
        "summary": "Adds a review agent.",
        "risk_level": "low",
        "findings": [
            {
                "severity": "P2",
                "confidence": 0.75,
                "file": "scripts/review_agent.py",
                "line": 10,
                "title": "Missing failure handling",
                "body": "The script does not handle malformed model output.",
                "suggestion": "Validate the JSON response before posting.",
            }
        ],
        "test_gaps": [],
        "release_note_needed": False,
    }

    parsed = review_agent.parse_review_json(
        "```json\n" + json.dumps(payload) + "\n```"
    )

    assert parsed["summary"] == "Adds a review agent."
    assert parsed["findings"][0]["severity"] == "P2"


def test_parse_review_json_rejects_invalid_severity():
    # severity 是后续阻断策略的输入，必须限制在约定枚举内。
    payload = {
        "findings": [
            {
                "severity": "Critical",
                "confidence": 0.9,
                "file": "tools.py",
                "title": "Bad severity",
                "body": "This should fail validation.",
            }
        ]
    }

    with pytest.raises(ValueError, match="Invalid severity"):
        review_agent.parse_review_json(json.dumps(payload))


def test_render_review_markdown_includes_marker_and_findings():
    # marker 用来更新同一条 PR 评论，避免每次 push 都重复刷屏。
    review = {
        "summary": "Adds CI review.",
        "risk_level": "medium",
        "findings": [
            {
                "severity": "P1",
                "confidence": 0.91,
                "file": "agent.py",
                "line": 42,
                "title": "Hard-coded tool dispatch",
                "body": "The change bypasses ToolRegistry.",
                "suggestion": "Route the tool through ToolRegistry.",
            }
        ],
        "test_gaps": [{"file": "tests/test_agent.py", "body": "Add a registry test."}],
        "release_note_needed": True,
    }

    markdown = review_agent.render_review_markdown(review)

    assert review_agent.COMMENT_MARKER in markdown
    assert "#### P1: Hard-coded tool dispatch" in markdown
    assert "`agent.py:42`" in markdown
    assert "`tests/test_agent.py`: Add a registry test." in markdown
    assert "CHANGELOG.md update appears to be needed" in markdown


def test_blocking_findings_require_high_confidence_p0_or_p1():
    # 第一版只把高置信度 P0/P1 当成可阻断问题，P2 及以下只评论。
    assert review_agent.has_blocking_findings(
        {"findings": [{"severity": "P1", "confidence": 0.8}]}
    )
    assert not review_agent.has_blocking_findings(
        {"findings": [{"severity": "P1", "confidence": 0.79}]}
    )
    assert not review_agent.has_blocking_findings(
        {"findings": [{"severity": "P2", "confidence": 1.0}]}
    )
