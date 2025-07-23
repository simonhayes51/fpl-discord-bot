import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from aiohttp import web
import asyncio
import json

TOKEN = os.getenv("DISCORD_TOKEN")
FPL_BASE = "https://fantasy.premierleague.com/api"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler()

SETTINGS_FILE = "settings.json"

# Load settings
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        guild_settings = json.load(f)
else:
    guild_settings = {}

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(guild_settings, f)

# ---------- FPL Data ----------
async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def get_bootstrap():
    return await fetch_json(f"{FPL_BASE}/bootstrap-static/")

async def get_current_gw():
    bootstrap = await get_bootstrap()
    for event in bootstrap['events']:
        if event['is_current']:
            return event['id']
    return 1

async def get_league_standings(league_id):
    data = await fetch_json(f"{FPL_BASE}/leagues-classic/{league_id}/standings/")
    return data['standings']['results']

async def get_manager_picks(entry_id, gw):
    return await fetch_json(f"{FPL_BASE}/entry/{entry_id}/event/{gw}/picks/")

async def get_manager_transfers(entry_id):
    return await fetch_json(f"{FPL_BASE}/entry/{entry_id}/transfers/")

# ---------- Embed Builders ----------
def standings_embed(league_name, standings):
    embed = discord.Embed(
        title=f"🏆 {league_name} - Top 10",
        colour=discord.Colour.gold(),
        timestamp=datetime.utcnow()
    )
    for i, team in enumerate(standings[:10], start=1):
        embed.add_field(
            name=f"{i}. {team['entry_name']}",
            value=f"{team['player_name']} • {team['total']} pts",
            inline=False
        )
    embed.set_footer(text="Updated automatically")
    return embed

def captains_embed(gw, picks):
    embed = discord.Embed(
        title=f"🎯 Captain Picks (GW{gw})",
        colour=discord.Colour.blue(),
        timestamp=datetime.utcnow()
    )
    for manager, captain, vice in picks:
        embed.add_field(
            name=manager,
            value=f"**C:** {captain}\n**VC:** {vice}",
            inline=True
        )
    embed.set_footer(text="Data from FPL")
    return embed

def transfers_embed(transfers):
    embed = discord.Embed(
        title="🔄 Transfers Made",
        colour=discord.Colour.purple(),
        timestamp=datetime.utcnow()
    )
    for manager, count in transfers:
        embed.add_field(
            name=manager,
            value=f"{count} transfers",
            inline=True
        )
    embed.set_footer(text="Data from FPL")
    return embed

# ---------- Summaries ----------
async def build_captain_summary(league_id, gw):
    standings = await get_league_standings(league_id)
    bootstrap = await get_bootstrap()
    players = {p['id']: p['web_name'] for p in bootstrap['elements']}
    picks_data = []
    for team in standings:
        entry_id = team['entry']
        picks = await get_manager_picks(entry_id, gw)
        captain = next(p for p in picks['picks'] if p['is_captain'])
        vice = next(p for p in picks['picks'] if p['is_vice_captain'])
        picks_data.append((team['player_name'], players[captain['element']], players[vice['element']]))
    return picks_data

async def build_transfers_summary(league_id):
    standings = await get_league_standings(league_id)
    transfer_data = []
    for team in standings:
        entry_id = team['entry']
        transfers = await get_manager_transfers(entry_id)
        if transfers:
            transfer_data.append((team['player_name'], len(transfers)))
    return transfer_data

# ---------- Scheduled Jobs ----------
async def post_standings():
    for guild_id, config in guild_settings.items():
        channel = bot.get_channel(config["channel_id"])
        if channel:
            standings = await get_league_standings(config["league_id"])
            embed = standings_embed("League Standings", standings)
            await channel.send(embed=embed)

async def post_captains():
    gw = await get_current_gw()
    for guild_id, config in guild_settings.items():
        channel = bot.get_channel(config["channel_id"])
        if channel:
            picks = await build_captain_summary(config["league_id"], gw)
            embed = captains_embed(gw, picks)
            await channel.send(embed=embed)

async def post_transfers():
    for guild_id, config in guild_settings.items():
        channel = bot.get_channel(config["channel_id"])
        if channel:
            transfers = await build_transfers_summary(config["league_id"])
            embed = transfers_embed(transfers)
            await channel.send(embed=embed)

# ---------- Slash Commands ----------
@bot.tree.command(name="setup", description="Setup FPL bot for this server")
async def setup(interaction: discord.Interaction, league_id: int, channel: discord.TextChannel):
    guild_id = str(interaction.guild.id)
    guild_settings[guild_id] = {"league_id": league_id, "channel_id": channel.id}
    save_settings()
    await interaction.response.send_message(f"✅ Setup complete!\nLeague: `{league_id}`\nChannel: {channel.mention}")

@bot.tree.command(name="view", description="View your current FPL setup")
async def view(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in guild_settings:
        await interaction.response.send_message("⚠️ Not set up yet. Use `/setup` first.", ephemeral=True)
        return
    cfg = guild_settings[guild_id]
    ch = interaction.guild.get_channel(cfg["channel_id"])
    await interaction.response.send_message(f"📋 League: `{cfg['league_id']}`\nChannel: {ch.mention}")

@bot.tree.command(name="standings", description="Show current league standings")
async def standings_cmd(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in guild_settings:
        await interaction.response.send_message("⚠️ Use `/setup` first.")
        return
    standings = await get_league_standings(guild_settings[guild_id]["league_id"])
    embed = standings_embed("League Standings", standings)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="captains", description="Show captain picks for current GW")
async def captains_cmd(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in guild_settings:
        await interaction.response.send_message("⚠️ Use `/setup` first.")
        return
    gw = await get_current_gw()
    picks = await build_captain_summary(guild_settings[guild_id]["league_id"], gw)
    embed = captains_embed(gw, picks)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="transfers", description="Show transfers made")
async def transfers_cmd(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in guild_settings:
        await interaction.response.send_message("⚠️ Use `/setup` first.")
        return
    transfers = await build_transfers_summary(guild_settings[guild_id]["league_id"])
    embed = transfers_embed(transfers)
    await interaction.response.send_message(embed=embed)

# ---------- Health Check ----------
async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# ---------- On Ready ----------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ---------- Main ----------
async def main():
    await start_web_server()
    scheduler.add_job(post_standings, "cron", day_of_week="sun", hour=23)
    scheduler.add_job(post_captains, "cron", day_of_week="fri", hour=18)
    scheduler.add_job(post_transfers, "cron", day_of_week="wed", hour=20)
    scheduler.start()
    await bot.start(TOKEN)

asyncio.run(main())
