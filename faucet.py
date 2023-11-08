import os
from dotenv import load_dotenv
import discord
from discord import app_commands
import json
from email_validator import validate_email, EmailNotValidError
import requests

async def send_domain(user, email):
    try:
        emailinfo = validate_email(email, check_deliverability=False)
        email = emailinfo.normalized
    except EmailNotValidError as e:
        await user.send("Your email is invalid")
        return
    
    response = requests.post("https://faucet.woodburn.au/api?email=" + email+"&name="+user.name + "&key=" + os.getenv('FAUCET_KEY'))
    response = response.json()
    if response['success']:
        await user.send("Congratulations! We've sent you a domain to your email")
    else:
        await user.send("Sorry, something went wrong. Please try again later")
        await user.send(response['error'])
    
