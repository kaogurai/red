import logging

import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

log = logging.getLogger("red.sentry")


async def _init(bot):
    url = await bot._config.sentry_url()
    if not url:
        return
    sentry_sdk.init(
        url,
        traces_sample_rate=1.0,
        shutdown_timeout=0.1,
        integrations=[
            AioHttpIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )

    async def command_start(ctx):
        if ctx.command is None:
            return
        if ctx.guild:
            m = f'{ctx.author} ({ctx.author.id}) ran command "{ctx.command.qualified_name}" in guild {ctx.guild.name} ({ctx.guild.id})'
        else:
            m = f'{ctx.author} ({ctx.author.id}) ran command "{ctx.command.qualified_name}" in DMs'
        log.info(m)

    bot.add_listener(command_start, "on_command")
