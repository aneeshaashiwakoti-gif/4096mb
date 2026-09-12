from .checkout import process_checkout

def create_order(cart):
    success = process_checkout(cart)
    if success:
        return "Order created"
    return "Checkout failed"
