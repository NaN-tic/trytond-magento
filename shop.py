# encoding: utf-8
# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.modules.magento.tools import unaccent, party_name, \
    remove_newlines, base_price_without_tax

from decimal import Decimal

import logging
import threading
import datetime

from magento import *

__all__ = ['SaleShop']
__metaclass__ = PoolMeta

PRODUCT_TYPE_OUT_ORDER_LINE = ['configurable']


class SaleShop:
    __name__ = 'sale.shop'
    magento_website = fields.Many2One('magento.website', 'Magento Website',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(SaleShop, cls).__setup__()
        cls._error_messages.update({
            'magento_product': 'Install Magento Product module to export '
                'products to Magento',
            'magento_error_get_orders': ('Magento "%s". '
                'Error connection or get earlier date: "%s".'),
        })

    @classmethod
    def get_shop_app(cls):
        '''Get Shop APP (tryton, magento, prestashop,...)'''
        res = super(SaleShop, cls).get_shop_app()
        res.append(('magento', 'Magento'))
        return res

    @classmethod
    def get_magento_region(cls, region):
        '''Get subdivision (magento to tryton)'''
        pool = Pool()
        MagentoRegion = pool.get('magento.region')

        subdivision = None
        if not region:
            return subdivision

        regions = MagentoRegion.search([
                    ('region_id', '=', region),
                    ], limit=1)
        if regions:
            region, = regions
            subdivision = region.subdivision
        return subdivision

    def get_shop_user(self):
        '''
        Get user
        User is not active change user defined in sale shop
        :param shop: object
        :return user
        '''
        User = Pool().get('res.user')

        user = User(Transaction().user)
        if not user.active:
            if self.esale_user:
                user = self.esale_user
            else:
                logging.getLogger('magento order').info(
                    'Add a default user in %s configuration.' % (self.name))
        return user

    def import_orders_magento(self, ofilter=None):
        '''
        Import Orders from Magento APP
        :param shop: Obj
        :param ofilter: dict
        '''
        pool = Pool()
        SaleShop = pool.get('sale.shop')

        mgnapp = self.magento_website.magento_app
        now = datetime.datetime.now()

        if not ofilter:
            from_time = SaleShop.datetime_to_str(self.esale_from_orders or now)
            if self.esale_to_orders:
                to_time = SaleShop.datetime_to_str(self.esale_to_orders)
            else:
                to_time = SaleShop.datetime_to_str(now)

            created_filter = {}
            created_filter['from'] = from_time
            created_filter['to'] = to_time
            ofilter = {'created_at': created_filter}

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
        self.write([self], {'esale_from_orders': now, 'esale_to_orders': None})

        if not orders:
            logging.getLogger('magento sale').info(
                'Magento %s. Not orders to import.' % (self.name))
        else:
            logging.getLogger('magento order').info(
                'Magento %s. Start import %s orders.' % (
                self.name, len(orders)))

            user = self.get_shop_user()
            db_name = Transaction().cursor.dbname
            context = Transaction().context

            thread1 = threading.Thread(
                target=self.import_orders_magento_thread,
                args=(db_name, user.id, self.id, orders, context,))
            thread1.start()

    @classmethod
    def mgn2order_values(self, shop, values):
        '''
        Convert magento values to sale
        :param shop: obj
        :param values: dict
        return dict
        '''
        comments = []
        if values.get('customer_note'):
            comments.append(values.get('customer_note'))
        if values.get('onestepcheckout_customercomment'):
            comments.append(values.get('onestepcheckout_customercomment'))
        if values.get('gomage_checkout_customer_comment'):
            comments.append(values.get('gomage_checkout_customer_comment'))
        if values.get('gift_message'):
            comments.append(values.get('gift_message'))
        comment = '\n'.join(comments)

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
            'external_shipment_amount': Decimal(values.get('shipping_amount')),
            'shipping_price': Decimal(values.get('shipping_amount')),
            'shipping_note': values.get('shipping_description'),
            'discount': Decimal(values.get('discount_amount'))
            }

        # fooman surchage extension
        if values.get('fooman_surcharge_amount'):
            surcharge = None
            if values.get('base_fooman_surcharge_amount'):
                surcharge = values.get('base_fooman_surcharge_amount')
            elif values.get('fooman_surcharge_amount'):
                surcharge = values.get('fooman_surcharge_amount')
            surcharge = Decimal(surcharge)
            if surcharge != 0.0000:
                vals['surcharge'] = surcharge

        return vals

    @classmethod
    def mgn2lines_values(self, shop, values):
        '''
        Convert magento values to sale lines
        :param shop: obj
        :param values: dict
        return list(dict)
        '''
        Product = Pool().get('product.product')

        app = shop.magento_website.magento_app
        vals = []
        sequence = 1
        for item in values.get('items'):
            if item['product_type'] not in PRODUCT_TYPE_OUT_ORDER_LINE:
                code = item.get('sku')
                price = Decimal(item.get('price'))
                products = Product.search([('code', '=', code)], limit=1)
                product = products[0] if products else None

                # Price include taxes. Calculate base price - without taxes
                if shop.esale_tax_include:
                    if item.get('price_incl_tax'):
                        price = Decimal(item.get('price_incl_tax'))
                        customer_taxes = None
                        if product:
                            customer_taxes = product.template.customer_taxes_used
                        if not product and app.default_taxes:
                            customer_taxes = app.default_taxes
                        if customer_taxes:
                            rate = customer_taxes[0].rate
                            price = Decimal(base_price_without_tax(price, rate))
                    else:
                        price = Decimal('0.0')

                # Product Options (available feature with product simple)
                if app.product_options and item.get('sku'):
                    values = Product.magento_product_type_simple(app, item, price,
                        product, sequence)
                    for sku in item['sku'].split('-'):
                        values['product'] = sku
                        vals.append(values)
                else:
                    # Get Product Type Attribute to transform data
                    method_type = 'magento_product_type_%s' % item.get('product_type')
                    if hasattr(Product, method_type):
                        product_type = getattr(Product, method_type)
                    else:
                        product_type = getattr(Product, 'magento_product_type_simple')
                    values = product_type(app, item, price, product, sequence)
                    vals.append(values)
                sequence += 1
        return vals

    def mgn2extralines_values(self, shop, values):
        '''
        Convert magento values to extra sale lines
        Super this method if in your Magento there are extra lines to create
        in sale order
        :param shop: obj
        :param values: dict
        return list(dict)
        '''
        return []

    @classmethod
    def mgn2party_values(self, shop, values):
        '''
        Convert magento values to party
        :param shop: obj
        :param values: dict
        return dict
        '''
        pool = Pool()
        eSaleAccountTaxRule = pool.get('esale.account.tax.rule')

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

        # Add customer/supplier tax rule
        # 1. Search Tax Rule from Billing Address Region ID
        # 2. Search Tax Rule from Billing Address Post Code
        # 3. Search Tax Tule from Billing Address Country ID
        tax_rule = None
        taxe_rules = eSaleAccountTaxRule.search([])

        subdivision = self.get_magento_region(billing.get('region_id'))
        if subdivision:
            tax_rules = eSaleAccountTaxRule.search([
                ('subdivision', '=', subdivision),
                ], limit=1)
            if tax_rules:
                tax_rule, = tax_rules

        postcode = billing.get('postcode')
        if postcode and not tax_rule:
            for tax in taxe_rules:
                if not tax.start_zip or not tax.end_zip:
                    continue
                try:
                    if (int(tax.start_zip) <= int(postcode) <=
                            int(tax.end_zip)):
                        tax_rule = tax
                        break
                except:
                    break

        country = billing.get('country_id')
        if country and not tax_rule:
            for tax in taxe_rules:
                if tax.subdivision or tax.start_zip or tax.end_zip:
                    continue
                if tax.country.code.lower() == country.lower():
                    tax_rule = tax
                    break

        if tax_rule:
            vals['customer_tax_rule'] = tax_rule.customer_tax_rule.id
            vals['supplier_tax_rule'] = tax_rule.supplier_tax_rule.id
        # End add customer/supplier tax rule

        return vals

    @classmethod
    def mgn2invoice_values(self, shop, values):
        '''
        Convert magento values to invoice address
        :param shop: obj
        :param values: dict
        return dict
        '''
        billing = values.get('billing_address')

        name = party_name(values.get('customer_firstname'),
            values.get('customer_lastname'))
        if billing.get('firstname'):
            name = party_name(billing.get('firstname'),
                billing.get('lastname'))

        email = values.get('customer_email')
        if billing.get('email') and not billing.get('email') != 'n/a@na.na':
            email = values.get('customer_email')
        vals = {
            'name': unaccent(name).title(),
            'street': remove_newlines(unaccent(billing.get('street')).title()),
            'zip': billing.get('postcode'),
            'city': unaccent(billing.get('city')).title(),
            'subdivision': self.get_magento_region(billing.get('region_id')),
            'country': billing.get('country_id'),
            'phone': billing.get('telephone'),
            'email': email,
            'fax': billing.get('fax'),
            'invoice': True,
            }
        return vals

    @classmethod
    def mgn2shipment_values(self, shop, values):
        '''
        Convert magento values to shipment address
        :param shop: obj
        :param values: dict
        return dict
        '''
        shipment = values.get('shipping_address')

        name = party_name(values.get('customer_firstname'),
            values.get('customer_lastname'))
        if shipment.get('firstname'):
            name = party_name(shipment.get('firstname'),
                shipment.get('lastname'))

        email = values.get('customer_email')
        if shipment.get('email') and not shipment.get('email') != 'n/a@na.na':
            email = values.get('customer_email')
        vals = {
            'name': unaccent(name).title(),
            'street':
                remove_newlines(unaccent(shipment.get('street')).title()),
            'zip': shipment.get('postcode'),
            'city': unaccent(shipment.get('city')).title(),
            'subdivision': self.get_magento_region(shipment.get('region_id')),
            'country': shipment.get('country_id'),
            'phone': shipment.get('telephone'),
            'email': email,
            'fax': shipment.get('fax'),
            'delivery': True,
            }
        return vals

    def import_orders_magento_thread(self, db_name, user, shop, orders, context={}):
        '''
        Create orders from Magento APP
        :param db_name: str
        :param user: int
        :param shop: int
        :param orders: list
        :param context: dict
        '''
        with Transaction().start(db_name, user, context=context):
            pool = Pool()
            SaleShop = pool.get('sale.shop')
            Sale = pool.get('sale.sale')

            sale_shop = SaleShop(shop)
            mgnapp = sale_shop.magento_website.magento_app

            with Order(mgnapp.uri, mgnapp.username, mgnapp.password) \
                    as order_api:
                for order in orders:
                    reference = order['increment_id']

                    sales = Sale.search([
                        ('reference_external', '=', reference),
                        ('shop', '=', sale_shop),
                        ], limit=1)

                    if sales:
                        logging.getLogger('magento sale').warning(
                            'Magento %s. Order %s exist (ID %s). Not imported'
                            % (sale_shop.name, reference, sales[0].id))
                        continue

                    #Get details Magento order
                    values = order_api.info(reference)

                    #Convert Magento order to dict
                    sale_values = self.mgn2order_values(sale_shop, values)
                    lines_values = self.mgn2lines_values(sale_shop, values)
                    extralines_values = self.mgn2extralines_values(sale_shop,
                        values)
                    party_values = self.mgn2party_values(sale_shop, values)
                    invoice_values = self.mgn2invoice_values(sale_shop, values)
                    shipment_values = self.mgn2shipment_values(sale_shop,
                        values)

                    # Create order, lines, party and address
                    Sale.create_external_order(sale_shop, sale_values,
                        lines_values, extralines_values, party_values,
                        invoice_values, shipment_values)
                    Transaction().cursor.commit()

            logging.getLogger('magento sale').info(
                'Magento %s. End import sales' % (sale_shop.name))

    def export_state_magento(self):
        '''Export State sale to Magento'''
        now = datetime.datetime.now()
        date = self.esale_last_state_orders or now

        orders = self.get_sales_from_date(date)

        #~ Update date last import
        self.write([self], {'esale_last_state_orders': now})

        if not orders:
            logging.getLogger('magento sale').info(
                'Magento %s. Not orders to export state' % (self.name))
        else:
            sales = [s.id for s in orders]
            logging.getLogger('magento order').info(
                'Magento %s. Start export %s state orders' % (
                self.name, len(orders)))
            db_name = Transaction().cursor.dbname
            thread1 = threading.Thread(target=self.export_state_magento_thread,
                args=(db_name, Transaction().user, self.id, sales,))
            thread1.start()

    def export_state_magento_thread(self, db_name, user, shop, sales):
        '''
        Export State sale to Magento APP
        :param db_name: str
        :param user: int
        :param shop: int
        :param sales: list
        '''
        with Transaction().start(db_name, user):
            pool = Pool()
            Sale = pool.get('sale.sale')
            SaleShop = pool.get('sale.shop')

            sale_shop = SaleShop(shop)
            mgnapp = sale_shop.magento_website.magento_app

            states = {}
            for s in sale_shop.esale_states:
                states[s.state] = {'code': s.code, 'notify': s.notify}

            with Order(mgnapp.uri, mgnapp.username, mgnapp.password) \
                    as order_api:
                for sale in Sale.browse(sales):
                    status = None
                    notify = None
                    cancel = None
                    comment = None
                    if sale.state == 'cancel':
                        status = states['cancel']['code']
                        notify = states['cancel']['notify']
                        cancel = True
                    if sale.invoices_paid:
                        status = states['paid']['code']
                        notify = states['paid']['notify']
                    if sale.shipments_done:
                        status = states['shipment']['code']
                        notify = states['shipment']['notify']
                    if sale.invoices_paid and sale.shipments_done:
                        status = states['paid-shipment']['code']
                        notify = states['paid-shipment']['notify']

                    if not status or status == sale.status:
                        logging.getLogger('magento sale').info(
                            'Magento %s. Not status or not update state %s' % (
                            sale_shop.name, sale.reference_external))
                        continue

                    try:
                        order_api.addcomment(sale.reference_external, status,
                            comment, notify)
                        if cancel:
                            order_api.cancel(sale_shop.reference_external)

                        Sale.write([sale], {
                            'status': status,
                            'status_history': '%s\n%s - %s' % (
                                sale.status_history,
                                str(datetime.datetime.now()),
                                status),
                            })
                        logging.getLogger('magento sale').info(
                            'Magento %s. Export state %s - %s' % (
                            sale_shop.name, sale.reference_external, status))
                    except:
                        logging.getLogger('magento sale').error(
                            'Magento %s. Not export state %s' % (
                            sale_shop.name, sale.reference_external))
            Transaction().cursor.commit()
            logging.getLogger('magento sale').info(
                'Magento %s. End export state' % (sale_shop.name))

    def export_products_magento(self, tpls=[]):
        '''
        Export Products to Magento
        This option is available in magento_product module
        '''
        self.raise_user_error('magento_product')

    def export_prices_magento(self, shop):
        '''
        Export Prices to Magento
        This option is available in magento_product module
        '''
        self.raise_user_error('magento_product')

    def export_stocks_magento(self):
        '''
        Export Stocks to Magento
        This option is available in magento_product module
        '''
        self.raise_user_error('magento_product')

    def export_images_magento(self, shop):
        '''
        Export Images to Magento
        This option is available in magento_product module
        '''
        self.raise_user_error('magento_product')

    def export_menus_magento(self, shop, tpls=[]):
        '''
        Export Menus to Magento
        :param shop: object
        :param tpls: list
        '''
        self.raise_user_error('magento_product')
