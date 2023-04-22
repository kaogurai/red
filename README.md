# Red-DiscordBot fork for kaogurai

## Notes

Using this fork is not supported. As in the nature of open source, you are free to use it as long as you follow the license, but I bear no responsibility for any issues that may arise from using this fork.

## Changes

### Audio Cog

- Native spotify support has been removed
  - Removal of the `[p]genre` command
  - Removed most (if not all) references to spotify from the code
- Support for Spotify and Apple Music is provided via a lavalink plugin
- YouTube is no longer used, and has been replaced with Deezer
- Some aliases have been added
  
### Cleanup Cog

- Only 10,000 messages can be deleted at a time
- The base `[p]cleanup` command has been made into an alias for `[p]cleanup messages`, and some aliases have been added for the cleanup command itself
- A message will be displayed if the messages are older than 2 weeks and cannot be deleted

### Filter Cog

- Support for 'decancering' messages has been added
- Names are automatically filtered by default
- The filterban modlog type is registered by default
  
### Mod Cog

- The success messages for moderation commands have been changed to identify the user that was moderated
- DMs are sent by default when a user is kicked or banned
- The `[p]rename` command has been removed
- An alias (`[p]sm`) has been added for `[p]slowmode`
  
### Mutes Cog

- DMs are now sent by default
- DMs are no longer sent when an outside source removes the mute role
  
### Permissions API

- The `@commands.admin()` decorator has been made into an alias for `@commands.admin_or_permissions(manage_guild=True)`
- The `@commands.mod()` decorator has been made into an alias for `@commands.mod_or_permissions(manage_messages=True)`

### Modlog API

- The following modlog types are now registered by default:
  - voicemute
  - voiceunmute
  - channelmute
  - channelunmute
  - voicekick
  
### Core Bot

- Support for Sentry monitoring has been added
  - A `[p]`sentry command has been added to set the Sentry DSN
- A `[p]mydata selfblacklist` command has been added to allow users to blacklist themselves from the bot
- The `[p]invite` command has been removed
- The `[p]set serverprefix` command has been removed
- Commands are now processed on message edits
