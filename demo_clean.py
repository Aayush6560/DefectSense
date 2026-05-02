"""Simple, clean utility module demonstrating good code practices."""


def calculate_sum(numbers):
    """Calculate the sum of a list of numbers.
    
    Args:
        numbers: List of numeric values.
    
    Returns:
        The sum total.
    """
    total = 0
    for num in numbers:
        total += num
    return total


def format_currency(amount, currency="USD"):
    """Format a number as currency.
    
    Args:
        amount: Numeric value to format.
        currency: Currency code (default USD).
    
    Returns:
        Formatted currency string.
    """
    return f"{currency} ${amount:.2f}"


def validate_email(email):
    """Check if an email contains @ symbol.
    
    Args:
        email: Email string to validate.
    
    Returns:
        True if email contains @, False otherwise.
    """
    return "@" in email
