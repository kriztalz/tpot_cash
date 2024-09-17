import asyncio
import traceback
from config import CONFIG
from api_client import APIClient
from card_manager import CardManager
from modules.auto_complete_collection import auto_complete_collection
from modules.auto_pack_opener import auto_pack_opener
from modules.auto_trader import (
    auto_trader, calculate_cheapest_acquisition, get_trader_deals,
    buy_from_market, execute_trade_strategy, open_packs_strategy
)

async def main_loop():
    api_client = APIClient(CONFIG)
    card_manager = CardManager(api_client)

    await api_client.get_bearer()
    await card_manager.fetch_all_cards()
    
    while True:
        try:
            status = await api_client.claim()
            if status is None:
                print("🔄 Token refresh needed. Retrying...")
                continue
            if status['wait_time'] > 0:
                print(f"⏳ Gotta wait {status['wait_time']}s for next claim")
                await asyncio.sleep(status['wait_time'])
                continue

            balance, cards = await api_client.get_user_info()
            if balance is None or cards is None:
                print("❌ Couldn't get user info. Retrying...")
                continue
            
            print(f"💰 Balance: ${balance:.2f}")
            missing_cards = card_manager.check_missing_cards(cards)
            print(f"🃏 Missing: {missing_cards}")
            
            if not missing_cards:
                print("🎉 Collection complete! We're done here!")
                break

            for special_card in [97, 99, 100]:
                if special_card in missing_cards:
                    print(f"🔮 Trying to get special card {special_card}")
                    await api_client.perform_special_action(special_card)
            
            balance, cards = await api_client.get_user_info()
            
            # Plan actions for this cycle
            action = await plan_action(api_client, card_manager, cards, balance)
            
            if not action:
                print("Saving money for future actions. Waiting for next cycle...")
            else:
                print(f"📝 Strategy for this turn: {action['type'].capitalize()} for card {action['card']}")
                
                try:
                    if action['type'] == 'market':
                        success, balance, cards = await buy_from_market(api_client, action['card'], action['entry_id'], balance, cards)
                    elif action['type'] == 'trade':
                        success, balance, cards = await execute_trade_strategy(api_client, card_manager, action['deal'], balance, cards)
                    elif action['type'] == 'pack':
                        success, balance, cards = await open_packs_strategy(api_client, card_manager, action['card'], balance, cards)

                    if success:
                        print(f"✅ Action successful: {action['type']} for card {action['card']}")
                    else:
                        print(f"❌ Action failed: {action['type']} for card {action['card']}")
                except Exception as e:
                    print(f"😱 Error in {action['type']} for card {action['card']}: {str(e)}")
                    print("Traceback:")
                    traceback.print_exc()

            # Refresh user info after action
            balance, cards = await api_client.get_user_info()
            if balance is None or cards is None:
                print("❌ Couldn't get updated user info. Continuing...")
            else:
                print(f"💰 Updated Balance: ${balance:.2f}")
                missing_cards = card_manager.check_missing_cards(cards)
                print(f"🃏 Still Missing: {missing_cards}")

            print("😴 Taking a breather...")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"😱 Oops! Something went wrong in main loop: {str(e)}")
            print("Traceback:")
            traceback.print_exc()
            print("🛌 Gonna nap for a minute...")
            await asyncio.sleep(60)

async def plan_action(api_client, card_manager, cards, balance):
    missing_cards = card_manager.check_missing_cards(cards)
    deals = await get_trader_deals(api_client)
    market_listings = await api_client.get_market_listings()
    
    actions = []

    for card_number in missing_cards:
        if 96 <= card_number <= 100:
            continue  # Skip special cards

        cost, method = await calculate_cheapest_acquisition(api_client, card_manager, card_number, deals, market_listings, cards, balance)
        
        action = {
            'type': method,
            'card': card_number,
            'cost': cost
        }
        
        if method == 'market':
            listing = next((l for l in market_listings if l['card']['number'] == card_number), None)
            if listing:
                action['entry_id'] = listing['id']
            else:
                continue
        elif method == 'trade':
            deal = next((d for d in deals if d['holo_card']['number'] == card_number), None)
            if deal:
                action['deal'] = deal
            else:
                continue
        
        actions.append(action)

    # Sort actions by cost
    actions.sort(key=lambda x: x['cost'])

    if actions:
        cheapest_action = actions[0]
        pack_price = api_client.config["modules"]["auto_pack_opener"]["pack_price"]

        if cheapest_action['type'] == 'pack' and balance >= pack_price:
            print(f"Best approach: Open packs for card {cheapest_action['card']}")
            print(f"  Estimated total cost: ${cheapest_action['cost']:.2f}")
            print(f"  Opening a pack for ${pack_price:.2f}")
            return {'type': 'pack', 'card': cheapest_action['card'], 'cost': pack_price}
        elif cheapest_action['cost'] <= balance:
            print(f"Best approach to get card {cheapest_action['card']}:")
            print(f"  Method: {cheapest_action['type']}")
            print(f"  Estimated cost: ${cheapest_action['cost']:.2f}")
            return cheapest_action
        else:
            next_target_cost = cheapest_action['cost']
            print(f"Saving up for next cheapest action:")
            print(f"  Card: {cheapest_action['card']}")
            print(f"  Method: {cheapest_action['type']}")
            print(f"  Target cost: ${next_target_cost:.2f}")
            print(f"  Current balance: ${balance:.2f}")
            print(f"  Need to save: ${next_target_cost - balance:.2f}")
            return None  # Return None to indicate we're saving money
    else:
        print("No viable actions found for any missing cards.")
        return None

    return None  # If we reach here, we're saving money

if __name__ == "__main__":
    print(f"🚀 Kicking off bot for {CONFIG['user']['username']}")
    asyncio.run(main_loop())