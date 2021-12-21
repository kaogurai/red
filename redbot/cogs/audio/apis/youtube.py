import json
import contextlib
import logging
from pathlib import Path

from typing import TYPE_CHECKING, Mapping, Optional, Union

import aiohttp

from redbot.core import Config
from redbot.core.bot import Red
from redbot.core.commands import Cog
from redbot.core.i18n import Translator

from ..errors import YouTubeApiError

if TYPE_CHECKING:
    from .. import Audio

log = logging.getLogger("red.cogs.Audio.api.YouTube")
_ = Translator("Audio", Path(__file__))
SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"


class YouTubeWrapper:
    """Wrapper for the YouTube Data API."""

    def __init__(
        self, bot: Red, config: Config, session: aiohttp.ClientSession, cog: Union["Audio", Cog]
    ):
        self.bot = bot
        self.config = config
        self.session = session
        self.api_key: Optional[str] = None
        self._token: Mapping[str, str] = {}
        self.cog = cog

    async def update_token(self, new_token: Mapping[str, str]):
        self._token = new_token

    async def _get_api_key(
        self,
    ) -> str:
        """Get the stored youtube token."""
        if not self._token:
            self._token = await self.bot.get_shared_api_tokens("youtube")
        self.api_key = self._token.get("api_key", "")
        return self.api_key if self.api_key is not None else ""

    async def get_call(self, query: str) -> Optional[str]:
        """Make a Get call to youtube data api."""
        config = await self.config.all()
        pw = config.get("password")
        host = config.get("host")
        port = config.get("rest_port")

        params = {"identifier": "ytsearch:" + query}
        headers = {"Authorization": pw, "Accept": "application/json"}
        async with self.session.get(
            f"http://{host}:{port}/loadtracks",
            params=params,
            headers=headers,
        ) as request:
            if request.status == 200:
                response = await request.json()
                with contextlib.suppress(KeyError, IndexError):
                    return response["tracks"][0]["info"]["uri"]
