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
        return "Your email is invalid"
    
    response = requests.post("https://faucet.woodburn.au/api?email=" + email+"&name="+str(user) + "&key=" + os.getenv('FAUCET_KEY'))
    print(response)
    print(response.text)
    response = response.json()
    if response['success']:
        return "Congratulations! We've sent you a domain to your email"
    else:
        return "Sorry, something went wrong. Please try again later\n" + response['error']
    
