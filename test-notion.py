from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

import os
from typing import List

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
notion = Client(auth=NOTION_TOKEN)


users = notion.users.list()
for user in users['results']:
    print(user['id'], user['name'])
print("Total users:", len(users['results']))