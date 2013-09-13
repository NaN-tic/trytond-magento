#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from decimal import Decimal

import logging
import threading
import datetime
import unicodedata

from magento import *

__all__ = ['SaleShop']
__metaclass__ = PoolMeta

PRODUCT_TYPE_OUT_ORDER_LINE = ['configurable']
SRC_CHARS = u""".'"()/*-+?¿!&$[]{}@#`'^:;<>=~%,|\\"""
DST_CHARS = u""""""

def unaccent(text):
    if not (isinstance(text, str) or isinstance(text, unicode)):
        return str(text)
    if isinstance(text, str):
        text = unicode(text, 'utf-8')
    text = text.lower()
    for c in xrange(len(SRC_CHARS)):
        if c >= len(DST_CHARS):
            break
        text = text.replace(SRC_CHARS[c], DST_CHARS[c])
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore')

def party_name(firstname, lastname):
    """
    Return party name format
    """
    return '%s %s' % (firstname, lastname)

def remove_newlines(text):
    return ' '.join(text.splitlines())


class SaleShop:
    __name__ = 'sale.shop'
    magento_website = fields.Many2One('magento.website', 'Magento Website', 
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(SaleShop, cls).__setup__()
        cls._error_messages.update({
            'magento_product': 'Install Magento Product module to export ' \
                'products to Magento',
            'magento_error_get_orders': ('Magento "%s". ' \
                'Error connection or get earlier date: "%s".'),
        })

    @staticmethod
    def default_magento_reference():
        return True

    @classmethod
    def get_shop_app(cls):
        '''Get Shop APP (tryton, magento, prestashop,...)'''
        res = super(SaleShop, cls).get_shop_app()
        res.append(('magento','Magento'))
        return res

    def import_orders_magento(self, shop, ofilter=None):
        """Import Orders from Magento APP
        :param shop: Obj
        :param ofilter: dict
        """
        pool = Pool()
        MagentoExternalReferential = pool.get('magento.external.referential')
        SaleShop = pool.get('sale.shop')

        mgnapp = shop.magento_website.magento_app
        now = datetime.datetime.now()

        if not ofilter:
            from_time = SaleShop.datetime_to_str(shop.esale_from_orders or now)
            creted_filter = {'from':from_time}
            if shop.esale_to_orders:
                to_time = SaleShop.datetime_to_str(shop.esale_to_orders)
                creted_filter['to'] = to_time
            ofilter = {'created_at':creted_filter}

        mgn_store = MagentoExternalReferential.get_try2mgn(mgnapp, 
            'magento.website', shop.magento_website.id)
        ofilter['store_id'] = mgn_store.mgn_id

        with Order(mgnapp.uri, mgnapp.username, mgnapp.password) as order_api:
            try:
                orders = order_api.list(ofilter)
                logging.getLogger('magento sale').info(
                    'Magento %s. Import orders %s.' % (mgnapp.name, ofilter))
            except:
                logging.getLogger('magento sale').error(
                    'Magento %s. Error connection or get earlier date: %s.' % (
                    mgnapp.name, ofilter))
                self.raise_user_error('magento_error_get_orders', (
                    mgnapp.name, ofilter))

        #~ Update date last import
        self.write([shop], {'esale_from_orders': now, 'esale_to_orders': None})

        if not orders:
            logging.getLogger('magento sale').info(
                'Magento website %s. Not orders to import.' % (shop.name))
        else:
            logging.getLogger('magento order').info(
                'Magento website %s. Start import %s orders.' % (
                shop.name, len(orders)))
            db_name = Transaction().cursor.dbname
            thread1 = threading.Thread(target=self.import_orders_magento_thread, 
                args=(db_name, Transaction().user, shop.id, orders,))
            thread1.start()

    @classmethod
    def mgn2order_values(self, shop, values):
        """
        Convert magento values to sale
        :param shop: obj
        :param values: dict
        return dict
        """
        comment = values.get('customer_note')
        if values.get('gift_message'):
            comment = '%s\n%s' % (values.get('customer_note'), values.get('gift_message'))

        status_history = []
        if values.get('status_history'):
            for history in values['status_history']:
                status_history.append('%s - %s - %s' % (
                    str(history['created_at']), 
                    str(history['status']), 
                    str(unicode(history['comment']).encode('utf-8')),
                    ))

        payment_type = None
        if 'method' in values.get('payment'):
            payment_type = values.get('payment')['method']

        vals = {
            'reference_external': values.get('increment_id'),
            'sale_date': values.get('created_at')[:10],
            'carrier': values.get('shipping_method'),
            'payment': payment_type,
            'currency': values.get('order_currency_code'),
            'comment': comment,
            'status': values['status_history'][0]['status'],
            'status_history': '\n'.join(status_history),
            'external_untaxed_amount': Decimal(values.get('base_subtotal')),
            'external_tax_amount': Decimal(values.get('base_tax_amount')),
            'external_total_amount': Decimal(values.get('base_grand_total')),
            'shipping_cost': Decimal(values.get('base_shipping_amount')),
            'shipping_note': values.get('shipping_description'),
            'discount': Decimal(values.get('discount_amount'))
            }

        return vals

    @classmethod
    def mgn2lines_values(self, shop, values):
        """
        Convert magento values to sale lines
        :param shop: obj
        :param values: dict
        return list(dict)
        """
        app = shop.magento_website.magento_app
        vals = []
        for item in values.get('items'):
            print item
            if item['product_type'] not in PRODUCT_TYPE_OUT_ORDER_LINE:
                values = {
                    'quantity': Decimal(item.get('qty_ordered')),
                    'description': item.get('description') or item.get('name'),
                    'unit_price': Decimal(item.get('price')),
                    'note': item.get('gift_message'),
                    }
                if app.product_options and item.get('sku'):
                    for sku in item['sku'].split('-'):
                        values['product'] = sku
                        vals.append(values)
                else:
                    values['product'] = item.get('sku')
                    vals.append(values)
        return vals

    def mgn2extralines_values(self, shop, values):
        """
        Convert magento values to extra sale lines
        Super this method if in your Magento there are extra lines to create
        in sale order
        :param shop: obj
        :param values: dict
        return list(dict)
        """
        return []

    @classmethod
    def mgn2party_values(self, shop, values):
        """
        Convert magento values to party
        :param shop: obj
        :param values: dict
        return dict
        """
        firstname = values.get('customer_firstname')
        lastname = values.get('customer_lastname')
        billing = values.get('billing_address')
        shipping = values.get('shipping_address')

        vals = {
            'name': unaccent(billing.get('company') and 
                billing.get('company').title() or 
                party_name(firstname, lastname)).title(),
            'esale_email': values.get('customer_email'),
            }

        vals['vat_number'] = values.get('customer_taxvat')
        if billing:
            vals['vat_country'] = billing.get('country_id')
        else:
            vals['vat_country'] = shipping.get('country_id')
        return vals

    @classmethod
    def mgn2invoice_values(self, shop, values):
        """
        Convert magento values to invoice address
        :param shop: obj
        :param values: dict
        return dict
        """
        billing = values.get('billing_address')

        name = party_name(values.get('customer_firstname'), 
            values.get('customer_lastname'))
        if billing.get('firstname'):
            name = party_name(billing.get('firstname'), 
                billing.get('lastname'))

        vals = {
            'name': unaccent(name).title(),
            'street': remove_newlines(unaccent(billing.get('street')).title()),
            'zip': billing.get('postcode'),
            'city': unaccent(billing.get('city')).title(),
            'country': billing.get('country_id'),
            'phone': billing.get('telephone'),
            'email': billing.get('email'),
            'fax': billing.get('fax'),
            'invoice': True,
            }
        return vals

    @classmethod
    def mgn2shipment_values(self, shop, values):
        """
        Convert magento values to shipment address
        :param shop: obj
        :param values: dict
        return dict
        """
        shipment = values.get('shipping_address')

        name = party_name(values.get('customer_firstname'), 
            values.get('customer_lastname'))
        if shipment.get('firstname'):
            name = party_name(shipment.get('firstname'), shipment.get('lastname'))

        vals = {
            'name': unaccent(name).title(),
            'street': remove_newlines(unaccent(shipment.get('street')).title()),
            'zip': shipment.get('postcode'),
            'city': unaccent(shipment.get('city')).title(),
            'country': shipment.get('country_id'),
            'phone': shipment.get('telephone'),
            'email': shipment.get('email'),
            'fax': shipment.get('fax'),
            'delivery': True,
            }
        return vals

    def import_orders_magento_thread(self, db_name, user, shop, orders):
        """Create orders from Magento APP
        :param db_name: str
        :param user: int
        :param shop: int
        :param orders: list
        """
        with Transaction().start(db_name, user) as transaction:
            pool = Pool()
            MagentoExternalReferential = pool.get('magento.external.referential')
            SaleShop = pool.get('sale.shop')
            Sale = pool.get('sale.sale')

            sale_shop = SaleShop.browse([shop])[0]
            mgnapp = sale_shop.magento_website.magento_app

            with Order(mgnapp.uri, mgnapp.username, mgnapp.password) as order_api:
                for order in orders:
                    order_id = order['order_id']
                    reference = order['increment_id']

                    orders = Sale.search([
                        ('reference_external', '=', reference),
                        ('shop', '=', sale_shop),
                        ])

                    if orders:
                        logging.getLogger('magento sale').warning(
                            'Magento website %s. Order %s exist (ID %s). Not imported.' % (
                            sale_shop.name, reference, orders[0].id))
                        continue

                    #Get details Magento order
                    values = order_api.info(reference)

                    #Convert Magento order to dict
                    sale_values = self.mgn2order_values(sale_shop, values)
                    lines_values = self.mgn2lines_values(sale_shop, values)
                    extralines_values = self.mgn2extralines_values(sale_shop, values)
                    party_values = self.mgn2party_values(sale_shop, values)
                    invoice_values = self.mgn2invoice_values(sale_shop, values)
                    shipment_values = self.mgn2shipment_values(sale_shop, values)

                    #Create order, lines, party and address
                    Sale.create_external_order(sale_shop, sale_values, 
                        lines_values, extralines_values, party_values, 
                        invoice_values, shipment_values)
                    Transaction().cursor.commit()

            logging.getLogger('magento order').info(
                'Magento website %s. End import orders.' % (sale_shop.name))

    def export_status_magento(self, shop):
        """Export Status Orders to Magento
        :param shop: Obj
        """
        #TODO
        pass

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
