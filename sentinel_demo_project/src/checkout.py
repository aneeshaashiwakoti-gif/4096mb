from .payment import calculate_total

def process_checkout(cart):
    if not cart:
        return False
    amount = calculate_total(cart)
    # process payment logic
    return amount > 0
