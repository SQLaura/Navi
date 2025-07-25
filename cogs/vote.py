# vote.py

from datetime import timedelta

import discord
from discord import utils
from discord.ext import bridge, commands

from cache import messages
from database import errors, reminders, users
from resources import emojis, exceptions, functions, logs, regex, settings


class VoteCog(commands.Cog):
    """Cog that contains the dungeon/miniboss detection commands"""
    def __init__(self, bot: bridge.AutoShardedBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_edit(self, message_before: discord.Message, message_after: discord.Message) -> None:
        """Runs when a message is edited in a channel."""
        if message_after.author.id not in [settings.EPIC_RPG_ID, settings.TESTY_ID]: return
        if message_before.pinned != message_after.pinned: return
        embed_data_before = await functions.parse_embed(message_before)
        embed_data_after = await functions.parse_embed(message_after)
        if (message_before.content == message_after.content and embed_data_before == embed_data_after
            and message_before.components == message_after.components): return
        row: discord.Component
        for row in message_after.components:
            if isinstance(row, discord.ActionRow):
                for component in row.children:
                    if isinstance(component, (discord.Button, discord.SelectMenu)):
                        if component.disabled:
                            return
        await self.on_message(message_after)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Runs when a message is sent in a channel."""
        if message.author.id not in [settings.EPIC_RPG_ID, settings.TESTY_ID]: return

        if message.embeds:
            if message.embeds[0].fields:
                field = message.embeds[0].fields[0]

                # Vote cooldown
                search_strings = [
                    'next vote rewards', #English
                    'recompensas del siguiente voto', #Spanish
                    'recompensas do próximo voto', #Portuguese
                ]
                if any(search_string in field.name.lower() for search_string in search_strings):
                    search_patterns = [
                        r'cooldown: \*\*(.+?)\*\*', #All languages
                    ]
                    user = await functions.get_interaction_user(message)
                    if user is None:
                        user_command_message = (
                            await messages.find_message(message.channel.id, regex.COMMAND_VOTE)
                        )
                        if user_command_message is None:
                            await functions.add_warning_reaction(message)
                            await errors.log_error('Couldn\'t find a user for the vote embed.', message)
                            return
                        user = user_command_message.author
                    try:
                        user_settings: users.User = await users.get_user(user.id)
                    except exceptions.FirstTimeUserError:
                        return
                    if not user_settings.bot_enabled or not user_settings.alert_vote.enabled: return
                    timestring_match = await functions.get_match_from_patterns(search_patterns, field.value.lower())
                    if not timestring_match:
                        try:
                            reminder: reminders.Reminder = await reminders.get_user_reminder(user.id, 'vote')
                        except exceptions.NoDataFoundError:
                            return
                        await reminder.delete()
                        if reminder.record_exists:
                            logs.logger.error(f'{utils.utcnow()}: Had an error deleting the horse reminder.')
                        else:
                            if user_settings.reactions_enabled: await message.add_reaction(emojis.NAVCHI)
                    else:
                        timestring = timestring_match.group(1)
                        user_command = await functions.get_slash_command(user_settings, 'vote')
                        time_left = await functions.calculate_time_left_from_timestring(message, timestring)
                        if time_left < timedelta(0): return
                        reminder_message = user_settings.alert_vote.message.replace('{command}', user_command)
                        reminder: reminders.Reminder = (
                            await reminders.insert_user_reminder(user.id, 'vote', time_left,
                                                                message.channel.id, reminder_message)
                        )
                        await functions.add_reminder_reaction(message, reminder, user_settings)


# Initialization
def setup(bot: bridge.AutoShardedBot):
    bot.add_cog(VoteCog(bot))