import datetime
from typing import Union, cast

import discord

from redbot.core import commands, i18n, checks
from redbot.core.utils.common_filters import (
    filter_invites,
    filter_various_mentions,
    escape_spoilers_and_mass_mentions,
)
from redbot.core.utils.mod import get_audit_reason
from .abc import MixinMeta
from .utils import is_allowed_by_hierarchy

_ = i18n.Translator("Mod", __file__)


class ModInfo(MixinMeta):
    """
    Commands regarding names, userinfo, etc.
    """

    async def get_names_and_nicks(self, user, ctx):
        names = await self.config.user(user).past_names()
        nicks = None
        if hasattr(user, "guild") and ctx.guild:
            nicks = await self.config.member(user).past_nicks()
        if names:
            names = [escape_spoilers_and_mass_mentions(name) for name in names if name]
        if nicks:
            nicks = [escape_spoilers_and_mass_mentions(nick) for nick in nicks if nick]
        return names, nicks

    def handle_custom(self, user):
        a = [c for c in user.activities if c.type == discord.ActivityType.custom]
        if not a:
            return None, discord.ActivityType.custom
        a = a[0]
        c_status = None
        if not a.name and not a.emoji:
            return None, discord.ActivityType.custom
        elif a.name and a.emoji:
            c_status = _("Custom: {emoji} {name}").format(emoji=a.emoji, name=a.name)
        elif a.emoji:
            c_status = _("Custom: {emoji}").format(emoji=a.emoji)
        elif a.name:
            c_status = _("Custom: {name}").format(name=a.name)
        return c_status, discord.ActivityType.custom

    def handle_playing(self, user):
        p_acts = [c for c in user.activities if c.type == discord.ActivityType.playing]
        if not p_acts:
            return None, discord.ActivityType.playing
        p_act = p_acts[0]
        act = _("Playing: {name}").format(name=p_act.name)
        return act, discord.ActivityType.playing

    def handle_streaming(self, user):
        s_acts = [c for c in user.activities if c.type == discord.ActivityType.streaming]
        if not s_acts:
            return None, discord.ActivityType.streaming
        s_act = s_acts[0]
        if isinstance(s_act, discord.Streaming):
            act = _("Streaming: [{name}{sep}{game}]({url})").format(
                name=discord.utils.escape_markdown(s_act.name),
                sep=" | " if s_act.game else "",
                game=discord.utils.escape_markdown(s_act.game) if s_act.game else "",
                url=s_act.url,
            )
        else:
            act = _("Streaming: {name}").format(name=s_act.name)
        return act, discord.ActivityType.streaming

    def handle_listening(self, user):
        l_acts = [c for c in user.activities if c.type == discord.ActivityType.listening]
        if not l_acts:
            return None, discord.ActivityType.listening
        l_act = l_acts[0]
        if isinstance(l_act, discord.Spotify):
            act = _("Listening: [{title}{sep}{artist}]({url})").format(
                title=discord.utils.escape_markdown(l_act.title),
                sep=" | " if l_act.artist else "",
                artist=discord.utils.escape_markdown(l_act.artist) if l_act.artist else "",
                url=f"https://open.spotify.com/track/{l_act.track_id}",
            )
        else:
            act = _("Listening: {title}").format(title=l_act.name)
        return act, discord.ActivityType.listening

    def handle_watching(self, user):
        w_acts = [c for c in user.activities if c.type == discord.ActivityType.watching]
        if not w_acts:
            return None, discord.ActivityType.watching
        w_act = w_acts[0]
        act = _("Watching: {name}").format(name=w_act.name)
        return act, discord.ActivityType.watching

    def handle_competing(self, user):
        w_acts = [c for c in user.activities if c.type == discord.ActivityType.competing]
        if not w_acts:
            return None, discord.ActivityType.competing
        w_act = w_acts[0]
        act = _("Competing in: {competing}").format(competing=w_act.name)
        return act, discord.ActivityType.competing

    def get_status_string(self, user):
        string = ""
        for a in [
            self.handle_custom(user),
            self.handle_playing(user),
            self.handle_listening(user),
            self.handle_streaming(user),
            self.handle_watching(user),
            self.handle_competing(user),
        ]:
            status_string, status_type = a
            if status_string is None:
                continue
            string += f"{status_string}\n"
        return string

    @commands.command(aliases=["ui", "uinfo", "whois"])
    @commands.bot_has_permissions(embed_links=True, use_external_emojis=True)
    async def userinfo(self, ctx, *, member: Union[discord.Member, discord.User] = None):
        """
        Show information about a user.

        This includes fields for status, discord join date, server
        join date, voice state and previous names/nicknames.

        If the user is not in the server, it will not have all the normal information.
        """
        status_emojis = {
            "mobile": "<:mobile:749067110931759185>",
            "streaming": "<:streaming:749221434039205909>",
            "online": "<:online:749221433552404581>",
            "offline": "<:offline:749221433049088082>",
            "dnd": "<:do_not_disturb:749221432772395140>",
            "idle": "<:idle:749221433095356417>",
        }
        badge_emojis = {
            "early_supporter": "<:early_supporter:706198530837970998>",
            "hypesquad_balance": "<:hypesquad_balance:706198531538550886>",
            "hypesquad_bravery": "<:hypesquad_bravery:706198532998299779>",
            "hypesquad_brilliance": "<:hypesquad_briliance:706198535846101092>",
            "hypesquad": "<:hypesquad_events:706198537049866261>",
            "verified_bot_developer": "<:early_verified_bot_developer:706198727953612901>",
            "discord_certified_moderator": "<:discord_certified_moderator:848556248357273620>",
            "staff": "<:discord_employee:848556248832016384>",
            "partner": "<:discord_partner:848556249192202247>",
            "verified_bot": "<:verified_bot:848557763328344064>",  # not used, just easier this way
            "verified_bot_part_1": "<:verified_bot1:848561838974697532>",
            "verified_bot_part_2": "<:verified_bot2:848561839260434482>",
            "bug_hunter": "<:bug_hunter_lvl1:848556247632052225>",
            "bug_hunter_level_2": "<:bug_hunter_lvl2:706199712402898985>",
        }
        guild = ctx.guild

        if not member:
            member = ctx.author

        names, nicks = await self.get_names_and_nicks(member, ctx)
        user_created = int(member.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())

        created_on = "<t:{0}>\n(<t:{0}:R>)".format(user_created)

        # stuff that needs a guild object here
        joined_at = None
        since_joined = None
        user_joined = None
        staus_emoji = None
        activity = None
        status_string = None
        roles = None
        joined_on = None
        name = str(member)
        colour = await ctx.embed_color()
        member_number = None
        voice_state = None
        shared_guilds = None
        if hasattr(member, "guild") and ctx.guild:
            if member.is_on_mobile():
                staus_emoji = status_emojis["mobile"]
            elif any(a.type is discord.ActivityType.streaming for a in member.activities):
                staus_emoji = status_emojis["streaming"]
            elif member.status.name == "online":
                staus_emoji = status_emojis["online"]
            elif member.status.name == "offline":
                staus_emoji = status_emojis["offline"]
            elif member.status.name == "dnd":
                staus_emoji = status_emojis["dnd"]
            elif member.status.name == "idle":
                staus_emoji = status_emojis["idle"]

            activity = _("Chilling in {} status").format(member.status)
            status_string = self.get_status_string(member)
            roles = member.roles[-1:0:-1]
            joined_on = _("{}\n({} days ago)").format(user_joined, since_joined)
            name = " ~ ".join((name, member.nick)) if member.nick else name
            colour = member.colour
            if hasattr(member, "guild") and ctx.guild:
                member_number = (
                    sorted(
                        guild.members, key=lambda m: m.joined_at or ctx.message.created_at
                    ).index(member)
                    + 1
                )
            voice_state = member.voice
            if member == ctx.guild.me:
                shared_guilds = len(ctx.bot.guilds)
            else:
                shared_guilds = len(member.mutual_guilds)
            joined_at = member.joined_at.replace(tzinfo=datetime.timezone.utc)

            if joined_at is not None:
                joined_on = "<t:{0}>\n(<t:{0}:R>)".format(int(joined_at.timestamp()))
            else:
                joined_on = _("Unknown")

        if roles:

            role_str = ", ".join([x.mention for x in roles])
            # 400 BAD REQUEST (error code: 50035): Invalid Form Body
            # In embed.fields.2.value: Must be 1024 or fewer in length.
            if len(role_str) > 1024:
                # Alternative string building time.
                # This is not the most optimal, but if you're hitting this, you are losing more time
                # to every single check running on users than the occasional user info invoke
                # We don't start by building this way, since the number of times we hit this should be
                # infinitesimally small compared to when we don't across all uses of Red.
                continuation_string = _(
                    "and {numeric_number} more roles not displayed due to embed limits."
                )
                available_length = 1024 - len(continuation_string)  # do not attempt to tweak, i18n

                role_chunks = []
                remaining_roles = 0

                for r in roles:
                    chunk = f"{r.mention}, "
                    chunk_size = len(chunk)

                    if chunk_size < available_length:
                        available_length -= chunk_size
                        role_chunks.append(chunk)
                    else:
                        remaining_roles += 1

                role_chunks.append(continuation_string.format(numeric_number=remaining_roles))

                role_str = "".join(role_chunks)

        else:
            role_str = None

        badges = member.public_flags.all()
        if badges:

            def format_name(name):
                return name.replace("_", " ").title()

            def get_emoji(name):
                if name == "verified_bot":
                    p1 = badge_emojis["verified_bot_part_1"]
                    p2 = badge_emojis["verified_bot_part_2"]
                    return p1 + p2
                return badge_emojis[name]

            badge_str = "\n".join(
                [
                    f"{format_name(badge.name)} {get_emoji(badge.name)}"
                    if badge.name in badge_emojis
                    else f"{badge.name} {badge.value})"
                    for badge in badges
                ]
            )

        description = status_string or activity or ""
        if shared_guilds:
            description += _("\nShared servers: {num_shared}").format(num_shared=shared_guilds)
        data = discord.Embed(description=description, colour=colour)

        data.add_field(name=_("Joined Discord on"), value=created_on)
        if joined_on:
            data.add_field(name=_("Joined this server on"), value=joined_on)

        if badges:
            data.add_field(name="Badges", value=badge_str, inline=False)

        if role_str is not None:
            data.add_field(
                name=_("Roles") if len(roles) > 1 else _("Role"), value=role_str, inline=False
            )
        if names:
            # May need sanitizing later, but mentions do not ping in embeds currently
            val = filter_invites(", ".join(names))
            data.add_field(
                name=_("Previous Names") if len(names) > 1 else _("Previous Name"),
                value=val,
                inline=False,
            )
        if nicks:
            # May need sanitizing later, but mentions do not ping in embeds currently
            val = filter_invites(", ".join(nicks))
            data.add_field(
                name=_("Previous Nicknames") if len(nicks) > 1 else _("Previous Nickname"),
                value=val,
                inline=False,
            )
        if voice_state and voice_state.channel:
            data.add_field(
                name=_("Current voice channel"),
                value="{0.mention} ID: {0.id}".format(voice_state.channel),
                inline=False,
            )

        if member_number:
            data.set_footer(text=_("Member #{} | User ID: {}").format(member_number, member.id))
        else:
            data.set_footer(text=_("User ID: {}").format(member.id))

        name = filter_invites(name)

        avatar = member.avatar_url_as(static_format="png")

        if staus_emoji:
            data.title = f"{staus_emoji} {name}"
        else:
            data.title = name

        data.set_thumbnail(url=avatar)

        await ctx.send(embed=data)

    @commands.command()
    async def names(self, ctx: commands.Context, *, member: Union[discord.Member, discord.User] = None):
        """Show previous names and nicknames of a member."""
        if not member:
            member = ctx.author

        names, nicks = await self.get_names_and_nicks(member, ctx)
        msg = ""
        if names:
            msg += _("**Past 20 names**:")
            msg += "\n"
            msg += ", ".join(names)
        if nicks:
            if msg:
                msg += "\n\n"
            msg += _("**Past 20 nicknames**:")
            msg += "\n"
            msg += ", ".join(nicks)
        if msg:
            msg = filter_various_mentions(msg)
            await ctx.send(msg)
        else:
            await ctx.send(_("That member doesn't have any recorded name or nickname change."))
