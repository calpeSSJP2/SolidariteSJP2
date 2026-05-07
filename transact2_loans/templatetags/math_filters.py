from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def subtract(value, arg):
    try:
        return Decimal(value) - Decimal(arg)
    except:
        return value

@register.filter
def add(value, arg):
    try:
        return Decimal(value) + Decimal(arg)
    except:
        return value
