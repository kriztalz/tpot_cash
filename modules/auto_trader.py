import httpx
from modules.auto_pack_opener import auto_pack_opener

async def auto_trader(api_client, card_manager, cards, balance):
    if not api_client.config["modules"]["auto_trader"]["enabled"]:
        return False, balance, cards, None

    missing_cards = card_manager.check_missing_cards(cards)
    deals = await get_trader_deals(api_client)
    market_listings = await api_client.get_market_listings()

    cheapest_option = None
    cheapest_cost = float('inf')
    market_cheaper_than_packs = False

    for card_number in missing_cards:
        if 96 <= card_number <= 100:
            continue

        acquisition_cost, method = await calculate_cheapest_acquisition(api_client, card_manager, card_number, deals, market_listings, cards, balance)
        
        if acquisition_cost < cheapest_cost:
            cheapest_cost = acquisition_cost
            cheapest_option = (card_number, method)
            market_cheaper_than_packs = (method == "market")

    if cheapest_option is None or cheapest_cost > balance:
        print(f"💸 No affordable cards. Cheapest: ${cheapest_cost:.2f}, Balance: ${balance:.2f}")
        return False, balance, cards, market_cheaper_than_packs

    card_number, method = cheapest_option
    print(f"🎯 Going for card {card_number} via {method} (${cheapest_cost:.2f})")
    
    if method == "trade":
        deal = next(d for d in deals if d['holo_card']['number'] == card_number)
        balance, cards, acquired = await execute_trade_strategy(api_client, card_manager, deal, balance, cards)
    elif method == "market":
        listing = next(l for l in market_listings if l['card']['number'] == card_number)
        balance, cards, acquired = await buy_from_market(api_client, card_number, listing['id'], balance, cards)
    else:
        balance, cards, acquired = await open_packs_strategy(api_client, card_manager, card_number, balance, cards)

    if acquired:
        print(f"✅ Snagged card {card_number}")
        return True, balance, cards, market_cheaper_than_packs

    print(f"❌ Couldn't get card {card_number}")
    return False, balance, cards, market_cheaper_than_packs

async def calculate_cheapest_acquisition(api_client, card_manager, card_number, deals, market_listings, cards, balance):
    deal = next((d for d in deals if d['holo_card']['number'] == card_number), None)
    market_listing = next((l for l in market_listings if l['card']['number'] == card_number), None)

    trade_cost = calculate_trade_cost(deal, cards, market_listings) if deal else float('inf')
    market_cost = market_listing['price'] if market_listing else float('inf')
    pack_cost = card_manager.calculate_card_acquisition_efficiency(card_number, float('inf'))[1]

    costs = [
        (trade_cost, "trade"),
        (market_cost, "market"),
        (pack_cost, "pack")
    ]

    min_cost, method = min(costs, key=lambda x: x[0])
    return min_cost, method

def calculate_trade_cost(deal, cards, market_listings):
    if not deal:
        return float('inf')
    
    total_cost = 0
    for card_data in deal['regular_cards']:
        card_number = str(card_data['card']['number'])
        required_quantity = card_data['quantity']
        owned_quantity = cards.get(card_number, 0)
        if owned_quantity < required_quantity:
            needed_quantity = required_quantity - owned_quantity
            cheapest_listing = min((l for l in market_listings if l['card']['number'] == int(card_number)), key=lambda x: x['price'], default=None)
            if cheapest_listing:
                total_cost += cheapest_listing['price'] * needed_quantity
            else:
                return float('inf')
    return total_cost

async def execute_trade_strategy(api_client, card_manager, deal, balance, cards):
    needed_cards = get_needed_cards(deal, cards)
    for card_number, quantity in needed_cards.items():
        balance, cards, success = await buy_from_market(api_client, int(card_number), None, balance, cards, quantity)
        if not success:
            print(f"❌ Couldn't buy cards for trade. Bailing...")
            return balance, cards, False

    if await execute_trade(api_client, deal['id']):
        holo_card_number = str(deal['holo_card']['number'])
        cards[holo_card_number] = cards.get(holo_card_number, 0) + 1
        for card_data in deal['regular_cards']:
            card_number = str(card_data['card']['number'])
            cards[card_number] -= card_data['quantity']
        print(f"🔄 Traded for card {holo_card_number}")
        return balance, cards, True
    return balance, cards, False

async def buy_from_market(api_client, card_number, entry_id, balance, cards, quantity=1):
    if entry_id is None:
        listings = await api_client.get_market_listings()
        cheapest = min((l for l in listings if l['card']['number'] == card_number), key=lambda x: x['price'], default=None)
        if not cheapest:
            print(f"❌ Card {card_number} not in market")
            return balance, cards, False
        entry_id = cheapest['id']
    
    card_price = await api_client.get_card_price(entry_id)
    if card_price is None:
        return balance, cards, False

    success = await api_client.buy_card(entry_id, quantity)
    if success:
        total_cost = card_price * quantity
        balance -= total_cost
        cards[str(card_number)] = cards.get(str(card_number), 0) + quantity
        print(f"💰 Bought {quantity} of card {card_number} for ${card_price} each. Total: ${total_cost:.2f}")
        new_balance, new_cards = await api_client.get_user_info()
        if new_balance is not None and new_cards is not None:
            balance, cards = new_balance, new_cards
        return balance, cards, True
    return balance, cards, False

async def open_packs_strategy(api_client, card_manager, target_card_number, balance, cards):
    initial_balance = balance
    packs_opened = 0
    while balance >= api_client.config["modules"]["auto_pack_opener"]["pack_price"]:
        new_balance, new_cards = await auto_pack_opener(api_client, balance, cards)
        if new_balance is None or new_cards is None:
            print("❌ Pack opening failed")
            break
        balance = new_balance
        cards = new_cards
        packs_opened += 1
        if target_card_number is not None:
            if str(target_card_number) in cards and cards[str(target_card_number)] > 0:
                print(f"✅ Got card {target_card_number} after {packs_opened} packs")
                return True, balance, cards
        else:
            print(f"Opened {packs_opened} pack(s)")
            return True, balance, cards
    if target_card_number is not None:
        print(f"❌ Didn't get card {target_card_number} after {packs_opened} packs")
    else:
        print(f"Opened {packs_opened} pack(s)")
    return packs_opened > 0, balance, cards

async def get_trader_deals(api_client):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{api_client.BASE_URL}/trader/deals", headers=api_client.headers_bearer)
        if resp.status_code == 200:
            return resp.json()['deals']
        else:
            print(f"❌ Couldn't get trader deals: {resp.json()}")
            return []
    except Exception as e:
        print(f"❌ Error getting trader deals: {e}")
        return []

async def execute_trade(api_client, deal_id):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{api_client.BASE_URL}/trader/trade", headers=api_client.headers_bearer, json={"deal_id": deal_id})
        if resp.status_code == 200:
            print(f"✅ Trade executed for deal ID: {deal_id}")
            return True
        else:
            print(f"❌ Trade failed: {resp.json()}")
            return False
    except Exception as e:
        print(f"❌ Error executing trade: {e}")
        return False

def get_needed_cards(deal, cards):
    needed_cards = {}
    for card_data in deal['regular_cards']:
        card_number = str(card_data['card']['number'])
        required_quantity = card_data['quantity']
        if cards.get(card_number, 0) < required_quantity:
            needed_quantity = required_quantity - cards.get(card_number, 0)
            needed_cards[card_number] = needed_quantity
    return needed_cards

async def refresh_trader_deals(api_client):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{api_client.BASE_URL}/trader/refresh", headers=api_client.headers_bearer)
        if resp.status_code == 200:
            return resp.json()['deals']
        else:
            print(f"❌ Couldn't refresh trader deals: {resp.json()}")
            return None
    except Exception as e:
        print(f"❌ Error refreshing trader deals: {e}")
        return None