#!/usr/bin/env python3
"""Synchronize openclaw/openclaw's skills subtree into a CC Switch repository."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
import urllib.parse
import urllib.request

UPSTREAM_OWNER = "openclaw"
UPSTREAM_REPO = "openclaw"
UPSTREAM_BRANCH = "main"
UPSTREAM_SUBDIRECTORY = "skills"
UPSTREAM_REPOSITORY_URL = "https://github.com/openclaw/openclaw"
UPSTREAM_SKILLS_URL = f"{UPSTREAM_REPOSITORY_URL}/tree/{UPSTREAM_BRANCH}/{UPSTREAM_SUBDIRECTORY}"
ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".openclaw" / "upstream.json"
RESERVED_ROOT_NAMES = {".git", ".github", ".openclaw", "scripts", "README.md"}


def run(*args: str, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def github_json(path: str, query: dict[str, str] | None = None):
    url = f"https://api.github.com{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Marco9442/openclaw-skills sync workflow",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def clone_upstream(destination: Path) -> str:
    run(
        "git",
        "clone",
        "--depth=1",
        "--filter=blob:none",
        "--sparse",
        "--branch",
        UPSTREAM_BRANCH,
        UPSTREAM_REPOSITORY_URL + ".git",
        str(destination),
    )
    run("git", "sparse-checkout", "set", UPSTREAM_SUBDIRECTORY, cwd=destination)
    return run("git", "rev-parse", "HEAD", cwd=destination)


def file_mode(path: Path) -> str:
    return "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"


def collect_candidates(upstream: Path) -> tuple[list[dict], int, str, str]:
    package = json.loads((upstream / "package.json").read_text(encoding="utf-8"))
    version = str(package["version"])
    license_id = str(package["license"])
    if license_id != "MIT":
        raise RuntimeError(f"Unexpected OpenClaw license: {license_id!r}")

    sources: list[tuple[Path, PurePosixPath, str]] = []
    skills_root = upstream / UPSTREAM_SUBDIRECTORY
    for source in sorted(skills_root.rglob("*")):
        if source.is_symlink():
            raise RuntimeError(f"Symlink is not allowed in upstream skills: {source}")
        if not source.is_file():
            continue
        relative = PurePosixPath(source.relative_to(skills_root).as_posix())
        if relative.parts[0] in RESERVED_ROOT_NAMES:
            raise RuntimeError(f"Upstream path conflicts with mirror infrastructure: {relative}")
        sources.append((source, relative, f"skills/{relative.as_posix()}"))

    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        source = upstream / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"Required upstream licensing file is missing: {name}")
        sources.append((source, PurePosixPath(name), name))

    records: list[dict] = []
    skill_dirs: set[PurePosixPath] = set()
    for source, local_path, source_path in sorted(sources, key=lambda item: item[1].as_posix()):
        data = source.read_bytes()
        if local_path.name == "SKILL.md":
            text = data.decode("utf-8-sig")
            if not text.lstrip().startswith("---"):
                raise RuntimeError(f"SKILL.md lacks YAML frontmatter: {source_path}")
            skill_dirs.add(local_path.parent)
        records.append(
            {
                "path": local_path.as_posix(),
                "sourcePath": source_path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
                "mode": file_mode(source),
                "_source": source,
            }
        )

    for directory in skill_dirs:
        if any(parent in skill_dirs for parent in directory.parents if parent != PurePosixPath(".")):
            raise RuntimeError(f"Nested skills are not fully discoverable by CC Switch: {directory}")
    if not skill_dirs:
        raise RuntimeError("No SKILL.md files found in upstream skills subtree")

    return records, len(skill_dirs), version, license_id


def digest_records(records: list[dict]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["path"].encode())
        digest.update(b"\0")
        digest.update(record["mode"].encode())
        digest.update(b"\0")
        digest.update(record["sha256"].encode())
        digest.update(b"\n")
    return digest.hexdigest()


def previous_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def remove_previous_files(state: dict) -> None:
    paths = [PurePosixPath(item["path"]) for item in state.get("files", [])]
    for relative in sorted(paths, key=lambda path: len(path.parts), reverse=True):
        target = ROOT / relative.as_posix()
        if target.is_file() or target.is_symlink():
            target.unlink()
    directories = {path.parent for path in paths if path.parent != PurePosixPath(".")}
    for relative in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        target = ROOT / relative.as_posix()
        try:
            target.rmdir()
        except (FileNotFoundError, OSError):
            pass


def copy_records(records: list[dict]) -> list[dict]:
    clean_records: list[dict] = []
    for record in records:
        target = ROOT / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(record["_source"], target)
        target.chmod(0o755 if record["mode"] == "100755" else 0o644)
        clean_records.append({key: value for key, value in record.items() if key != "_source"})
    return clean_records


def write_readme(
    version: str,
    license_id: str,
    source_commit: str,
    skills_commit: str,
    skills_commit_date: str,
    skill_count: int,
    file_count: int,
) -> None:
    short_source = source_commit[:12]
    short_skills = skills_commit[:12]
    content = f"""# openclaw-skills

[![Sync OpenClaw skills](https://github.com/Marco9442/openclaw-skills/actions/workflows/sync-upstream.yml/badge.svg)](https://github.com/Marco9442/openclaw-skills/actions/workflows/sync-upstream.yml)

这是 OpenClaw 官方仓库 [`openclaw/openclaw` 的 `skills/` 目录]({UPSTREAM_SKILLS_URL})的**自动同步公开镜像**，按 CC Switch 可直接扫描的多 Skill GitHub 仓库格式发布。

上游 `skills/<skill-name>/...` 会被同步到本仓库 `<skill-name>/...`。每个技能目录保留其原始 `SKILL.md` 和配套文件，CC Switch 无需依赖额外清单即可递归识别。

## 当前镜像

- OpenClaw 版本：`{version}`
- 上游分支：`{UPSTREAM_BRANCH}`
- 同步快照提交：[`{short_source}`]({UPSTREAM_REPOSITORY_URL}/commit/{source_commit})
- `skills/` 最近变更提交：[`{short_skills}`]({UPSTREAM_REPOSITORY_URL}/commit/{skills_commit})
- `skills/` 最近变更时间：`{skills_commit_date}`
- 可识别 Skills：`{skill_count}`
- 同步文件：`{file_count}`
- 上游许可证：`{license_id}`
- 来源清单：[`.openclaw/upstream.json`](.openclaw/upstream.json)

## 在 CC Switch 中添加

打开 **Skills → 仓库管理 → 添加仓库**，填写：

| 字段 | 值 |
|---|---|
| Owner | `Marco9442` |
| Name | `openclaw-skills` |
| Branch | `main` |
| Subdirectory | 留空 |

> [!IMPORTANT]
> **CC Switch v3.20.0 不要直接添加 `openclaw/openclaw` 或带 `/tree/main/skills` 的官方 URL。** 当前版本只保存 Owner、Name 和 Branch，下载时仍会获取整个 OpenClaw 仓库，不能只下载 `skills/` 子目录。OpenClaw 完整 ZIP 约有 35,000 个条目，超过 CC Switch 的 10,000 条目安全上限，因此会显示“识别到 0 个技能”。请删除旧的 `openclaw/openclaw` 条目，只保留 `Marco9442/openclaw-skills`。

CC Switch 会递归扫描仓库中的 `SKILL.md`，因此仓库根目录下的各技能可以直接显示、安装和更新。

对应仓库地址：

```text
https://github.com/Marco9442/openclaw-skills
```

## 自动同步机制

GitHub Actions 工作流 [`.github/workflows/sync-upstream.yml`](.github/workflows/sync-upstream.yml) 会：

1. 每 6 小时检查 `openclaw/openclaw@main`。
2. 以 sparse clone 方式只获取 `skills/` 和必要的许可证信息。
3. 将 `skills/` 子树完整同步到仓库根目录，包括文件增删、内容和可执行权限。
4. 校验所有技能均包含带 YAML frontmatter 的 `SKILL.md`，并防止路径覆盖镜像基础设施。
5. 更新上游提交、OpenClaw 版本和逐文件 SHA-256 清单。
6. 仅当同步内容实际变化时提交；无变化时正常结束，不产生空提交。

同步提交由 `github-actions[bot]` 创建，格式为：

```text
chore(sync): update OpenClaw skills to <commit>
```

## 来源与许可证

技能原始来源为 [`openclaw/openclaw/skills`]({UPSTREAM_SKILLS_URL})。本仓库保留 OpenClaw 的 [`LICENSE`](LICENSE) 和 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。所有上游内容的权利归其原作者和权利人所有。

本仓库不是独立开发分支。除 README、同步脚本、Workflow 和来源清单外，不对上游技能内容进行改写。
"""
    (ROOT / "README.md").write_text(content, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="openclaw-skills-") as temp:
        upstream = Path(temp) / "openclaw"
        source_commit = clone_upstream(upstream)
        records, skill_count, version, license_id = collect_candidates(upstream)
        content_sha = digest_records(records)
        old_state = previous_state()
        if old_state.get("contentSha256") == content_sha:
            print(
                f"OpenClaw skills are already current: "
                f"{old_state.get('skillsCommit', source_commit)[:12]} "
                f"({skill_count} skills, {len(records)} files)"
            )
            return

        commits = github_json(
            f"/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/commits",
            {"sha": source_commit, "path": UPSTREAM_SUBDIRECTORY, "per_page": "1"},
        )
        if not commits:
            raise RuntimeError("GitHub returned no commit history for the skills subtree")
        skills_commit = commits[0]["sha"]
        skills_commit_date = commits[0]["commit"]["author"]["date"]

        remove_previous_files(old_state)
        clean_records = copy_records(records)
        write_readme(
            version,
            license_id,
            source_commit,
            skills_commit,
            skills_commit_date,
            skill_count,
            len(clean_records),
        )
        state = {
            "schemaVersion": 1,
            "upstreamOwner": UPSTREAM_OWNER,
            "upstreamRepository": UPSTREAM_REPO,
            "upstreamBranch": UPSTREAM_BRANCH,
            "upstreamSubdirectory": UPSTREAM_SUBDIRECTORY,
            "upstreamUrl": UPSTREAM_SKILLS_URL,
            "sourceCommit": source_commit,
            "skillsCommit": skills_commit,
            "skillsCommitDate": skills_commit_date,
            "openclawVersion": version,
            "license": license_id,
            "skillCount": skill_count,
            "fileCount": len(clean_records),
            "contentSha256": content_sha,
            "pathMapping": "skills/<path> -> <path>",
            "files": clean_records,
        }
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"Synced OpenClaw {version} skills at {skills_commit[:12]} "
            f"({skill_count} skills, {len(clean_records)} files)"
        )


if __name__ == "__main__":
    main()
