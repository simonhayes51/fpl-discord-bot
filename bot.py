import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Load .env file locally (ignored in Railway)
load_dotenv()

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
        print(f"🔁 Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# Test command
@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

# 🔍 Load token from environment
token = os.getenv("DISCORD_TOKEN")
print("🔍 DISCORD_TOKEN loaded as:", repr(token))  # For debugging

if not token or not isinstance(token, str):
    raise ValueError("❌ DISCORD_TOKEN is not set or invalid. Make sure it's configured in Railway or your .env file.")

# ✅ Run the bot
bot.run(token)
