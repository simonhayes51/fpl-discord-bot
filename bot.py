import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()  # Works locally if you have a .env file

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name}")

    try:
        await bot.load_extension("cogs.pricecheck")
        print("📦 Loaded pricecheck cog")
    except Exception as e:
        print(f"❌ Failed to load pricecheck cog: {e}")

    try:
        await bot.load_extension("cogs.pricecheckgg")
        print("📦 Loaded pricecheckgg cog")
    except Exception as e:
        print(f"❌ Failed to load pricecheckgg cog: {e}")

    try:
        synced = await bot.tree.sync()
        print(f"🔁 Globally synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

# ✅ Safe cross-env token handling
token = os.getenv("DISCORD_TOKEN")

if not token:
    raise ValueError("❌ DISCORD_TOKEN not found. Make sure it's set in Railway or in your local .env file.")

bot.run(token)
