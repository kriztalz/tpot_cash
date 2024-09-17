async def auto_pack_opener(api_client, balance, cards):
    pack_price = api_client.config["modules"]["auto_pack_opener"]["pack_price"]
    min_balance = api_client.config["modules"]["auto_pack_opener"]["min_balance"]
    
    if balance - pack_price >= min_balance:
        print(f"Opening a pack for ${pack_price}...")
        new_balance, new_cards = await api_client.open_pack()
        if new_balance is not None and new_cards is not None:
            balance = new_balance
            cards = new_cards
            print(f"New balance: ${balance:.2f}")
        else:
            print("Failed to open pack.")
    else:
        print(f"Not opening pack to maintain minimum balance. Current balance: ${balance:.2f}")
    
    return balance, cards