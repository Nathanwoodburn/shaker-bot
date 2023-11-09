import os
from dotenv import load_dotenv
import dns.resolver
import dns.exception
import dns.message
import discord
import json

load_dotenv()

resolver = dns.resolver.Resolver()
serverIP = os.getenv('DNS_SERVER')
resolver.nameservers = [serverIP]
resolver.port = int(os.getenv('DNS_PORT'))

LOCAL = False
if os.getenv('LOCAL') == "True":
    LOCAL = True

verified_roles = '/data/roles.json'

if LOCAL:
    verified_roles = 'roles.json'


def check_name(user_id: int, name: str) -> bool:
    try:
        answer = resolver.resolve('_shaker._auth.' + name, 'TXT')
        for rrset in answer.response.answer:
            parts = rrset.to_text().split(" ")
            if str(user_id) in parts[-1]:
                return True
    except dns.exception.DNSException as e:
        print("DNS Exception")
        print(e)
        pass
    return False

async def handle_role(member: discord.Member, shouldHaveRole: bool):
    with open(verified_roles, 'r') as f:
        roles = json.load(f)

    key = str(member.guild.id)

    if not key in roles:
        return

    role_id = roles[key]

    if role_id:
        guild = member.guild
        role = guild.get_role(role_id)
        if role and shouldHaveRole and not role in member.roles:
            await member.add_roles(role)
        elif role and not shouldHaveRole and role in member.roles:
            await member.remove_roles(role)


async def check_member(member: discord.Member) -> bool:
    if member.display_name[-1] != "/":
        await handle_role(member, False)
        return

    if check_name(member.id, member.display_name[0:-1]):
        await handle_role(member, True)
        return True
    
    try:
        await member.edit(nick=member.display_name[0:-1])
    except Exception as e:
        print(e)
    await handle_role(member, False)
    return False