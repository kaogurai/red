import asyncio
import contextlib
import datetime
import json
import random
import time

from collections import namedtuple
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, MutableMapping, Optional, Tuple, Union, cast

import aiohttp
import discord
import lavalink
from red_commons.logging import getLogger

from lavalink.rest_api import LoadResult, LoadType
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.commands import Cog, Context
from redbot.core.i18n import Translator
from redbot.core.utils import AsyncIter
from redbot.core.utils.dbtools import APSWConnectionWrapper

from ..audio_dataclasses import Query
from ..errors import DatabaseError, TrackEnqueueError
from ..utils import CacheLevel, Notifier
from .api_utils import LavalinkCacheFetchForGlobalResult
from .global_db import GlobalCacheWrapper
from .local_db import LocalCacheWrapper
from .persist_queue_wrapper import QueueInterface
from .playlist_interface import get_playlist
from .playlist_wrapper import PlaylistWrapper

if TYPE_CHECKING:
    from .. import Audio

_ = Translator("Audio", Path(__file__))
log = getLogger("red.cogs.Audio.api.AudioAPIInterface")
_TOP_100_US = "https://www.youtube.com/playlist?list=PL4fGSI1pDJn5rWitrRWFKdm-ulaFiIyoK"
# TODO: Get random from global Cache


class AudioAPIInterface:
    """Handles music queries.

    Always tries the Local cache first, then Global cache before making API calls.
    """

    def __init__(
        self,
        bot: Red,
        config: Config,
        session: aiohttp.ClientSession,
        conn: APSWConnectionWrapper,
        cog: Union["Audio", Cog],
    ):
        self.bot = bot
        self.config = config
        self.conn = conn
        self.cog = cog
        self.local_cache_api = LocalCacheWrapper(self.bot, self.config, self.conn, self.cog)
        self.global_cache_api = GlobalCacheWrapper(self.bot, self.config, session, self.cog)
        self.persistent_queue_api = QueueInterface(self.bot, self.config, self.conn, self.cog)
        self._session: aiohttp.ClientSession = session
        self._tasks: MutableMapping = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialises the Local Cache connection."""
        await self.local_cache_api.lavalink.init()
        await self.persistent_queue_api.init()

    def close(self) -> None:
        """Closes the Local Cache connection."""
        self.local_cache_api.lavalink.close()

    async def get_random_track_from_db(self, tries=0) -> Optional[MutableMapping]:
        """Get a random track from the local database and return it."""
        track: Optional[MutableMapping] = {}
        try:
            query_data = {}
            date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
            date_timestamp = int(date.timestamp())
            query_data["day"] = date_timestamp
            max_age = await self.config.cache_age()
            maxage = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
                days=max_age
            )
            maxage_int = int(time.mktime(maxage.timetuple()))
            query_data["maxage"] = maxage_int
            track = await self.local_cache_api.lavalink.fetch_random(query_data)
            if track is not None:
                if track.get("loadType") == "V2_COMPACT":
                    track["loadType"] = "V2_COMPAT"
                results = LoadResult(track)
                track = random.choice(list(results.tracks))
        except Exception as exc:
            log.trace("Failed to fetch a random track from database", exc_info=exc)
            track = {}

        if not track:
            return None

        return track

    async def route_tasks(
        self,
        action_type: str = None,
        data: Union[List[MutableMapping], MutableMapping] = None,
    ) -> None:
        """Separate the tasks and run them in the appropriate functions."""

        if not data:
            return
        if action_type == "insert" and isinstance(data, list):
            for table, d in data:
                if table == "lavalink":
                    await self.local_cache_api.lavalink.insert(d)
        elif action_type == "update" and isinstance(data, dict):
            for table, d in data:
                if table == "lavalink":
                    await self.local_cache_api.lavalink.update(data)
        elif action_type == "global" and isinstance(data, list):
            await asyncio.gather(*[self.global_cache_api.update_global(**d) for d in data])

    async def run_tasks(self, ctx: Optional[commands.Context] = None, message_id=None) -> None:
        """Run tasks for a specific context."""
        if message_id is not None:
            lock_id = message_id
        elif ctx is not None:
            lock_id = ctx.message.id
        else:
            return
        lock_author = ctx.author if ctx else None
        async with self._lock:
            if lock_id in self._tasks:
                log.trace("Running database writes for %s (%s)", lock_id, lock_author)
                try:
                    tasks = self._tasks[lock_id]
                    tasks = [self.route_tasks(a, tasks[a]) for a in tasks]
                    await asyncio.gather(*tasks, return_exceptions=False)
                    del self._tasks[lock_id]
                except Exception as exc:
                    log.verbose(
                        "Failed database writes for %s (%s)", lock_id, lock_author, exc_info=exc
                    )
                else:
                    log.trace("Completed database writes for %s (%s)", lock_id, lock_author)

    async def run_all_pending_tasks(self) -> None:
        """Run all pending tasks left in the cache, called on cog_unload."""
        async with self._lock:
            log.trace("Running pending writes to database")
            try:
                tasks: MutableMapping = {"update": [], "insert": [], "global": []}
                async for k, task in AsyncIter(self._tasks.items()):
                    async for t, args in AsyncIter(task.items()):
                        tasks[t].append(args)
                self._tasks = {}
                coro_tasks = [self.route_tasks(a, tasks[a]) for a in tasks]

                await asyncio.gather(*coro_tasks, return_exceptions=False)

            except Exception as exc:
                log.verbose("Failed database writes", exc_info=exc)
            else:
                log.trace("Completed pending writes to database have finished")

    def append_task(self, ctx: commands.Context, event: str, task: Tuple, _id: int = None) -> None:
        """Add a task to the cache to be run later."""
        lock_id = _id or ctx.message.id
        if lock_id not in self._tasks:
            self._tasks[lock_id] = {"update": [], "insert": [], "global": []}
        self._tasks[lock_id][event].append(task)

    async def fetch_track(
        self,
        ctx: commands.Context,
        player: lavalink.Player,
        query: Query,
        forced: bool = False,
        lazy: bool = False,
        should_query_global: bool = True,
    ) -> Tuple[LoadResult, bool]:
        """A replacement for :code:`lavalink.Player.load_tracks`. This will try to get a valid
        cached entry first if not found or if in valid it will then call the lavalink API.

        Parameters
        ----------
        ctx: commands.Context
            The context this method is being called under.
        player : lavalink.Player
            The player who's requesting the query.
        query: audio_dataclasses.Query
            The Query object for the query in question.
        forced:bool
            Whether or not to skip cache and call API first.
        lazy:bool
            If set to True, it will not call the api if a track is not found.
        should_query_global:bool
            If the method should query the global database.

        Returns
        -------
        Tuple[lavalink.LoadResult, bool]
            Tuple with the Load result and whether or not the API was called.
        """
        current_cache_level = CacheLevel(await self.config.cache_level())
        cache_enabled = CacheLevel.set_lavalink().is_subset(current_cache_level)
        val = None
        query = Query.process_input(query, self.cog.local_folder_current_path)
        query_string = str(query)
        globaldb_toggle = self.cog.global_api_user.get("can_read")
        valid_global_entry = False
        results = None
        called_api = False
        prefer_lyrics = await self.cog.get_lyrics_status(ctx)
        if prefer_lyrics and query.is_youtube and query.is_search:
            query_string = f"{query} - lyrics"
        if cache_enabled and not forced and not query.is_local:
            try:
                (val, last_updated) = await self.local_cache_api.lavalink.fetch_one(
                    {"query": query_string}
                )
            except Exception as exc:
                log.verbose("Failed to fetch %r from Lavalink table", query_string, exc_info=exc)

            if val and isinstance(val, dict):
                log.trace("Updating Local Database with %r", query_string)
                task = ("update", ("lavalink", {"query": query_string}))
                self.append_task(ctx, *task)
            else:
                val = None

            if val and not forced and isinstance(val, dict):
                valid_global_entry = False
                called_api = False
            else:
                val = None
        if (
            globaldb_toggle
            and not val
            and should_query_global
            and not forced
            and not query.is_local
        ):
            valid_global_entry = False
            with contextlib.suppress(Exception):
                global_entry = await self.global_cache_api.get_call(query=query)
                if global_entry.get("loadType") == "V2_COMPACT":
                    global_entry["loadType"] = "V2_COMPAT"
                results = LoadResult(global_entry)
                if results.load_type in [
                    LoadType.PLAYLIST_LOADED,
                    LoadType.TRACK_LOADED,
                    LoadType.SEARCH_RESULT,
                    LoadType.V2_COMPAT,
                ]:
                    valid_global_entry = True
                if valid_global_entry:
                    log.trace("Querying Global DB api for %r", query)
                    results, called_api = results, False
        if valid_global_entry:
            pass
        elif lazy is True:
            called_api = False
        elif val and not forced and isinstance(val, dict):
            data = val
            data["query"] = query_string
            if data.get("loadType") == "V2_COMPACT":
                data["loadType"] = "V2_COMPAT"
            results = LoadResult(data)
            called_api = False
            if results.has_error:
                # If cached value has an invalid entry make a new call so that it gets updated
                results, called_api = await self.fetch_track(ctx, player, query, forced=True)
            valid_global_entry = False
        else:
            log.trace("Querying Lavalink api for %r", query_string)
            called_api = True
            try:
                results = await player.load_tracks(query_string)
            except KeyError:
                results = None
            except RuntimeError:
                raise TrackEnqueueError
        if results is None:
            results = LoadResult({"loadType": "LOAD_FAILED", "playlistInfo": {}, "tracks": []})
            valid_global_entry = False
        update_global = (
            globaldb_toggle and not valid_global_entry and self.global_cache_api.has_api_key
        )
        with contextlib.suppress(Exception):
            if (
                update_global
                and not query.is_local
                and not results.has_error
                and len(results.tracks) >= 1
            ):
                global_task = ("global", dict(llresponse=results, query=query))
                self.append_task(ctx, *global_task)
        if (
            cache_enabled
            and results.load_type
            and not results.has_error
            and not query.is_local
            and results.tracks
        ):
            try:
                time_now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
                data = json.dumps(results._raw)
                if all(k in data for k in ["loadType", "playlistInfo", "isSeekable", "isStream"]):
                    task = (
                        "insert",
                        (
                            "lavalink",
                            [
                                {
                                    "query": query_string,
                                    "data": data,
                                    "last_updated": time_now,
                                    "last_fetched": time_now,
                                }
                            ],
                        ),
                    )
                    self.append_task(ctx, *task)
            except Exception as exc:
                log.verbose(
                    "Failed to enqueue write task for %r to Lavalink table",
                    query_string,
                    exc_info=exc,
                )
        return results, called_api

    async def autoplay(self, player: lavalink.Player, playlist_api: PlaylistWrapper):
        """Enqueue a random track."""
        autoplaylist = await self.config.guild(player.guild).autoplaylist()
        current_cache_level = CacheLevel(await self.config.cache_level())
        cache_enabled = CacheLevel.set_lavalink().is_subset(current_cache_level)
        notify_channel_id = player.fetch("notify_channel")
        playlist = None
        tracks = None
        if autoplaylist["enabled"]:
            try:
                playlist = await get_playlist(
                    autoplaylist["id"],
                    autoplaylist["scope"],
                    self.bot,
                    playlist_api,
                    player.guild,
                    player.guild.me,
                )
                tracks = playlist.tracks_obj
            except Exception as exc:
                log.verbose("Failed to fetch playlist for autoplay", exc_info=exc)

        if not tracks or not getattr(playlist, "tracks", None):
            if cache_enabled:
                track = await self.get_random_track_from_db()
                tracks = [] if not track else [track]
            if not tracks:
                ctx = namedtuple("Context", "message guild cog")
                (results, called_api) = await self.fetch_track(
                    cast(commands.Context, ctx(player.guild, player.guild, self.cog)),
                    player,
                    Query.process_input(_TOP_100_US, self.cog.local_folder_current_path),
                )
                tracks = list(results.tracks)
        if tracks:
            multiple = len(tracks) > 1
            valid = not multiple
            tries = len(tracks)
            track = tracks[0]
            while valid is False and multiple:
                tries -= 1
                if tries <= 0:
                    raise DatabaseError("No valid entry found")
                track = random.choice(tracks)
                query = Query.process_input(track, self.cog.local_folder_current_path)
                await asyncio.sleep(0.001)
                if (not query.valid) or (
                    query.is_local
                    and query.local_track_path is not None
                    and not query.local_track_path.exists()
                ):
                    continue
                notify_channel = player.guild.get_channel_or_thread(notify_channel_id)
                if not await self.cog.is_query_allowed(
                    self.config,
                    notify_channel,
                    f"{track.title} {track.author} {track.uri} {query}",
                    query_obj=query,
                ):
                    log.debug(
                        "Query is not allowed in %r (%s)", player.guild.name, player.guild.id
                    )
                    continue
                valid = True
            track.extras.update(
                {
                    "autoplay": True,
                    "enqueue_time": int(time.time()),
                    "vc": player.channel.id,
                    "requester": player.guild.me.id,
                }
            )
            player.add(player.guild.me, track)
            self.bot.dispatch(
                "red_audio_track_auto_play",
                player.guild,
                track,
                player.guild.me,
                player,
            )
            if notify_channel_id:
                await self.config.guild_from_id(
                    guild_id=player.guild.id
                ).currently_auto_playing_in.set([notify_channel_id, player.channel.id])
            else:
                await self.config.guild_from_id(
                    guild_id=player.guild.id
                ).currently_auto_playing_in.set([])
            if not player.current:
                await player.play()

    async def fetch_all_contribute(self) -> List[LavalinkCacheFetchForGlobalResult]:
        return await self.local_cache_api.lavalink.fetch_all_for_global()
