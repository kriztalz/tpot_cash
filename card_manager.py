import httpx

class CardManager:
    def __init__(self, api_client):
        self.api_client = api_client
        self.all_cards = []

    async def fetch_all_cards(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.api_client.BASE_URL}/cards", headers=self.api_client.headers_bearer)
                data = resp.json()
                self.all_cards = data.get('cards', [])
            print(f"Fetched {len(self.all_cards)} cards")
        except Exception as e:
            print(f"Error fetching all cards: {e}")

    def check_missing_cards(self, cards):
        missing = []
        for i in range(1, 101):
            if str(i) not in cards or cards[str(i)] == 0:
                missing.append(i)
        return missing

    def calculate_card_acquisition_efficiency(self, card_number, market_price):
        pack_price = self.api_client.config["modules"]["auto_pack_opener"]["pack_price"]
        
        if card_number <= 80:  # Regular card
            prob_in_pack = 1 - (79/80)**5  # Probability of getting at least one in 5 draws
        else:  # Holo card
            prob_in_pack = 0.2 * (1/15)  # 20% chance of holo, then 1/15 chance of specific holo
        
        expected_packs_needed = 1 / prob_in_pack
        expected_cost_from_packs = expected_packs_needed * pack_price
        
        if expected_cost_from_packs < market_price:
            return "pack", expected_cost_from_packs
        else:
            return "market", market_price