from __future__ import annotations

from mewcode.commands.registry import Command, CommandContext, CommandType


async def handle_exit(ctx: CommandContext) -> None:
    ctx.ui.add_system_message("再见！")
    ctx.ui.shutdown()


EXIT_COMMAND = Command(
    name="exit",
    aliases=["quit", "q"],
    description="退出 XHCode",
    type=CommandType.LOCAL_UI,
    handler=handle_exit,
)
