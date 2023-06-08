from redbot.core import commands
import asyncio
import random
import discord
import sans
import xml.etree.ElementTree as ET
import os
import discord


def is_owner_overridable():
    def predicate(ctx):
        return False
    return commands.permissions_check(predicate)


class issues(commands.Cog):
    """My custom cog"""

    def __init__(self, bot):
        self.bot = bot
        self.auth = sans.NSAuth()
        self.IssuesNation = ""
        self.client = sans.AsyncClient()
        self.vote_time = 30  # 6 hours in seconds
        self.tie_break_time = 30  # 12 hours in seconds  
        self.stop_loop = False  # Flag to control the while loop
        
    def cog_unload(self):
        asyncio.create_task(self.client.aclose())

    async def api_request(self, data) -> sans.Response:
        response = await self.client.get(sans.World(**data), auth=self.auth)
        response.raise_for_status()
        return response

    @commands.command()
    @commands.is_owner()
    async def stop_issues_loop(self, ctx):
        self.stop_loop = True
        await ctx.send("Stopping the issues loop.")
    
    
    @commands.command()
    @commands.is_owner()
    async def issues_agent(self, ctx, *, agent):
        sans.set_agent(agent, _force=True)
        await ctx.send("Agent set.")

    @commands.command()
    @commands.is_owner()
    async def set_issues_nation(self, ctx, *, nation):
        nation = "_".join(nation.lower().split())
        self.IssuesNation = nation
        await ctx.send(f"Set regional nation to {self.IssuesNation}")

    @commands.command()
    @commands.is_owner()
    async def set_issues_nation_password(self, ctx, *, password2):
        self.auth = sans.NSAuth(password=password2)
        await ctx.send(f"Set regional nation password for {self.IssuesNation}.")

    @commands.command()
    @commands.is_owner()
    async def issues(self, ctx):
        self.stop_loop = False
        while not self.stop_loop:
            r = await self.api_request(data={'nation': self.IssuesNation, 'q': 'issues'})
            root = ET.fromstring(r.text)
            issues = root.findall('ISSUES/ISSUE')
            issue = issues[0]
            issue_id = issue.attrib['id']
            title = issue.find('TITLE').text
            text = issue.find('TEXT').text
            author = issue.find('AUTHOR').text
            editor = issue.find('EDITOR').text
            pic1 = issue.find('PIC1').text
            pic2 = issue.find('PIC2').text
            option_messages = []
            options = [
                {'id': option.attrib['id'], 'text': option.text}
                for option in issue.findall('OPTION')
            ]
            embed = discord.Embed(
                title=title,
                description='The issue at hand',
                color=discord.Color.blue()
            )
            embed.set_author(name=f'Written by {author}, Edited by {editor}')
            embed.add_field(name='The issue', value=text, inline=False)
            message = await ctx.send(embed=embed)

            for option in options:
                embed = discord.Embed(
                    title="This might work...",
                    color=discord.Color.blue()
                )
                embed.add_field(name=option['id'], value=option['text'], inline=False)
                option_message = await ctx.send(embed=embed)
                await option_message.add_reaction('👍')  # Add thumbs up reaction to each option message

            await asyncio.sleep(self.vote_time)  # Wait for the voting time

            reactions = []
            channel = ctx.channel
            for option_message_id in option_messages:
                option_message = await channel.fetch_message(option_message_id)
                reaction = discord.utils.get(option_message.reactions, emoji='👍')
                if reaction:
                    reactions.append((option_message_id, reaction.count))

            if not reactions:
                chosen_option = random.choice(options)
            else:
                max_votes = max(reactions, key=lambda x: x[1])[1]
                tied_options = [option_id for option_id, votes in reactions if votes == max_votes]
                chosen_option_id = tied_options[0]
                chosen_option = next(option for option in options if option['id'] == chosen_option_id)

            await self.AnswerIssue(ctx, chosen_option)

    async def AnswerIssue(self, ctx, option_id):
        await ctx.send(f"picked option {option_id}")
        pass

    @commands.command()
    @commands.is_owner()
    async def myCom(self, ctx):
        await ctx.send("I work")
