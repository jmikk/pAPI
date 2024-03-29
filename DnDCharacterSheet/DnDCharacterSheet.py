from redbot.core import commands, Config, data_manager
import random
import discord
import os
import asyncio
from collections import Counter 
from discord.ui import Button, View
from discord import ButtonStyle, Interaction
from discord import Embed
from discord import Color
from discord.utils import MISSING

class PotionView(View):
    def __init__(self, cog, ctx, member, potions, message=None):
        super().__init__()
        self.ctx = ctx
        self.member = member
        self.potions = potions
        self.current_index = 0
        self.cog = cog
        self.message = message  # The original message reference
        self.embed = MISSING  # Initialize the embed to MISSING
        self.update_embed()  # Update the embed with the first potion's details

        # Previous Button
        self.previous_button = Button(label="Previous", style=discord.ButtonStyle.grey)
        self.previous_button.callback = self.previous_potion
        self.add_item(self.previous_button)

        # Next Button
        self.next_button = Button(label="Next", style=discord.ButtonStyle.grey)
        self.next_button.callback = self.next_potion
        self.add_item(self.next_button)

        self.give_to_guild_button = Button(label="Give to Guild", style=discord.ButtonStyle.blurple)
        self.give_to_guild_button.callback = self.give_to_guild
        self.add_item(self.give_to_guild_button)

    async def log(self, message: str):
        await self.ctx.send(message)

    async def previous_potion(self, interaction):
        # Decrement the index and update the embe
        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.current_index = len(self.potions) - 1  # Loop back to the last potion
        self.update_embed()

        # Respond to the interaction by updating the message with the new embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def next_potion(self, interaction):
        # Increment the index and update the embed
        self.current_index = (self.current_index + 1) % len(self.potions)  # Loop back to the first potion
        self.update_embed()

        # Respond to the interaction by updating the message with the new embed
        await interaction.response.edit_message(embed=self.embed, view=self)


    def update_embed(self):
        if self.potions:
            potion_name, potion_details = self.potions[self.current_index]
            effects_text = "\n".join(f"{effect['name']}: {effect['text']}" for effect in potion_details['effects'])
            self.embed = Embed(title=f"{potion_name} (Quantity: {potion_details['quantity']})", description=effects_text, color=Color.blue())
            self.embed.set_footer(text=f"Potion {self.current_index + 1} of {len(self.potions)}")
        else:
            self.embed = Embed(title="No potions available", description="You currently have no potions in your stash.", color=Color.red())


    async def give_to_guild(self, interaction: discord.Interaction):
        try:

            potion_name, potion_details = self.potions[self.current_index]  # Corrected potion extraction
    
            user = interaction.user  # Assuming the user who clicked is the one giving the potion
            guild = interaction.guild  # The guild where the interaction happened
    
            user_potions = await self.cog.config.member(user).potions()
            guild_stash = await self.cog.config.guild(guild).stash()
    
            # Add the potion to the guild's stash
            if potion_name in guild_stash:
                guild_stash[potion_name]['quantity'] += 1
            else:
                guild_stash[potion_name] = {'quantity': 1, 'effects': potion_details.get('effects', [])}
    
            # Decrement the potion's quantity from the user's inventory
            user_potions[potion_name]['quantity'] -= 1
    
            # If the potion quantity is 0, remove it from the inventory
            if user_potions[potion_name]['quantity'] == 0:
                del user_potions[potion_name]
                if self.current_index > 0:  # Adjust the index if necessary
                    self.current_index -= 1
    
            # Save the updated stashes
            await self.cog.config.member(user).potions.set(user_potions)
            await self.cog.config.guild(guild).stash.set(guild_stash)
    
            # Update the view
            self.update_embed()
                        
            # Send a follow-up message to confirm the action to the user
            await interaction.response.edit_message(embed=self.embed, view=self)
            await interaction.followup.send(f"You gave one {potion_name} to the guild's stash.")
    
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @discord.ui.button(label="Drink", style=ButtonStyle.green)
    async def drink(self, interaction: Interaction, button: Button):
        try:
            potion_name, potion_details = self.potions[self.current_index]
            potion_quantity = potion_details['quantity']
            potion_effects = potion_details['effects']
            #await interaction.response.send_message(f"{potion_name}\n{potion_details['effects']}\n {potion_effects}\n{potion_quantity}", view=self)

            potion_effects = "\n".join([f"{effect['name']}: {effect['text']}" for effect in potion_details['effects']])

            potion_details['quantity'] -= 1
    
            if potion_details['quantity'] <= 0:
                self.potions.pop(self.current_index)
                self.current_index = max(self.current_index - 1, 0)
            #await interaction.response.send_message(f"{potion_effects}")
            await self.cog.config.member(self.member).potions.set({potion_name: potion_details for potion_name, potion_details in self.potions})

            self.update_embed()

            
            await interaction.response.edit_message(embed=self.embed, view=self)
            await interaction.followup.send(f"{self.member.mention} drank {potion_name}!\nEffects:\n{potion_effects}")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")




class DnDCharacterSheet(commands.Cog):
    """Gives items to players with random effects"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier="9003s_guild_items", force_registration=True)

        default_guild = {
            "items": {},
            "stash": {}
        }

        default_member = {
            "inventory": {},
            "potions":{}
        }

        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)

    # Command group for D&D related commands
    @commands.group(name="D&D")
    async def dnd(self, ctx):
        """D&D Commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Type `help D&D` for more information on D&D commands.")


    async def read_effects_tsv(self):
        effects = []
        # Construct the path to your effects.tsv file within the cog's data directory
        effects_filepath = os.path.join(data_manager.cog_data_path(self), 'effects.tsv')
        
        with open(effects_filepath, 'r') as file:
            for line in file:
                parts = line.strip().split('\t')
                if len(parts) == 4:  # Ensure there are exactly 4 columns
                    effects.append({
                        "Name": parts[0],
                        "Effect": parts[1],
                        "Duration": parts[2],
                        "Notes": parts[3]
                    })
        return effects

    @dnd.command(name="giveitem")
    @commands.has_role("Last Light (DM)")
    async def giveitem(self, ctx, member: discord.Member, item_name: str):
        """Gives a randomly effectuated item to a specified player"""

        # Read effects from TSV
        all_effects = await self.read_effects_tsv()

        # Check if item already exists in guild config
        guild_items = await self.config.guild(ctx.guild).items.all()
        
        if item_name in guild_items:
            item_effects = guild_items[item_name]
        else:
            # Pick 4 unique random effects for the new item
            item_effects = random.sample(all_effects, 4)
            # Save the new item with its effects to the guild config
            await self.config.guild(ctx.guild).items.set_raw(item_name, value=item_effects)

        # Add the item to the specified user's inventory
        user_inventory = await self.config.member(member).inventory.all()
        user_inventory[item_name] = item_effects
        await self.config.member(member).inventory.set(user_inventory)

        await ctx.send(f"{member.display_name} has been given the item: {item_name} with {item_effects}!")

    
    async def paginate_inventory(self, ctx, inventory, member):
        """Sends paginated embeds of the inventory items."""
        items_per_page = 10
        pages = [inventory[i:i + items_per_page] for i in range(0, len(inventory), items_per_page)]

        def get_embed(page_index):
            embed = discord.Embed(title=f"{member.display_name}'s Inventory", color=discord.Color.blue())
            page = pages[page_index]
            for item in page:
                embed.add_field(name=item, value="\u200b", inline=False)
            embed.set_footer(text=f"Page {page_index + 1}/{len(pages)}")
            return embed

        current_page = 0
        message = await ctx.send(embed=get_embed(current_page))

        # Reaction controls
        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"] and reaction.message.id == message.id

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)

                if str(reaction.emoji) == "▶️" and current_page < len(pages) - 1:
                    current_page += 1
                    await message.edit(embed=get_embed(current_page))
                    await message.remove_reaction(reaction, user)
                elif str(reaction.emoji) == "◀️" and current_page > 0:
                    current_page -= 1
                    await message.edit(embed=get_embed(current_page))
                    await message.remove_reaction(reaction, user)
                else:
                    await message.remove_reaction(reaction, user)
            except asyncio.TimeoutError:
                await message.clear_reactions()
                break

    @dnd.command(name="viewinventory")
    async def viewinventory(self, ctx, member: discord.Member = None):
        """View the inventory of a specified user, or your own if no user is specified."""

        if not member:
            member = ctx.author

        user_inventory = await self.config.member(member).inventory()

        if user_inventory:
            inventory_list = list(user_inventory.keys())
            await self.paginate_inventory(ctx, inventory_list, member)
        else:
            await ctx.send(f"{member.display_name} has no items in their inventory.")

    @dnd.command(name="clearinventory")
    @commands.is_owner()
    async def clear_inventory(self, ctx, member: discord.Member):
        """Clear the entire inventory of a specified player"""
        await self.config.member(member).inventory.clear()
        await ctx.send(f"{member.display_name}'s inventory has been cleared.")

    @dnd.command(name="deleteitem")
    @commands.is_owner()
    async def delete_item(self, ctx, member: discord.Member, *, item_name: str):
        """Delete a specific item from a player's inventory"""
        user_inventory = await self.config.member(member).inventory()
        if item_name in user_inventory:
            del user_inventory[item_name]
            await self.config.member(member).inventory.set(user_inventory)
            await ctx.send(f"Item '{item_name}' has been removed from {member.display_name}'s inventory.")
        else:
            await ctx.send(f"{member.display_name} does not have an item named '{item_name}'.")


    @dnd.command(name="clearpotions")
    @commands.is_owner()
    async def clear_potions(self, ctx, member: discord.Member):
        """Clear the entire inventory of a specified player"""
        await self.config.member(member).potions.clear()
        await ctx.send(f"{member.display_name}'s potions has been cleared.")

    @dnd.command(name="deletepotion")
    @commands.is_owner()
    async def delete_potions(self, ctx, member: discord.Member, *, item_name: str):
        """Delete a specific item from a player's inventory"""
        user_inventory = await self.config.member(member).potions()
        if item_name in user_inventory:
            del user_inventory[item_name]
            await self.config.member(member).potions.set(user_inventory)
            await ctx.send(f"Item '{item_name}' has been removed from {member.display_name}'s potions.")
        else:
            await ctx.send(f"{member.display_name} does not have an item named '{item_name}'.")
            
    @dnd.command(name="eatitem")
    async def eat_item(self, ctx, *, item_name: str):
        """Eat an item from your inventory, deleting it and showing its first effect."""
        user_inventory = await self.config.member(ctx.author).inventory()

        if item_name in user_inventory:
            item_effects = user_inventory[item_name]
            if item_effects:
                # Assuming item_effects is a list of effects and you want to show the first one
                first_effect = item_effects[0]
                await ctx.send(f"{ctx.author.display_name} eats the {item_name} and experiences: {first_effect['Name']}, {first_effect['Effect']}, for {first_effect['Duration']} (when used in a potion), Notes: {first_effect['Notes']} ")
            else:
                await ctx.send(f"The {item_name} seems to have no effects.")

            # Delete the item from the inventory after "eating" it
            del user_inventory[item_name]
            await self.config.member(ctx.author).inventory.set(user_inventory)
        else:
            await ctx.send(f"You don't have an item named '{item_name}' in your inventory.")

    @dnd.command(name="brew")
    async def brew(self, ctx, *item_names: str):
        """Brew a potion using items from your inventory, using up to three of the most shared effects, and add or update it in your potions with effect text and adjusted quantity."""
        user_data = await self.config.member(ctx.author).all()
    
        if 'potions' not in user_data:
            user_data['potions'] = {}
    
        missing_items = [item for item in item_names if item not in user_data.get('inventory', {})]
        if missing_items:
            await ctx.send(f"Brewing failed, missing: {', '.join(missing_items)}")
            return
    
        all_effects = []  # Store tuples of (effect_name, effect_text)
        for item_name in item_names:
            item_effects = user_data.get('inventory', {}).get(item_name, [])
            for effect in item_effects:
                effect_name = effect.get('Name', 'Unnamed Effect')
                effect_text = effect.get('Effect', 'Unnamed Effect')
                all_effects.append((effect_name, effect_text))
    
            # Remove the used ingredients from the inventory
            del user_data['inventory'][item_name]
    
        # Count the effects based on effect names and find the most common ones
        effect_counts = Counter([effect_name for effect_name, _ in all_effects])
        most_common_effects = effect_counts.most_common()
        highest_count = most_common_effects[0][1] if most_common_effects else 0
    
        # Get tuples of all effects that share the highest count
        final_effects = [effect for effect in all_effects if effect_counts[effect[0]] == highest_count]
    
        if len(final_effects) > 3:
            final_effects = random.sample(final_effects, 3)
    
        if final_effects:
            potion_effects_data = [{'name': name, 'text': text} for name, text in final_effects]
            potion_name = "Potion of " + " and ".join(name for name, _ in final_effects)
    
            # Diagnostic logging to understand the current structure of the potion
            if potion_name in user_data['potions']:
                current_structure = user_data['potions'][potion_name]
    
            # Check if the potion already exists and increase the quantity if it does
            if potion_name in user_data['potions'] and isinstance(user_data['potions'][potion_name], dict) and 'quantity' in user_data['potions'][potion_name]:
                user_data['potions'][potion_name]['quantity'] += 1
            else:
                # New potion entry with effects and initial quantity
                user_data['potions'][potion_name] = {
                    'effects': potion_effects_data,
                    'quantity': 1
                }
    
            await ctx.send(f"Successfully brewed {potion_name} with effects: {', '.join(name for name, _ in final_effects)}")
            await self.config.member(ctx.author).set(user_data)
        else:
            await ctx.send("Brewing failed. The ingredients share no common effects.")


    @dnd.command(name="clearstash")
    @commands.guild_only()  # Ensure this command is only usable within a guild
    @commands.has_permissions(administrator=True)  # Restrict to users with the Administrator permission
    async def clear_stash(self, ctx):
        # Set the guild's stash to an empty dictionary, effectively clearing it
        await self.config.guild(ctx.guild).stash.set({})
        
        # Send a confirmation message
        await ctx.send("The guild stash has been cleared.")


    @dnd.command(name="viewpotions")
    async def view_potions(self, ctx):
        
        member = ctx.author
    
        member_potions = await self.config.member(member).potions()
    
        if not member_potions:
            await ctx.send(f"{member.display_name}'s potion stash is empty.")
            return
    
        potions_list = list(member_potions.items())
    
        # Check if there are potions in the list
        if potions_list:
            potion_name, potion_details = potions_list[0]  # Get the first potion's details
            effects_text = "\n".join(f"{effect['name']}: {effect['text']}" for effect in potion_details['effects'])
            initial_embed = Embed(title=f"{potion_name} (Quantity: {potion_details['quantity']})", description=effects_text, color=Color.blue())
            initial_embed.set_footer(text=f"Potion 1 of {len(potions_list)}")
        else:
            # No potions available
            initial_embed = Embed(title="No potions available", description="You currently have no potions in your stash.", color=Color.red())
    
        # Send the initial message
        message = await ctx.send(embed=initial_embed)
    
        # Instantiate PotionView with the message reference
        view = PotionView(self, ctx, member, potions_list, message=message)
        await message.edit(embed=initial_embed, view=view)  # Make sure the view is attached to the message





