import pytest
from src.order import create_order

def test_create_order():
    assert create_order([{'price': 10}]) == "Order created"
