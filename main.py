# a Discord Bot
# with the ability to play music
# and to do some other stuff
# like telling the time
# or the weather
# and to search on reddit
import asyncio
import datetime
import os
import random
import re
import urllib
import youtube_dl

import discord
import asyncpraw
import praw
import pyowm
import requests
import openai
import wandb

from discord import client
from discord.app_commands import commands
from dotenv import load_dotenv
from prawcore import ResponseException

load_dotenv()

# get the API Key from .env
APIKEY = os.environ.get('WEATHER_API_KEY')
openai.api_key = os.getenv("OPENAI_API_KEY")
print(APIKEY)
OpenWMap = pyowm.OWM(APIKEY)
base_url = "http://api.openweathermap.org/data/2.5/weather?"

intent = discord.Intents.default()
intent.members = True
intent.message_content = True
intent.messages = True
intent.voice_states = True
client = discord.Client(intents=intent)

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                  'options': '-vn'}
YTDL_OPTIONS = {
    'format': 'bestaudio',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
}


@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')
    await client.change_presence(activity=discord.Game(name="now waiting for commands"))


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    print(message.content)
    await manage_message(message)


async def manage_message(message):
    if message.content.startswith('!weather'):
        await weather(message)
    if message.content.startswith('!reddit'):
        await reddit(message)
    if message.content.startswith('!time'):
        await time(message)
    if message.content.startswith('!youtube'):
        await youtube(message)
    if message.content.startswith('!jarvis'):
        await gpt3(message)
    if message.content.startswith('!help'):
        await help_message(message)


async def gpt3(message):
    gpt_prompt = message.content[6:]
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=gpt_prompt,
        temperature=0.5,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
    )
    gpt_output = discord.Embed()
    gpt_output.title = "Jarvis: "
    gpt_output.description = response['choices'][0]['text']
    await message.channel.send(embed=gpt_output)


async def help_message(message):
    embed = discord.Embed(title="Help", color=0x00ff00)
    embed.add_field(name="!weather", value="Get the weather for a city", inline=False)
    embed.add_field(name="!reddit", value="Get a random post from a subreddit", inline=False)
    embed.add_field(name="!time", value="Get the current time", inline=False)
    embed.add_field(name="!youtube", value="Search for a video on youtube", inline=False)
    embed.add_field(name="!jarvis", value="Talk to Jarvis", inline=False)
    await message.channel.send(embed=embed)


async def youtube(message):
    ydl = youtube_dl.YoutubeDL(YTDL_OPTIONS)
    info = ydl.extract_info("ytsearch:" + message.content[9:], download=False)['entries'][0]
    url = info['url']
    embed = discord.Embed()
    embed.title = info['title']
    embed.url = url
    embed.description = info['description']
    embed.set_image(url=info['thumbnail'])
    await message.channel.send(embed=embed)
    # get the voice channel
    if hasattr(message.author.voice, 'channel'):
        voice_channel = message.author.voice.channel
        # join the voice channel
        voice = await voice_channel.connect()
        # play the audio
        voice.play(discord.FFmpegPCMAudio(executable="C:/ffmpeg/bin/ffmpeg.exe", source=url, **FFMPEG_OPTIONS))
        # disconnect after the player has finished
        while voice.is_playing():
            await asyncio.sleep(1)
    else:
        embed = discord.Embed(title="You are not connected to a voice channel", color=0xff0000)
        embed.description = "Please join a voice channel and try again"
        await message.channel.send(embed=embed)





async def weather(message):
    location = message.content[9:]
    URL = base_url + "q=" + location + "&appid=" + APIKEY
    print(URL)
    response = requests.get(URL)
    if response.status_code == 200:
        data = response.json()
    main = data['main']
    temperature = main['temp']
    temperature = temperature - 273
    humidity = main['humidity']
    pressure = main['pressure']
    report = data['weather']
    print(main)
    temperature = round(temperature)
    descripton = "".join([
        (str(f"Temperature: {temperature}""\n")),
        (str(f"Humidity: {humidity}""\n")),
        (str(f"Pressure: {pressure}""\n")),
        (str(f"Weather Report: {report[0]['description']}""\n"))])
    weather_output = discord.Embed()
    weather_output.title = "Weather: " + location
    weather_output.description = descripton
    # color like the temperature
    if temperature < 0:
        weather_output.color = 0x0000ff
    elif temperature < 10:
        weather_output.color = 0x00ffff
    elif temperature < 20:
        weather_output.color = 0x00ff00
    elif temperature < 30:
        weather_output.color = 0xffff00
    elif temperature < 40:
        weather_output.color = 0xff0000
    else:
        weather_output.color = 0xff00ff

    await message.channel.send(embed=weather_output)


async def reddit(message):
    subreddit = message.content[8:]
    try:
        post = await get_reddit_post(subreddit)
    except Exception as e:
        embed = discord.Embed(title="Subreddit not found", description=e, color=0xff0000)
        await message.channel.send(embed=embed)
        return

    print(post.title + " " + post.url)
    embed = discord.Embed()
    embed.title = post.title
    embed.url = post.url
    embed.description = post.selftext
    # check if the post has an image
    if post.url.endswith((".png", ".jpg", ".jpeg", ".gif", ".gifv")):
        embed.set_image(url=post.url)
    await message.channel.send(embed=embed)


async def get_reddit_post(subreddit):
    try:
        reddit_client = asyncpraw.Reddit(client_id=os.environ.get('REDDIT_CLIENT_ID'),
                                         client_secret=os.environ.get('REDDIT_CLIENT_SECRET'),
                                         user_agent="discord bot")
        subreddit = await reddit_client.subreddit(subreddit)
        posts = subreddit.hot(limit=10)
        post = random.choice([post async for post in posts if not post.stickied])
        return post
    except Exception as e:
        raise e


async def time(message):
    time = datetime.datetime.now()
    output = "".join([(str(f"{time:-^30}""\n"))])
    await message.channel.send(output)


client.run(os.getenv("DISCORD_TOKEN"))
