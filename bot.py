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
import datetime


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ADMINID = 0
LOCAL = False
if os.getenv('LOCAL') == "True":
    LOCAL = True

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

faucet_messages = []

faucet_roles = '/data/faucet.json'
verified_roles = '/data/roles.json'

if LOCAL:
    faucet_roles = 'faucet.json'
    verified_roles = 'roles.json'

# Commands
@tree.command(name="faucet", description="Get a free domain")
async def faucet(ctx, email:str):
    # Check if a DM
    if ctx.guild is None:
        await ctx.response.send_message("You can not claim from the faucet in DMs")
        return


    roles = {}
    if os.path.exists(faucet_roles):
        with open(faucet_roles, 'r') as f:
            roles = json.load(f)
    if str(ctx.guild.id) in roles:
        if roles[str(ctx.guild.id)] in [role.id for role in ctx.user.roles]:
            await ctx.response.send_message("The faucet will gift you a domain when someone approves your request",ephemeral=True)
            message = await ctx.channel.send(f"Faucet request from {ctx.user.name} (<@{ctx.user.id}>)\n\nThis is a gift from the faucet. You will receive a domain when someone approves your request.\n\nPlease approve this gift by reacting to this message with a 👍")
            faucet_messages.append({
                "id": message.id,
                "email": email,
                "user": ctx.user.id,
                "time": datetime.datetime.now()
            })
            print(faucet_messages)
            await message.add_reaction("👍")
            return
    await ctx.response.send_message("You can't claim from the faucet",ephemeral=True)

@tree.command(name="setfaucetrole", description="Change the role that can use the faucet")
async def faucetrole(ctx,role:discord.Role):
    if ctx.user.id != ADMINID:
        await ctx.response.send_message("You don't have permission to do that",ephemeral=True)
        return
    await ctx.response.send_message("Faucet role set to " + role.name + " for server " + ctx.guild.name,ephemeral=True)
    roles = {}
    if os.path.exists(faucet_roles):
        with open(faucet_roles, 'r') as f:
            roles = json.load(f)
    
    roles[str(ctx.guild.id)] = role.id
    with open(faucet_roles, 'w') as f:
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
    
    if not os.path.exists(verified_roles):
        with open(verified_roles, 'w') as f:
            json.dump({}, f)

    with open(verified_roles, 'r') as f:
        roles = json.load(f)

    roles[str(ctx.guild.id)] = role.id
    with open(verified_roles, 'w') as f:
        json.dump(roles, f)   
    
    await ctx.response.send_message("Verified role set to " + role.name + " for server " + ctx.guild.name,ephemeral=True)
    
@tree.command(name="verify", description="Verifies your ownership of a Handshake name and sets your nickname.")
async def verify(ctx, domain:str):
    name_idna = domain.strip().rstrip("/").encode("idna")
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

# On reaction
@client.event
async def on_reaction_add(reaction, user):
    if user == client.user:
        return
    if not reaction.message.guild:
        return
    if user.bot:
        return
    if reaction.message.author != client.user:
        return
    if reaction.emoji != "👍":
        return
    
    print(reaction.message.id)
    # If it is within 15 minutes
    for faucet_message in faucet_messages:
        if faucet_message["id"] == reaction.message.id:
            if faucet_message["user"] == user.id and user.id != ADMINID:
                await reaction.message.channel.send("You can't approve your own gift")
                return
            
            # Verify the approver has the shaker role
            if not os.path.exists(verified_roles):
                with open(verified_roles, 'w') as f:
                    json.dump({}, f)

            with open(verified_roles, 'r') as f:
                roles = json.load(f)

            if str(reaction.message.guild.id) in roles:
                if roles[str(reaction.message.guild.id)] not in [role.id for role in user.roles]:
                    await reaction.message.channel.send("You don't have permission to approve this gift\nRun /verify to be eligible to approve gifts")
                    return
            else:
                await reaction.message.channel.send("You don't have permission to approve this gift\nRun /verify to be eligible to approve gifts")
                return

            if (datetime.datetime.now() - faucet_message["time"]).total_seconds() > 900:
                await reaction.message.channel.send("This gift has expired")
                return
            
            result = await send_domain(faucet_message["user"], faucet_message["email"])   
            receiver = await client.fetch_user(faucet_message["user"])
            await receiver.send(result)
            faucet_messages.remove(faucet_message)
            # Update message
            await reaction.message.edit(content="Approved by " + user.name)

            return


client.run(TOKEN)