"""Wires the exoclaw stack with GitHubChannel for GitHub Actions."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from exoclaw.agent.loop import AgentLoop
from exoclaw.bus.queue import MessageBus
from exoclaw_conversation.conversation import DefaultConversation
from exoclaw_provider_litellm.provider import LiteLLMProvider
from exoclaw_tools_workspace.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from exoclaw_tools_workspace.shell import ExecTool

from exoclaw_github.channel import GitHubChannel
from exoclaw_github.tools import (
    GitHubChecksTool,
    GitHubFileTool,
    GitHubIssueTool,
    GitHubLabelTool,
    GitHubPRDiffTool,
    GitHubReactionTool,
    GitHubReviewTool,
    GitHubSearchTool,
)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


_GITHUB_TOOLS: dict[str, Any] = {
    "github_review": GitHubReviewTool,
    "github_label": GitHubLabelTool,
    "github_pr_diff": GitHubPRDiffTool,
    "github_issue": GitHubIssueTool,
    "github_reaction": GitHubReactionTool,
    "github_file": GitHubFileTool,
    "github_checks": GitHubChecksTool,
    "github_search": GitHubSearchTool,
}


async def create(
    model: str | None = None,
    state_dir: Path | None = None,
    repo_dir: Path | None = None,
    trigger: str | None = ...,  # type: ignore[assignment]
    respond_to_issues_opened: bool = True,
    respond_to_prs_opened: bool = False,
    max_tokens: int = 8192,
    max_iterations: int = 40,
    tools: list[str] | None = None,
) -> tuple[AgentLoop, GitHubChannel, MessageBus]:
    """
    Create a fully wired exoclaw stack for GitHub Actions.

    Args:
        model: LLM model string (default: EXOCLAW_MODEL env var or claude-sonnet-4-5).
        state_dir: Where sessions and memory are persisted (default: ~/.nanobot/workspace).
            In a GitHub Actions workflow, check out the bot-state branch here before
            running and commit it back afterwards.
        repo_dir: Root of the checked-out repository for file/shell tools
            (default: GITHUB_WORKSPACE env var or current directory).
        trigger: Word that must appear in comments to trigger the bot.
            Defaults to EXOCLAW_TRIGGER env var, then "@exoclaw". Pass None to respond
            to all comments.
        respond_to_issues_opened: Whether to respond when an issue is opened.
        respond_to_prs_opened: Whether to respond when a PR is opened.
        max_tokens: Maximum tokens per LLM response.
        max_iterations: Maximum tool-call iterations per turn.
        tools: GitHub tool names to enable (e.g. ["github_pr_diff", "github_review"]).
            Defaults to EXOCLAW_TOOLS env var (comma-separated). Empty = no GitHub tools.
            Workspace tools (read/write/exec) are always enabled.
    """
    model = model or _env("EXOCLAW_MODEL", "claude-sonnet-4-5")

    state_dir = state_dir or Path(_env("EXOCLAW_STATE_DIR", "~/.nanobot/workspace")).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)

    repo_dir = repo_dir or Path(_env("GITHUB_WORKSPACE") or os.getcwd())

    # trigger: sentinel ... means "read from env"
    if trigger is ...:  # type: ignore[comparison-overlap]
        env_val = _env("EXOCLAW_TRIGGER", "@exoclaw")
        trigger = env_val if env_val else None

    provider = LiteLLMProvider(default_model=model)

    bus = MessageBus()

    conversation = DefaultConversation.create(
        workspace=state_dir,
        provider=provider,
        model=model,
    )

    # Resolve which GitHub tools to enable
    if tools is None:
        env_tools = _env("EXOCLAW_TOOLS")
        tools = [t.strip() for t in env_tools.split(",") if t.strip()] if env_tools else []

    enabled_tools: list[Any] = [
        ReadFileTool(workspace=repo_dir),
        WriteFileTool(workspace=repo_dir),
        EditFileTool(workspace=repo_dir),
        ListDirTool(workspace=repo_dir),
        ExecTool(working_dir=str(repo_dir)),
    ]
    for tool_name in tools:
        cls = _GITHUB_TOOLS.get(tool_name)
        if cls:
            enabled_tools.append(cls())
        else:
            import warnings
            warnings.warn(f"Unknown tool: {tool_name!r}. Available: {list(_GITHUB_TOOLS)}")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        conversation=conversation,
        model=model,
        max_iterations=max_iterations,
        max_tokens=max_tokens,
        tools=enabled_tools,
    )

    channel = GitHubChannel(
        trigger=trigger,
        respond_to_issues_opened=respond_to_issues_opened,
        respond_to_prs_opened=respond_to_prs_opened,
    )

    return agent_loop, channel, bus


async def run() -> None:
    """Create the stack and run one GitHub Actions turn."""
    agent_loop, channel, bus = await create()
    loop_task = asyncio.create_task(agent_loop.run())
    try:
        await channel.start(bus)
    finally:
        loop_task.cancel()
        await asyncio.gather(loop_task, return_exceptions=True)
