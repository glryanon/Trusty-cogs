import discord
from .errors import NotAValidTeamError, VotingHasEndedError, UserHasVotedError
from datetime import datetime, timedelta
from .constants import TEAMS
from .helper import hockey_config
from redbot.core.i18n import Translator
from redbot.core import Config
import asyncio
import logging


_ = Translator("Hockey", __file__)
log = logging.getLogger("red.trusty-cogs.Hockey")


class Pickems:
    """
        Pickems object for handling votes on games for the day
    """

    def __init__(
        self,
        message: list,
        channel: list,
        game_start: str,
        home_team: str,
        away_team: str,
        votes: dict,
        name: str,
        winner: str = None,
    ):
        super().__init__()
        self.message = message
        self.channel = channel
        self.game_start = datetime.strptime(game_start, "%Y-%m-%dT%H:%M:%SZ")
        self.home_team = home_team
        self.away_team = away_team
        self.votes = votes
        self.home_emoji = (
            TEAMS[home_team]["emoji"] if home_team in TEAMS else "nhl:496510372828807178"
        )
        self.away_emoji = (
            TEAMS[away_team]["emoji"] if away_team in TEAMS else "nhl:496510372828807178"
        )
        self.winner = winner
        self.name = name

    def add_vote(self, user_id, team):
        time_now = datetime.utcnow()

        team_choice = None
        if str(team.id) in self.home_emoji:
            team_choice = self.home_team
        if str(team.id) in self.away_emoji:
            team_choice = self.away_team
        if team_choice is None:
            raise NotAValidTeamError()
        if str(user_id) in self.votes:
            choice = self.votes[str(user_id)]
            if time_now > self.game_start:
                if choice == self.home_team:
                    emoji = self.home_emoji
                if choice == self.away_team:
                    emoji = self.away_emoji
                raise VotingHasEndedError(_("You have voted for ") + f"<:{emoji}>")
            else:
                if choice != team_choice:
                    self.votes[str(user_id)] = team_choice
                    raise UserHasVotedError("{} {}".format(team, team_choice))
        if time_now > self.game_start:
            raise VotingHasEndedError(_("You did not vote on this game!"))
        if str(user_id) not in self.votes:
            self.votes[str(user_id)] = team_choice

    @staticmethod
    def pickems_name(game):
        return f"{game.away_abr}@{game.home_abr}-{game.game_start.month}-{game.game_start.day}"

    async def set_pickem_winner(self, game):
        """
            Sets the pickem object winner from game object
        """
        if game.home_score > game.away_score:
            self.winner = self.home_team
        if game.away_score > game.home_score:
            self.winner = self.away_team

    @staticmethod
    async def find_pickems_object(bot, game):
        """
            Returns a list of all pickems on the bot for that game
        """
        # config = hockey_config()
        return_pickems = []
        new_name = f"{game.away_abr}@{game.home_abr}-{game.game_start.month}-{game.game_start.day}"
        for guild_id, pickems in bot.get_cog("Hockey").all_pickems.items():
            guild = bot.get_guild(int(guild_id))
            if guild is None:
                # await config._clear_scope(Config.GUILD, str(guild_id))
                continue
            # pickems = await config.guild(guild).pickems()
            if pickems is None:
                pickems = []
            if new_name in pickems:
                return_pickems.append(pickems[new_name])

        return return_pickems

    @staticmethod
    async def set_guild_pickem_winner(bot, game):
        for guild_id, pickems in bot.get_cog("Hockey").all_pickems.items():
            guild = bot.get_guild(int(guild_id))
            if guild is None:
                # await config._clear_scope(Config.GUILD, str(guild_id))
                continue
            # pickems = await config.guild(guild).pickems()
            if pickems is None:
                pickems = {}
            pickem_name = Pickems.pickems_name(game)
            if pickem_name in pickems:
                pickems[pickem_name].set_pickem_winner(game)

    @staticmethod
    async def create_pickem_object(bot, guild, message, channel, game):
        """
            Checks to see if a pickem object is already created for the game
            if not it creates one or adds the message, channel to the current ones
        """
        # config = hockey_config()
        pickems = bot.get_cog("Hockey").all_pickems.get(str(guild.id), None)
        new_name = Pickems.pickems_name(game)
        if type(pickems) is list:
            pickems = {}
        if pickems is None:
            bot.get_cog("Hockey").all_pickems[str((guild.id))] = {}
            pickems = {}
        old_pickem = None
        old_name = None
        for name, p in pickems.items():
            if p.home_team == game.home_team and p.away_team == game.away_team:
                if p.game_start == game.game_start:
                    log.debug(_("Pickem already exists, adding channel"))
                    old_pickem = p
                    old_name = name
            # if p["home_team"] == game.home_team and p["away_team"] == game.away_team:
                # if p["game_start"] == game.game_start.strftime("%Y-%m-%dT%H:%M:%SZ"):
                    # Only use the old one if the date is the same and the same teams are playing
                    # log.debug(_("Pickem already exists, adding channel"))
                    # old_pickem = p

        if old_pickem is None:
            pickems[new_name] = Pickems.from_json({
                    "message": [message.id],
                    "channel": [channel.id],
                    "game_start": game.game_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "home_team": game.home_team,
                    "away_team": game.away_team,
                    "votes": {},
                    "name": new_name,
                    "winner": None,
                })

            bot.get_cog("Hockey").all_pickems[str(guild.id)] = pickems
            log.debug("creating new pickems")
            # await config.guild(guild).pickems.set(pickems)
            return True
        else:
            del pickems[old_name]
            # old_pickem["message"].append(message.id)
            # old_pickem["channel"].append(channel.id)
            old_pickem.message.append(message.id)
            old_pickem.channel.append(message.id)
            pickems[old_name] = old_pickem
            bot.get_cog("Hockey").all_pickems[str(guild.id)] = pickems
            # await config.guild(guild).pickems.set(pickems)
            log.debug("using old pickems")
            return False

    @staticmethod
    async def reset_weekly(bot):
        # Reset the weekly leaderboard for all servers
        config = hockey_config()
        pickems_channels_to_delete = []
        for guild_id in await config.all_guilds():
            guild = bot.get_guild(id=guild_id)
            if guild is None:
                continue
            leaderboard = await config.guild(guild).leaderboard()
            try:
                current_guild_pickem_channels = await config.guild(guild).pickems_channels()
                if current_guild_pickem_channels:
                    pickems_channels_to_delete += current_guild_pickem_channels
            except Exception:
                log.error(_("Error adding channels to delete"), exc_info=True)
            if leaderboard is None:
                leaderboard = {}
            for user in leaderboard:
                leaderboard[str(user)]["weekly"] = 0
            await config.guild(guild).leaderboard.set(leaderboard)
        try:
            await Pickems.delete_pickems_channels(bot, pickems_channels_to_delete)
        except Exception:
            log.error(_("Error deleting pickems Channels"), exc_info=True)

    @staticmethod
    async def create_pickems_channel(bot, name, guild):
        msg = _(
            "**Welcome to our daily Pick'ems challenge!  Below you will see today's games!"
            "  Vote for who you think will win!  You get one point for each correct prediction."
            "  We will be tracking points over the course "
            "of the season and will be rewarding weekly,"
            " worst and full-season winners!**\n\n"
            "- Click the reaction for the team you think will win the day's match-up.\n"
            "- Anyone who votes for both teams will have their "
            "vote removed and will receive no points!\n\n\n\n"
        )
        config = hockey_config()
        category = bot.get_channel(await config.guild(guild).pickems_category())
        if not category:
            return
        try:
            new_chn = await guild.create_text_channel(name, category=category)
        except discord.errors.Forbidden:
            await config.guild(guild).pickems_category.set(None)
            return None
        await new_chn.send(msg)
        return new_chn

    @staticmethod
    async def create_pickems_game_msg(bot, channel, game):
        new_msg = await channel.send(
            "__**{} {}**__ @ __**{} {}**__".format(
                game.away_emoji, game.away_team, game.home_emoji, game.home_team
            )
        )
        # Create new pickems object for the game
        await Pickems.create_pickem_object(bot, channel.guild, new_msg, channel, game)
        if channel.permissions_for(channel.guild.me).add_reactions:
            try:
                await new_msg.add_reaction(game.away_emoji[2:-1])
                await new_msg.add_reaction(game.home_emoji[2:-1])
            except Exception:
                log.debug("Error adding reactions")

    @staticmethod
    async def create_weekly_pickems_pages(bot, guilds, game_obj):
        config = hockey_config()
        save_data = {}
        today = datetime.now()
        new_day = timedelta(days=1)
        count = 0

        while True:
            chn_name = _("pickems-{month}-{day}").format(
                month=today.month, day=today.day
            )
            data = []
            for guild in guilds:
                new_chn = await Pickems.create_pickems_channel(bot, chn_name, guild)
                data.append(new_chn)

            for new_channel in data:
                if new_channel is None:
                    continue
                if new_channel.guild.id not in save_data:
                    save_data[new_channel.guild.id] = [new_channel.id]
                else:
                    save_data[new_channel.guild.id].append(new_channel.id)

            games_list = await game_obj.get_games(None, today, today)

            for game in games_list:
                for channel in data:
                    if channel:
                        await Pickems.create_pickems_game_msg(bot, channel, game)
                        await asyncio.sleep(0.1)
            # await asyncio.gather(*game_msg_tasks)
            today = today + new_day
            count += 1
            if today.weekday() == 6 or count == 7:
                # just incase we end up in an infinite loop somehow
                # can never be too careful with async coding
                break
        for guild_id, channels in save_data.items():
            guild = bot.get_guild(guild_id)
            if not guild:
                continue
            await config.guild(guild).pickems_channels.set(channels)

    @staticmethod
    async def delete_pickems_channels(bot, channels):
        log.debug("Deleting pickems channels")
        for channel_id in channels:
            channel = bot.get_channel(channel_id)
            if not channel:
                continue
            try:
                await channel.delete()
            except discord.errors.Forbidden:
                pass
            except Exception:
                log.error(_("Error deleting old pickems channels"), exc_info=True)

    @staticmethod
    async def tally_leaderboard(bot):
        """
            This should be where the pickems is removed and tallies are added
            to the leaderboard
        """
        config = hockey_config()

        for guild_id, pickem_list in bot.get_cog("Hockey").all_pickems.items():
            guild = bot.get_guild(id=guild_id)
            if guild is None:
                continue
            try:
                to_remove = []
                for name, pickems in pickem_list.items():
                    if pickems.winner is not None:
                        to_remove.append(name)
                        leaderboard = await config.guild(guild).leaderboard()
                        if leaderboard is None:
                            leaderboard = {}
                        for user, choice in pickems.votes.items():
                            if str(user) not in leaderboard:
                                leaderboard[str(user)] = {"season": 0, "weekly": 0, "total": 0}
                            if choice == pickems.winner:
                                if str(user) not in leaderboard:
                                    leaderboard[str(user)] = {"season": 1, "weekly": 1, "total": 0}
                                else:
                                    leaderboard[str(user)]["season"] += 1
                                    leaderboard[str(user)]["weekly"] += 1
                            if "total" not in leaderboard[str(user)]:
                                leaderboard[str(user)]["total"] = 0
                            leaderboard[str(user)]["total"] += 1
                        await config.guild(guild).leaderboard.set(leaderboard)
                for name in to_remove:
                    try:
                        del bot.get_cog("Hockey").all_pickems[name]
                    except Exception as e:
                        log.error("Error removing pickems from memory", exc_info=True)
                # await config.guild(guild).pickems.set(
                    # [p.to_json() for p in pickem_list if p.winner is None]
                # )
            except Exception:
                log.error(_("Error tallying leaderboard in ") + f"{guild.name}", exc_info=True)

    def to_json(self) -> dict:
        return {
            "message": self.message,
            "channel": self.channel,
            "game_start": self.game_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": self.home_team,
            "away_team": self.away_team,
            "votes": self.votes,
            "winner": self.winner,
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            data["message"],
            data["channel"],
            data["game_start"],
            data["home_team"],
            data["away_team"],
            data["votes"],
            data["winner"],
        )
