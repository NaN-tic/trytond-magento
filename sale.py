# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.modules.product import price_digits
from trytond.config import config as config_

__all__ = ['Sale', 'SaleLine']
DISCOUNT_DIGITS = config_.getint('product', 'discount_decimal', default=4)


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def convert_magento_status(self):
        '''Return Magento state'''
        states = dict((s.state, {
            'code': s.code, 'notify': s.notify, 'cancel': s.cancel or None})
            for s in self.shop.esale_states)

        status, notify, cancel = None, None, None
        if self.invoice_state == 'paid':
            status = states['paid']['code']
            notify = states['paid']['notify']
            cancel = states['paid']['cancel']
        elif self.shipment_state == 'sent':
            status = states['shipment']['code']
            notify = states['shipment']['notify']
            cancel = states['shipment']['cancel']
        elif (self.invoice_state == 'paid') and (self.shipment_state == 'sent'):
            status = states['paid-shipment']['code']
            notify = states['paid-shipment']['notify']
            cancel = states['paid-shipment']['cancel']
        elif states.get(self.state):
            status = states[self.state]['code']
            notify = states[self.state]['notify']
            cancel = states[self.state]['cancel']
        return status, notify, cancel

    def esale_sale_export_csv(self):
        vals = super(Sale, self).esale_sale_export_csv()

        if self.shop.esale_shop_app != 'magento':
            return vals

        status, _, _ = self.convert_magento_status()
        if status:
            vals['state'] = status
        return vals


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    discount_amount = fields.Numeric('Discount Amount', digits=price_digits)
    discount_percentage = fields.Numeric('Discount Percentage', digits=(16, DISCOUNT_DIGITS))

    @staticmethod
    def default_discount_amount():
        return 0

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['discount_amount'] = None
        default['discount_percentage'] = None
        return super(SaleLine, cls).copy(lines, default=default)
