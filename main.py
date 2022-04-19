import discord
from discord.ext import commands
from discord.ui import Button, View, Item
from discord import Interaction

import re
import configparser
import asyncio
import google_sheets_async as gsa
from gspread import WorksheetNotFound


description = '''ROYLEAGUE bot beta'''

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='%', description=description, intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('-------------------------------------------')


@bot.command()
async def ping(ctx):
    """pong"""
    await ctx.send("Pong 🏓")


@bot.command()
async def debug(ctx):
    """delete me"""  # TODO delete this
    print(ctx.__dict__)
    await ctx.send("check logs")


@bot.group()
async def royleague(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send(f"League: {ctx.subcommand} was not found")


class ResultsView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="confirm", emoji='\U00002714', style=discord.ButtonStyle.green, custom_id='confirm-button')
    async def confirm_callback(self, interaction: Interaction, button: Button):
        button.label = 'Processing'
        button.disabled = True

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="decline", emoji='\U0000274C', style=discord.ButtonStyle.red, custom_id='decline-button')
    async def decline_callback(self, interaction: Interaction, button: Button):
        self.clear_items()
        await interaction.response.edit_message(content="results invalidated", view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        allowed = [discord.utils.find(lambda r: r.name == 'royleague-test', self.ctx.guild.roles)]
        if not any([r in interaction.user.roles for r in allowed]):
            await interaction.response.send_message(f"missing required role {allowed} to interact", ephemeral=True)
            return False
        else:
            return True

    async def on_error(self, interaction: Interaction, error: Exception, item: Item) -> None:
        await interaction.response.send_message(str(error))


@royleague.command(name='match', aliases=['register', 'register_match'])
async def _match(ctx, league: str, division: str, *raw_results):
    leagues = ('NA', 'SA', 'EU', 'AS')
    divisions = ('CL', 'PL', 'D1', 'D2', 'D3', 'D4')
    if league.upper() not in leagues:
        await ctx.send(f"League: {league} not in {leagues}")
        return
    if division.upper() not in divisions:
        await ctx.send(f"Division: {division} not in {divisions}")
        return
    if len(raw_results) < 3:
        await ctx.send(f"Not enough parameters. expected 3. got {len(raw_results)}")
        return
    elif not (p1_match := re.match(r"^<@(\d{17,18})>$", raw_results[0])):
        await ctx.send(f"{raw_results[0]} isn't a valid ping of a discord member")
        return
    elif not (p2_match := re.match(r"^<@(\d{17,18})>$", raw_results[-1])):
        await ctx.send(f"{raw_results[-1]} isn't a valid ping of a discord member")
        return

    p1_raw, *result, p2_raw = raw_results
    result = "".join(result)
    p1_score, p2_score = "".join(result).split('-')
    league, division = league.upper(), division.upper()

    try:
        player1_user = await bot.fetch_user(int(p1_match.group(1)))
        player2_user = await bot.fetch_user(int(p2_match.group(1)))
    except discord.NotFound:
        await ctx.reply(f'player {p1_raw} or {p2_raw} is Unknown', ephemeral=True)
        return
    result_dict = {'league': league, 'division': division,
                   'player1': (player1_user.name, p1_score),
                   'player2': (player2_user.name, p2_score)
                   }
    view = ResultsView(ctx)
    msg = await ctx.send(f"**{league} {division}** {p1_raw} {p1_score} - {p2_score} {p2_raw}", view=view)

    def check_confirm(interaction: Interaction):
        allowed = [discord.utils.find(lambda r: r.name == 'royleague-test', ctx.guild.roles)]
        return (interaction.data['component_type'] == 2 and interaction.data['custom_id'] == 'confirm-button'
                and any(r in interaction.user.roles for r in allowed))

    try:
        res = await bot.wait_for('interaction', check=check_confirm, timeout=60*30)
        try:
            updated_flag = await gsa.update_league_sheet(gsa.agcm_royleague, result_dict)
            if updated_flag:
                await res.followup.send('sheet updated', ephemeral=True)
                await msg.edit(view=View())
            else:
                await res.followup.send("didn't change anything", ephemeral=True)
                await msg.edit(view=View())
        except gsa.PlayerNotFound as nf_e:
            await res.followup.send(f'player {nf_e.player} not found in {league} {division}', ephemeral=True)
        except WorksheetNotFound:
            await res.followup.send(f'worksheet {league} {division} not found', ephemeral=True)
    except asyncio.TimeoutError:
        await msg.edit(content='Timed out', view=View())


@royleague.command(name='list', aliases=['players'])
async def _list(ctx, league: str, division: str,):
    leagues = ('NA', 'SA', 'EU', 'AS')
    divisions = ('CL', 'PL', 'D1', 'D2', 'D3', 'D4')
    if (leag_up := league.upper()) not in leagues:
        await ctx.send(f"League: {league} not in {leagues}")
        return
    if (div_up := division.upper()) not in divisions:
        await ctx.send(f"Division: {division} not in {divisions}")
        return
    try:
        players = await gsa.list_players(gsa.agcm_royleague, leag_up, div_up)
        nl = '\n'
        players_str = f'**{leag_up} {div_up}** Players:\n{nl.join(players[0])}'
        await ctx.send(players_str)
    except WorksheetNotFound:
        await ctx.send(f"worksheet {league} {division} not found")


@bot.event
async def on_command_error(ctx, error):
    await ctx.send(ctx.command)
    await ctx.send(error)
    raise error


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('token.ini')
    bot.run(config.get('py-bot-testing', 'token'))
