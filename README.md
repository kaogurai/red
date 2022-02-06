# kaogurai's fork of red

## notes
this fork is mainly for my use, and therefor i will not be providing any support for running this

## changes from core red

### new features
- commands are now processed on command edits
- a playmix command has been added to audio (from draper's alpha audio)
- sentry has been added to the bot (plus `[p]set sentry` to set the dsn)
- supports apple music in audio (needs [apple music ll plugin](https://github.com/Topis-Lavalink-Plugins/Topis-Source-Managers-Plugin))

### enhancements
- audio uses lavalink's /loadtracks instead of the youtube api
- cleanup now has a maximum of 10000 messages per command
- messages are automatically decancered in the filter cog
- some of the success messages have been changed in the mod cog
- dms are now sent by default for the mod cog
- dms are sent by default in the mutes cog but dms are no longer sent for actions made by other users/bots
- some aliases have been added to audio commands
- the message when commands error has been made prettier
- all modlog types are now on by default except filterhit
- a message will be displayed when trying to purge messages over 14 days old in the cleanup cog
- `[p]payday` is now in an embed
- `[p]leaderboard` has been renamed to `[p]economyleaderboard`
- `[p]serverinfo` has been made pretty
- `[p]names` and `[p]userinfo` now accepts users outside the guild

### removals
- `[p]invite` has been removed
- `[p]serverprefix` has been removed
- `[p]rename` has been removed
