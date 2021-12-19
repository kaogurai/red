# kaogurai's fork of red

## notes
- i do not recommend using this fork
- it is designed strictly for my use and breaking changes can occur whenever
- no support will be provided if you do choose to use it

## changes from core red
- audio uses lavalink's /loadtracks instead of the youtube api
- some aliases have been added to audio commands
- a playmix command has been added to audio (from draper's alpha audio)
- cleanup now has a maximum of 10000 messages per command
- `[p]payday` is now in an embed
- `[p]leaderboard` has been renamed to `[p]economyleaderboard`
- messages are automatically decancered in the filter cog
- `[p]serverinfo` has been made pretty
- some of the success messages have been changed in the mod cog
- dms are now sent by default for the mod cog
- `[p]rename` has been removed
- `[p]names` and `[p]userinfo` now accepts users outside the guild
- dms are sent by default in the mutes cog but dms are no longer sent for actions made by other users
- sentry has been added to the bot (plus `[p]set sentry` to set the dsn)
- `[p]invite` has been removed
- `[p]serverprefix` has been removed
- commands are now processed on command edits
- the message when commands error has been made prettier
- all modlog types are now on by default except filterhit
- a message will be displayed when trying to purge messages over 14 days old in the cleanup cog
- the `[p]ping` command has been removed
- the `[p]info` command has been removed
