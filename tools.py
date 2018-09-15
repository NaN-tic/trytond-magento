# encoding: utf-8
# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unicodedata
from decimal import Decimal

SRC_CHARS = u"""/*+?¿!&$[]{}`^<>=~%|\\"""

def unaccent(text):
    if not text:
        return ''
    text = text.lower()
    for c in range(len(SRC_CHARS)):
        text = text.replace(SRC_CHARS[c], '')
    text = text.replace('º', '. ')
    text = text.replace('ª', '. ')
    text = text.replace('  ', ' ')
    output = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore')
    return output.decode('utf-8')


def party_name(firstname, lastname):
    '''
    Return party name format
    '''
    if lastname:
        return '%s %s' % (firstname, lastname)
    return firstname


def remove_newlines(text):
    '''
    Remove new lines
    '''
    return ' '.join(text.splitlines())


def base_price_without_tax(price, rate, currency=None):
    '''
    From price with taxes and return price without tax
    :param price: total price
    :param rate: rate tax
    :param currency: currency object
    '''
    price = price / (1 + rate)
    precision = currency.digits if currency else 2
    return Decimal('{:.{prec}f}'.format(price, prec=precision))


def base_price_with_tax(price, rate, currency=None):
    '''
    From price without taxes and return with tax
    :param price: total price
    :param rate: rate tax
    :param currency: currency object
    '''
    price = price * (1 + rate)
    precision = currency.digits if currency else 2
    return Decimal('{:.{prec}f}'.format(price, prec=precision))
