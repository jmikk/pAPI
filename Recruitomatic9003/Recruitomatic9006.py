from redbot.core import commands, Config
import discord
from discord.ui import Button, View
import asyncio

class Recruitomatic9006(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.send_message_task = None
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)

    @commands.command()
    async def start_task(self, ctx):
        if self.send_message_task is not None:
            self.send_message_task.cancel()

        self.send_message_task = asyncio.create_task(self.send_periodic_messages(ctx))

    async def send_periodic_messages(self, ctx):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.send_approval_message(ctx)
            await asyncio.sleep(60)  # Wait X minutes before sending the next message

    async def send_approval_message(self, ctx):
        view = ApprovalView(ctx.author)
        embed = discord.Embed(title="Approval Needed", description="Please click Approve or All Done.", color=0x00ff00)
        message = await ctx.send(embed=embed, view=view)

        def check(interaction):
            return interaction.message.id == message.id and interaction.user == ctx.author

        try:
            interaction = await self.bot.wait_for("interaction", check=check, timeout=180)  # 3 minutes timeout
            await interaction.response.edit_message(content="Button clicked, action taken.", view=None)
        except asyncio.TimeoutError:
            wrap_up_embed = discord.Embed(title="Wrap Up", description="No approval received. Wrapping up.", color=0xff0000)
            await message.edit(embed=wrap_up_embed, view=None)
