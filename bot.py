import discord
from discord.ext import commands
import aiohttp
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")
LEAGUE_ID = 211093  # Your FPL league ID
CHANNEL_ID = 1234567890  # Replace with your Discord channel ID

bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
scheduler = AsyncIOScheduler()
players_data = {}

async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def load_players():
    global players_data
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    data = await fetch(url)
    for p in data['elements']:
        players_data[p['id']] = {
            'name': p['web_name'],
            'price': p['now_cost'] / 10,
            'status': p['status']
        }
    return data

async def get_league_standings():
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{LEAGUE_ID}/standings/"
    return await fetch(url)

async def get_entry(entry_id):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/"
    return await fetch(url)

async def post_standings():
    data = await get_league_standings()
    standings = data['standings']['results']
    channel = bot.get_channel(CHANNEL_ID)
    embed = discord.Embed(title="🏆 League Standings", color=0x1abc9c)
    for team in standings[:10]:
        embed.add_field(name=f"{team['rank']}. {team['entry_name']}", value=f"{team['total']} pts", inline=False)
    await channel.send(embed=embed)

async def post_captains():
    data = await get_league_standings()
    entries = data['standings']['results']
    channel = bot.get_channel(CHANNEL_ID)
    msg = "**Captain Picks for This GW**\n"
    for team in entries[:10]:
        entry_id = team['entry']
        entry_data = await get_entry(entry_id)
        try:
            picks = entry_data['current_event_picks']
        except KeyError:
            continue
        captain = next((p for p in picks if p['is_captain']), None)
        if captain:
            cap_name = players_data[captain['element']]['name']
            msg += f"**{team['entry_name']}** → {cap_name}\n"
    await channel.send(msg)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await load_players()
    scheduler.start()
    print("✅ Scheduler started")

    # Schedule tasks (example times - adjust as needed)
    scheduler.add_job(post_standings, 'cron', day_of_week='sun', hour=23)  # End of GW
    scheduler.add_job(post_captains, 'cron', day_of_week='fri', hour=17)  # Before deadline

@bot.command()
async def standings(ctx):
    await post_standings()

@bot.command()
async def price(ctx, *, player_name):
    player = next((p for p in players_data.values() if player_name.lower() in p['name'].lower()), None)
    if player:
        await ctx.send(f"{player['name']} is priced at £{player['price']}m")
    else:
        await ctx.send("Player not found.")

bot.run(TOKEN)
