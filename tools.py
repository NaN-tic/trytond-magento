# encoding: utf-8
# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unicodedata
from decimal import Decimal

SRC_CHARS = u"""/*+?¿!&$[]{}`^<>=~%|\\"""

def unaccent(text):
    if not (isinstance(text, str) or isinstance(text, unicode)):
        return str(text)
    if isinstance(text, str):
        text = unicode(text, 'utf-8')
    text = text.lower()
    for c in xrange(len(SRC_CHARS)):
        text = text.replace(SRC_CHARS[c], '')
    text = text.replace(u'º', '. ')
    text = text.replace(u'ª', '. ')
    text = text.replace(u'  ', ' ')
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore')


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
    price = Decimal(price / (1 + rate))
    PRECISION = Decimal(str(10.0 ** - currency.digits if currency else 2))
    return price.quantize(PRECISION)


def base_price_with_tax(price, rate, currency=None):
    '''
    From price without taxes and return with tax
    :param price: total price
    :param rate: rate tax
    :param currency: currency object
    '''
    price = price * (1 + rate)
    PRECISION = Decimal(str(10.0 ** - currency.digits if currency else 2))
    return price.quantize(PRECISION)
