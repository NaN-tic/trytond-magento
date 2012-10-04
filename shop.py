#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval, datetime_strftime
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval, Bool

import logging
import threading

class SaleShop(ModelSQL, ModelView):
    _name = 'sale.shop'

    magento_reference = fields.Boolean('Magento Reference',
        help='Use Magento Reference (Increment) in sale name')
    magento_website = fields.Many2One('magento.website', 'Magento Website')
    magento_status = fields.One2Many('magento.shop.status', 'shop', 'Status')
    magento_payments = fields.One2Many('magento.shop.payment', 'shop', 'Payments')
    magento_status_paid = fields.Char('Paid',
        states={
            'required': Eval('esale_shop_app') == 'magento',
        },help='Status for paid orders (invoice)')
    magento_notify_paid = fields.Boolean('Notify Paid',
        help='Magento notification')
    magento_status_delivered = fields.Char('Delivered', 
        states={
            'required': Eval('esale_shop_app') == 'magento',
        }, help='Status for delivered (picking)')
    magento_notify_delivered = fields.Boolean('Notify Delivered', 
        help='Magento notification')
    magento_status_paid_delivered = fields.Char('Paid/Delivered', 
        states={
            'required': Eval('esale_shop_app') == 'magento',
        }, help='Status for paid and delivered')
    magento_notify_paid_delivered = fields.Boolean('Notify Paid/Delivered',
        help='Magento notification')
    magento_status_paidinweb = fields.Char('Paid in web', 
        states={
            'required': Eval('esale_shop_app') == 'magento',
        }, help='Status for paid in  web')
    magento_notify_paidinweb = fields.Boolean('Notify Paid in web',
        help='Magento notification')
    magento_status_paidinweb_delivered = fields.Char('Paid in web/Delivered',
        states={
            'required': Eval('esale_shop_app') == 'magento',
        }, help='Status for paid in web and delivered')
    magento_notify_paidinweb_delivered = fields.Boolean('Notify Paid in web/Delivered',
        help='Magento notification')
    magento_status_cancel = fields.Char('Cancel',
        states={
            'required': Eval('esale_shop_app') == 'magento',
        }, help='Status for cancel orders')
    magento_notify_cancel = fields.Boolean('Notify Cancel',
        help='Magento notification')
    magento_price_global = fields.Boolean('Price Global',
        help='This sale use in global prices (by multistore)')

    def __init__(self):
        super(SaleShop, self).__init__()
        self._error_messages.update({
            'magento_product': 'Install Magento Product module to export ' \
                'products to Magento',
        })

    def default_magento_reference(self):
        return True

    def get_shop_app(self):
        '''Get Shop APP (tryton, magento, prestashop,...)'''
        res = super(SaleShop, self).get_shop_app()
        res.append(('magento','Magento'))
        return res

    def import_orders_magento(self, shop):
        """Import Orders from Magento APP
        :param shop: Obj
        """
        self.raise_user_error('magento_product')

    def export_status_magento(self, shop):
        """Export Status Orders to Magento
        :param shop: Obj
        """
        self.raise_user_error('magento_product')
    
    def export_products_magento(self, shop):
        """Export Products to Magento
        This option is available in magento_product module
        """
        self.raise_user_error('magento_product')

    def export_prices_magento(self, shop):
        """Export Prices to Magento
        This option is available in magento_product module
        """
        self.raise_user_error('magento_product')

    def export_stocks_magento(self, shop):
        """Export Stocks to Magento
        This option is available in magento_product module
        """
        self.raise_user_error('magento_product')

    def export_images_magento(self, shop):
        """Export Images to Magento
        This option is available in magento_product module
        """
        self.raise_user_error('magento_product')

SaleShop()
