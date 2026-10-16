import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import init_db

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="\\", intents=intents)


@bot.event
async def setup_hook():
    await init_db()
    for filename in os.listdir("cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

    await bot.tree.sync()
    print("Synced commands globally")


@bot.event
async def on_ready():
    print(f"{bot.user.name} is online in {len(bot.guilds)} guild(s)")


if __name__ == "__main__":
    if TOKEN is None:
        print("ERROR: DISCORD_BOT_TOKEN not found in .env file.")
    else:
        bot.run(TOKEN)
