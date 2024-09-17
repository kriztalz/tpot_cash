async def auto_complete_collection(api_client, card_manager, balance, cards):
    if api_client.config["modules"]["auto_complete_collection"]["enabled"]:
        print("Attempting to complete collection...")
        all_card_numbers = set(range(1, 101))
        owned_cards = set(map(int, cards.keys()))
        missing_cards = all_card_numbers - owned_cards
        
        if missing_cards:
            print(f"Missing cards: {sorted(missing_cards)}")
            listings = await api_client.get_market_listings()
            for card_number in missing_cards:
                cheapest = min((l for l in listings if l['card'].get('number') == card_number), key=lambda x: x['price'], default=None)
                if cheapest:
                    acquisition_method, expected_cost = card_manager.calculate_card_acquisition_efficiency(card_number, cheapest['price'])
                    if acquisition_method == "market" and expected_cost <= balance:
                        if await api_client.buy_card(cheapest['id'], 1):
                            balance -= cheapest['price']
                            cards[str(card_number)] = cards.get(str(card_number), 0) + 1
                            print(f"Bought missing card {card_number} for ${cheapest['price']}")
                            # Update balance and cards after buying
                            balance, cards = await api_client.get_user_info()
                    elif acquisition_method == "pack":
                        print(f"It's more efficient to get card {card_number} through packs. Expected cost: ${expected_cost:.2f}")
                        # The auto_pack_opener module will handle opening packs
    return balance, cards