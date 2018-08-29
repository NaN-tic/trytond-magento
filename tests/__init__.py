# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
try:
    from trytond.modules.magento.tests.test_magento import suite
except ImportError:
    from .test_magento import suite

__all__ = ['suite']
