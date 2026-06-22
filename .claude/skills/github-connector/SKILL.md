---
name: github-connector
description: "Use ChatGPT's GitHub Connector to interact with a repository. Automatically detects repo, branch, and optional commit. Use when the user asks to review code, audit a PR, analyze project structure, or optimize code via ChatGPT's web interface with GitHub access. Triggers: 'github connector', 'gpt review', 'chatgpt review', 'gpt audit', '让gpt审核', '让gpt看看', 'gpt代码审查'."
---

# github-connector — ChatGPT GitHub Connector Bridge

Send tasks to ChatGPT via MCP, leveraging its GitHub Connector to access repositories.
Auto-detects repo name, branch, and optionally a specific commit.

## Instructions

When this skill is triggered, follow these steps IN ORDER:

### Step 1: Gather git context

Run these commands to detect the current project's git info:

```bash
git remote get-url origin 2>/dev/null
git branch --show-current
git log --oneline -1 2>/dev/null
```

Parse the remote URL to extract **owner/repo**:
- `https://github.com/owner/repo.git` → `owner/repo`
- `git@github.com:owner/repo.git` → `owner/repo`

### Step 2: Determine task parameters

From the user's request, identify:

| Parameter | Source | Example |
|-----------|--------|---------|
| **repo** | Auto-detected from git remote | `maoulee/llm_eduated` |
| **branch** | `git branch --show-current` | `feature/hybrid-solver` |
| **commit** | Only if user mentions a specific commit | `a87e12d` or omit |
| **task** | User's actual request | "review this code", "optimize the pipeline" |

### Step 3: Build and send the ChatGPT prompt

Use the `mcp__chatgpt-web__chatgpt` tool. Construct the prompt with this structure:

**If reviewing a specific commit:**

```
请使用 GitHub 连接器访问仓库 {owner}/{repo}，分支 {branch}。
审核 commit {commit_hash} 的变更内容，重点关注：
- 代码质量和可读性
- 潜在 bug 或逻辑错误
- 性能问题
- 安全隐患

{user's specific request if any}
```

**If general review / optimization (no specific commit):**

```
请使用 GitHub 连接器访问仓库 {owner}/{repo}，分支 {branch}。
{user's request}

注意：请先确认你能访问该仓库，然后基于最新代码进行分析。
```

**If the user's request already contains all needed context**, just prepend the connector instruction:

```
请使用 GitHub 连接器访问仓库 {owner}/{repo}，分支 {branch}。
{user's original request}
```

### Step 4: Handle the response

- Return the ChatGPT response to the user
- If ChatGPT mentions it cannot access the repo, tell the user they need to enable the GitHub Connector in the ChatGPT web UI first (open the conversation URL and click the GitHub connector)

## Important notes

- Always auto-detect repo and branch — never hardcode
- Only include commit reference when the user specifically asks about a commit or diff
- Use `model: "gpt-instant"` for quick tasks, `model: "gpt-thinking"` for complex analysis
- The ChatGPT conversation URL is returned in the MCP response — share it with the user so they can follow up in the web UI
- If the user provides a topic, pass it to the MCP call for conversation tracking
