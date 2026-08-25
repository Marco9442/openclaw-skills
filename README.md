# openclaw-skills

[![Sync OpenClaw skills](https://github.com/Marco9442/openclaw-skills/actions/workflows/sync-upstream.yml/badge.svg)](https://github.com/Marco9442/openclaw-skills/actions/workflows/sync-upstream.yml)

这是 OpenClaw 官方仓库 [`openclaw/openclaw` 的 `skills/` 目录](https://github.com/openclaw/openclaw/tree/main/skills)的**自动同步公开镜像**，按 CC Switch 可直接扫描的多 Skill GitHub 仓库格式发布。

上游 `skills/<skill-name>/...` 会被同步到本仓库 `<skill-name>/...`。每个技能目录保留其原始 `SKILL.md` 和配套文件，CC Switch 无需依赖额外清单即可递归识别。

## 当前镜像

- OpenClaw 版本：`2026.8.1`
- 上游分支：`main`
- 同步快照提交：[`147e9da5d8b5`](https://github.com/openclaw/openclaw/commit/147e9da5d8b5e02a29a5eb17931d2d07dc1b2c68)
- `skills/` 最近变更提交：[`8f0503657c0b`](https://github.com/openclaw/openclaw/commit/8f0503657c0b6aadc5f58585797bbf971f1934b2)
- `skills/` 最近变更时间：`2026-08-25T05:57:03Z`
- 可识别 Skills：`51`
- 同步文件：`77`
- 上游许可证：`MIT`
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

技能原始来源为 [`openclaw/openclaw/skills`](https://github.com/openclaw/openclaw/tree/main/skills)。本仓库保留 OpenClaw 的 [`LICENSE`](LICENSE) 和 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。所有上游内容的权利归其原作者和权利人所有。

本仓库不是独立开发分支。除 README、同步脚本、Workflow 和来源清单外，不对上游技能内容进行改写。
