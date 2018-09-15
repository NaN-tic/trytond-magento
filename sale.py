# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['Sale']


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def convert_magento_status(self):
        '''Return Magento state'''
        states = dict((s.state, {'code': s.code, 'notify': s.notify}) \
                for s in self.shop.esale_states)

        status = None
        notify = None
        cancel = None
        if self.state == 'cancel':
            status = states['cancel']['code']
            notify = states['cancel']['notify']
            cancel = True
        if self.invoice_state == 'paid':
            status = states['paid']['code']
            notify = states['paid']['notify']
        if self.shipment_state == 'sent':
            status = states['shipment']['code']
            notify = states['shipment']['notify']
        if (self.invoice_state == 'paid') and (self.shipment_state == 'sent'):
            status = states['paid-shipment']['code']
            notify = states['paid-shipment']['notify']
        return status, notify, cancel

    def esale_sale_export_csv(self):
        vals = super(Sale, self).esale_sale_export_csv()

        if self.shop.esale_shop_app != 'magento':
            return vals

        status, _, _ = self.convert_magento_status()
        if status:
            vals['state'] = status
        return vals
