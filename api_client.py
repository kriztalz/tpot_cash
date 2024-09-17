import httpx
import asyncio

class APIClient:
    BASE_URL = "https://tpot-tcg-backend.onrender.com/api"
    
    def __init__(self, config):
        self.config = config
        self.token = "idkjustregenme"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "br, gzip, deflate",
            "Referer": "https://tpot-tcg.com/",
            "Origin": "https://tpot-tcg.com",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }
        self.headers_bearer = self.headers.copy()
        self.headers_bearer["Authorization"] = f"Bearer {self.token}"

    async def get_bearer(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/login", headers=self.headers, json={
                    "username": self.config["user"]["username"],
                    "password": self.config["user"]["password"]
                })
                data = resp.json()
                self.token = data["token"]
                self.headers_bearer["Authorization"] = f"Bearer {self.token}"
                print("New token obtained")
        except Exception as e:
            print(f"Error getting bearer token: {e}")

    async def claim(self):
        try:
            data = {"username": self.config["user"]["username"]}
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/claim-teapot-reward", headers=self.headers_bearer, json=data)
            resp_data = resp.json()
            
            if 'reward' in resp_data:
                return {'wait_time': 0, 'balance': resp_data['balance'], 'cards': resp_data['cards']}
            elif resp_data == {'message': 'Token expired'}:
                print("Token expired. Getting new token...")
                await self.get_bearer()
                return None
            elif resp_data == {'message': 'Cannot claim reward yet'}:
                return await self.get_status()
            else:
                print(f"Unexpected response: {resp_data}")
                return {'wait_time': 60, 'balance': 0}
        except Exception as e:
            print(f"Error claiming reward: {e}")
            return {'wait_time': 60, 'balance': 0}

    async def get_status(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.BASE_URL}/teapot-status", headers=self.headers_bearer)
                data = resp.json()
                can_claim = data["can_claim"]
                if not can_claim:
                    return {'wait_time': data["seconds_until_next_reward"], 'balance': data.get('balance', 0)}
                return {'wait_time': 0, 'balance': data.get('balance', 0)}
        except Exception as e:
            print(f"Error getting status: {e}")
            return {'wait_time': 60, 'balance': 0}

    async def get_user_info(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.BASE_URL}/user/{self.config['user']['username']}", headers=self.headers_bearer)
            data = resp.json()
            return data['balance'], data['cards']
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None, None

    async def perform_special_action(self, card_number):
        action_map = {97: "action", 99: "hacker", 100: "aura"}
        action = action_map.get(card_number)
        if not action:
            print(f"No special action for card {card_number}")
            return
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/{action}", headers=self.headers_bearer, json={"username": self.config["user"]["username"]})
            print(resp.json())
        except Exception as e:
            print(f"Error performing special action for card {card_number}: {e}")

    async def get_market_listings(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.BASE_URL}/market/all", headers=self.headers_bearer)
                return resp.json()['entries']
        except Exception as e:
            print(f"Error getting market listings: {e}")
            return []

    async def buy_card(self, entry_id, quantity):
        try:
            data = {"entry_id": str(entry_id), "quantity": quantity}
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/market/buy", headers=self.headers_bearer, json=data)
                if resp.json() == {"message": "Purchase successful"}:
                    print(f"Successfully bought card (Entry ID: {entry_id}, Quantity: {quantity})")
                    return True
                else:
                    print(f"Failed to buy card: {resp.json()}")
                    return False
        except Exception as e:
            print(f"Error buying card: {e}")
            return False

    async def open_pack(self):
        try:
            data = {"username": self.config["user"]["username"]}
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/open-pack", headers=self.headers_bearer, json=data)
            resp_data = resp.json()
            print("Opened a pack:")
            for card in resp_data['new_cards']:
                print(f"- {card['name']} (#{card['number']}) {'(Holo)' if card['holo'] else ''}")
            return resp_data['balance'], resp_data['cards']
        except Exception as e:
            print(f"Error opening pack: {e}")
            return None, None

    async def get_card_price(self, entry_id):
        listings = await self.get_market_listings()
        listing = next((l for l in listings if l['id'] == entry_id), None)
        if listing:
            return listing['price']
        else:
            print(f"❌ Couldn't find price for entry ID: {entry_id}")
            return None

    # Add other API methods as needed