"""
Quantity tracking service.
Manages remaining winding quantity/count.
"""

QUANTITY_FILE = 'data/quantitytxt'

def read_quantity():
    """Read current winding quantity from file.
    Returns: int quantity or 0 if not found
    """
    try:
        with open(QUANTITY_FILE, 'r') as f:
            quantity = int(f.read().strip())
            return quantity
    except OSError:
        # File doesn't exist, return default
        return 0
    except Exception as e:
        print(f"Error reading quantity: {e}")
        return 0

def write_quantity(quantity):
    """Write winding quantity to file.
    Args:
        quantity: int number of windings remaining
    Returns: bool success
    """
    try:
        with open(QUANTITY_FILE, 'w') as f:
            f.write(str(quantity))
        return True
    except Exception as e:
        print(f"Error writing quantity: {e}")
        return False
