import pytest
from src.checkout import process_checkout

def test_process_checkout_empty():
    assert process_checkout([]) == False

def test_process_checkout_valid():
    assert process_checkout([{'price': 10}]) == True
