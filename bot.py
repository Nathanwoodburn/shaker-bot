import base64
import os
from dotenv import load_dotenv
import discord
from discord import app_commands
import json
from faucet import send_domain
import dns.resolver
import dns.exception
import dns.message
import shaker
import re


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ADMINID = 0

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Commands
@tree.command(name="faucet", description="Get a free domain")
async def faucet(ctx, email:str):
    # Check if a DM
    if ctx.guild is None:
        await ctx.response.send_message("You can not claim from the faucet in DMs")
        return


    roles = {}
    if os.path.exists('/data/faucet.json'):
        with open('/data/faucet.json', 'r') as f:
            roles = json.load(f)
    if str(ctx.guild.id) in roles:
        if roles[str(ctx.guild.id)] in [role.id for role in ctx.user.roles]:
            await ctx.response.send_message("I'll send you a DM when your domain has been sent",ephemeral=True)
            await send_domain(ctx.user, email)
            return
    await ctx.response.send_message("You can't claim from the faucet",ephemeral=True)

@tree.command(name="faucet-role", description="Change the role that can use the faucet")
async def faucetrole(ctx,role:discord.Role):
    if ctx.user.id != ADMINID:
        await ctx.response.send_message("You don't have permission to do that",ephemeral=True)
        return
    await ctx.response.send_message("Faucet role set to " + role.name + " for server " + ctx.guild.name,ephemeral=True)
    roles = {}
    if os.path.exists('/data/faucet.json'):
        with open('/data/faucet.json', 'r') as f:
            roles = json.load(f)
    
    roles[str(ctx.guild.id)] = role.id
    with open('/data/faucet.json', 'w') as f:
        json.dump(roles, f)

@tree.command(name="setverifiedrole", description="Set the role that verified users get")
async def setverifiedrole(ctx,role:discord.Role):
    # Check user has manage guild permission
    if not ctx.user.guild_permissions.manage_guild:
        await ctx.response.send_message("You don't have permission to do that",ephemeral=True)
        return
    # Verify bot can manage roles
    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.response.send_message("I don't have permission to do that",ephemeral=True)
        return
    # Verify I can manage the role
    if not ctx.guild.me.top_role > role:
        await ctx.response.send_message("I don't have permission to do that",ephemeral=True)
        return
    
    if not os.path.exists('/data/roles.json'):
        with open('/data/roles.json', 'w') as f:
            json.dump({}, f)

    with open('/data/roles.json', 'r') as f:
        roles = json.load(f)

    roles[str(ctx.guild.id)] = role.id
    with open('/data/roles.json', 'w') as f:
        json.dump(roles, f)   
    
    await ctx.response.send_message("Verified role set to " + role.name + " for server " + ctx.guild.name,ephemeral=True)
    
@tree.command(name="verify", description="Verifies your ownership of a Handshake name and sets your nickname.")
async def verify(ctx, domain:str):
    name_idna = domain.lower().strip().rstrip("/").encode("idna")
    name_ascii = name_idna.decode("ascii")
    
    parts = name_ascii.split(".")

    for part in parts:
        if not re.match(r'[A-Za-z0-9-_]+$', part):
            return await ctx.response.send_message("Invalid domain",ephemeral=True)
    

    try:
        name_rendered = name_idna.decode("idna")
    except UnicodeError: # don't render invalid punycode
        name_rendered = name_ascii

    if shaker.check_name(ctx.user.id, name_ascii):
        try:
            await ctx.user.edit(nick=name_rendered + "/")
            # Set role
            await shaker.handle_role(ctx.user, True)
            return await ctx.response.send_message("Your nickname has been set to " + name_rendered + "/",ephemeral=True)
        except discord.errors.Forbidden:
            return await ctx.response.send_message("I don't have permission to do that",ephemeral=True)
        
    records = [{
            "type": 'TXT',
            "host": ".".join(["_shaker", "_auth"] + parts[:-1]),
            "value": str(ctx.user.id),
            "ttl": 60,
    }]

    records = json.dumps(records)
    records = records.encode("utf-8")
    records = base64.b64encode(records)
    records = records.decode("utf-8")

    message = f"To verify that you own `{name_rendered}/` please create a TXT record located at `_shaker._auth.{name_ascii}` with the following data: `{ctx.user.id}`.\n\n"
    message += f"If you use Namebase, you can do this automatically by visiting the following link:\n"
    message += f"<https://namebase.io/next/domain-manager/{parts[-1]}/records?records={records}>\n\n"
    message += f"Once the record is set (this may take a few minutes) you can run this command again or manually set your nickname to `{name_rendered}/`."

    await ctx.response.send_message(message,ephemeral=True)



# When the bot is ready
@client.event
async def on_ready():
    global ADMINID
    ADMINID = client.application.owner.id
    await tree.sync()

# When a member updates their nickname
@client.event
async def on_member_update(before, after):
    await shaker.check_member(after)

@client.event
async def on_member_join(member) -> None:
    await shaker.check_member(member)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if not message.guild:
        await message.channel.send('Invite this bot into your server by using this link:\nhttps://discord.com/api/oauth2/authorize?client_id=1073940877984153692&permissions=402653184&scope=bot')


client.run(TOKEN)