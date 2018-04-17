# encoding: utf-8
# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import grouped_slice
from trytond.config import config as config_
from trytond.pyson import Eval, Not, Equal
from trytond.modules.magento.tools import unaccent, party_name, \
    remove_newlines, base_price_without_tax
from trytond.modules.sale_discount.sale import DISCOUNT_DIGITS
from decimal import Decimal
import magento
import logging
import datetime

__all__ = ['SaleShop']

DIGITS = config_.getint('product', 'price_decimal', default=4)
PRECISION = Decimal(str(10.0 ** - DIGITS))
MAX_CONNECTIONS = config_.getint('magento', 'max_connections', default=50)
PRODUCT_TYPE_OUT_ORDER_LINE = ['configurable']
logger = logging.getLogger(__name__)


class SaleShop:
    __metaclass__ = PoolMeta
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
    def view_attributes(cls):
        return super(SaleShop, cls).view_attributes() + [
            ('/form/notebook/page[@id="esale"]/notebook/page[@id="magento"]', 'states', {
                    'invisible': Not(Equal(Eval('esale_shop_app'), 'magento')),
                    }),]

    @classmethod
    def get_shop_app(cls):
        '''Get Shop APP (tryton, magento, prestashop,...)'''
        res = super(SaleShop, cls).get_shop_app()
        res.append(('magento', 'Magento'))
        return res

    @classmethod
    def get_magento_region(cls, region, country=None):
        '''
        Get subdivision (mgn2tryton)
        :param region: magento ID or string
        :param country: country code (uppercase)
        return subdivision or None
        '''
        pool = Pool()
        MagentoRegion = pool.get('magento.region')
        Subdivision = pool.get('country.subdivision')

        if not region:
            return

        try:
            region_id = int(region)
        except:
            region_id = None

        if region_id:
            regions = MagentoRegion.search([
                        ('region_id', '=', region_id),
                        ], limit=1)
            if regions:
                region, = regions
                subdivision = region.subdivision
                return subdivision

        if country:
            subdivisions = Subdivision.search([
                        ('name', 'ilike', region),
                        ('country.code', '=', country),
                        ], limit=1)
            if subdivisions:
                subdivision, = subdivisions
                return subdivision
        return

    def mgn2order_values(self, values):
        '''
        Convert magento values to sale
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

        external_untaxed_amount = Decimal(values.get('base_subtotal'))
        if values.get('discount_amount'):
            discount_amount = abs(Decimal(values['discount_amount']))
            if self.esale_tax_include:
                customer_taxes = self.esale_discount_product.template.customer_taxes_used
                rate = customer_taxes[0].rate
                discount_amount = base_price_without_tax(
                    discount_amount, rate, self.currency)
            external_untaxed_amount -= discount_amount

        vals = {
            'number_external': values.get('increment_id'),
            'sale_date': values.get('created_at')[:10],
            'carrier': values.get('shipping_method'),
            'payment': payment_type,
            'currency': values.get('order_currency_code'),
            'comment': comment,
            'status': values['status_history'][0]['status'],
            'status_history': '\n'.join(status_history),
            'external_untaxed_amount': external_untaxed_amount,
            'external_tax_amount': Decimal(values.get('base_tax_amount')),
            'external_total_amount': Decimal(values.get('base_grand_total')),
            'external_shipment_amount': Decimal(values.get('shipping_amount')),
            'shipping_price': Decimal(values.get('shipping_amount')),
            'shipping_note': values.get('shipping_description'),
            'coupon_code': values.get('coupon_code'),
            'coupon_description': values.get('coupon_rule_name'),
            }

        # discount new line
        if self.esale_discount_new_line:
            vals['discount'] = Decimal(values.get('discount_amount'))
            vals['discount_description'] = values.get('discount_description')

        # fee line (Payment Service - Cash On Delivery)
        if values.get('base_cod_fee'):
            fee = values.get('base_cod_fee')
            fee = Decimal(fee)
            if fee != 0.0000:
                vals['fee'] = fee

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

    def mgn2lines_values(self, values, party_values):
        '''
        Convert magento values to sale lines
        :param values: dict
        return list(dict)
        '''
        pool = Pool()
        Product = pool.get('product.product')
        ProductCode = pool.get('product.code')
        AccountTax = pool.get('account.tax')
        SaleLine = pool.get('sale.line')

        app = self.magento_website.magento_app
        vals = []
        sequence = 1
        for item in values.get('items'):
            if item['product_type'] not in PRODUCT_TYPE_OUT_ORDER_LINE:
                code = item.get('sku')
                price = Decimal(item.get('price'))

                products = Product.search([
                    ('code', '=', code),
                    ], limit=1)
                if products:
                    product, = products
                else:
                    product_codes = ProductCode.search([
                        ('number', '=', code)
                        ], limit=1)
                    if product_codes:
                        product = product_codes[0].product
                    else:
                        product = None

                # Price include taxes. Calculate base price - without taxes
                if self.esale_tax_include:
                    if item.get('price_incl_tax'):
                        price = Decimal(item.get('price_incl_tax'))
                        customer_taxes = None
                        if product:
                            customer_taxes = product.template.customer_taxes_used
                        if not product and app.default_taxes:
                            customer_taxes = app.default_taxes
                        # apply customer tax rule
                        if customer_taxes and party_values.get('customer_tax_rule'):
                            pattern = {}
                            customer_tax_rule = party_values['customer_tax_rule']
                            tax_ids = customer_tax_rule.apply(customer_taxes[0], pattern)
                            if tax_ids:
                                customer_taxes = AccountTax.browse(tax_ids)
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
                else:
                    # Get Product Type Attribute to transform data
                    method_type = 'magento_product_type_%s' % item.get('product_type')
                    if hasattr(Product, method_type):
                        product_type = getattr(Product, method_type)
                    else:
                        product_type = getattr(Product, 'magento_product_type_simple')
                    values = product_type(app, item, price, product, sequence)
                    values['unit_price'] = price.quantize(PRECISION)

                if (not self.esale_discount_new_line
                        and hasattr(SaleLine, 'gross_unit_price')):
                    gross_unit_price = price
                    if (item.get('discount_percent')
                            and item.get('discount_percent') != '0.0000'):
                        discount_percent = Decimal(item['discount_percent']) / 100
                        values['discount_percent'] = discount_percent
                        price *= (1 - discount_percent)
                    elif ((item.get('discount_amount')
                            and item.get('discount_amount') != '0.0000') or
                            (item.get('base_discount_amount')
                            and item.get('base_discount_amount') != '0.0000')):
                        discount_amount = Decimal(item['discount_amount']
                            if self.esale_tax_include else item['base_discount_amount'])
                        price -= discount_amount
                        # calculate discount according price and gross unit price
                        discount_percent = (100 - (price * 100) / gross_unit_price) / 100
                        values['discount_percent'] = discount_percent.quantize(
                            Decimal(str(10.0 ** -DISCOUNT_DIGITS)))
                    values['gross_unit_price'] = gross_unit_price.quantize(PRECISION)
                    values['unit_price'] = price.quantize(PRECISION)

                vals.append(values)
                sequence += 1
        return vals

    def mgn2extralines_values(self, values):
        '''
        Convert magento values to extra sale lines
        Super this method if in your Magento there are extra lines to create
        in sale order
        :param values: dict
        return list(dict)
        '''
        return []

    def mgn2party_values(self, values):
        '''
        Convert magento values to party
        :param values: dict
        return dict
        '''
        pool = Pool()
        Country = pool.get('country.country')
        eSaleAccountTaxRule = pool.get('esale.account.tax.rule')

        firstname = values.get('customer_firstname')
        lastname = values.get('customer_lastname')

        billing = values.get('billing_address')
        shipping = values.get('shipping_address')

        if not firstname:
            if billing.get('company'):
                firstname = billing.get('company')
                lastname = None
            else:
                firstname = billing.get('firstname')
                lastname = billing.get('lastname')
        if not firstname and shipping:
            firstname = shipping.get('firstname')
            lastname = shipping.get('lastname')

        vals = {}
        vals['name'] = party_name(firstname, lastname).title()
        vals['esale_email'] = values.get('customer_email')
        vals['vat_code'] = values.get('customer_taxvat')
        if billing:
            vals['vat_country'] = billing.get('country_id')
            if not vals.get('vat_code') and billing.get('vat_id'):
                vals['vat_code'] = billing['vat_id']
        else:
            vals['vat_country'] = shipping.get('country_id')
            if not vals.get('vat_code') and shipping.get('vat_id'):
                vals['vat_code'] = shipping['vat_id']

        # Add customer/supplier tax rule
        country_id = billing.get('country_id')
        if country_id:
            countries = Country.search(['OR',
                ('name', 'like', country_id),
                ('code', '=', country_id.upper()),
                ], limit=1)
            if countries:
                country, = countries
                subdivision = self.get_magento_region(
                    billing.get('region_id'),
                    billing.get('country_id'))
                zip = billing.get('postcode')
                tax_rule = eSaleAccountTaxRule.compute(country, subdivision, zip)
                if tax_rule:
                    vals['customer_tax_rule'] = tax_rule.customer_tax_rule
                    vals['supplier_tax_rule'] = tax_rule.supplier_tax_rule
        # End add customer/supplier tax rule

        return vals

    def mgn2invoice_values(self, values):
        '''
        Convert magento values to invoice address
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
            'zip': unaccent(billing.get('postcode')),
            'city': unaccent(billing.get('city')).title(),
            'subdivision': self.get_magento_region(
                billing.get('region_id'),
                billing.get('country_id')),
            'country': billing.get('country_id'),
            'phone': unaccent(billing.get('telephone')),
            'email': unaccent(email),
            'fax': unaccent(billing.get('fax')),
            'invoice': True,
            }
        return vals

    def mgn2shipment_values(self, values):
        '''
        Convert magento values to shipment address
        :param values: dict
        return dict
        '''
        shipment = values.get('shipping_address')
        if not shipment:
            shipment = values.get('billing_address')

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
            'subdivision': self.get_magento_region(
                shipment.get('region_id'),
                shipment.get('country_id')),
            'country': shipment.get('country_id'),
            'phone': unaccent(shipment.get('telephone')),
            'email': unaccent(email),
            'fax': unaccent(shipment.get('fax')),
            'delivery': True,
            }
        return vals

    def import_orders_magento(self, ofilter=None):
        '''
        Import Orders from Magento APP
        :param ofilter: dict
        '''
        pool = Pool()
        Sale = pool.get('sale.sale')
        User = pool.get('res.user')
        MagentoExternalReferential = pool.get('magento.external.referential')

        mgnapp = self.magento_website.magento_app
        now = datetime.datetime.now()

        if not ofilter:
            start_date = self.esale_from_orders or now
            end_date = self.esale_to_orders or now

            if self.esale_import_delayed:
                start_date = start_date - datetime.timedelta(
                        minutes=self.esale_import_delayed)
                end_date = end_date - datetime.timedelta(
                        minutes=self.esale_import_delayed)

            from_time = self.datetime_to_str(start_date)
            to_time = self.datetime_to_str(end_date)

            created_filter = {}
            created_filter['from'] = from_time
            created_filter['to'] = to_time
            ofilter = {'created_at': created_filter}

            # filter orders by store views. Get all views from a website related a shop
            store_views = []
            for sgroups in self.magento_website.magento_storegroups:
                for sview in sgroups.magento_storeviews:
                    mgn_storeview = MagentoExternalReferential.get_try2mgn(mgnapp,
                        'magento.storeview', sview.id)
                    if mgn_storeview:
                        store_views.append(mgn_storeview.mgn_id)
            if store_views:
                ofilter['store_id'] = {'in': store_views}
            if self.esale_import_states:
                ofilter['state'] = {'in': self.esale_import_states.split(',')}

        with magento.Order(mgnapp.uri, mgnapp.username, mgnapp.password) as order_api:
            try:
                order_ids = [o['increment_id'] for o in order_api.list(ofilter)]
                logger.info(
                    'Magento %s. Import orders %s.' % (mgnapp.name, ofilter))
            except:
                logger.error(
                    'Magento %s. Error connection or get earlier date: %s.' % (
                    mgnapp.name, ofilter))
                self.raise_user_error('magento_error_get_orders', (
                    mgnapp.name, ofilter))

        # Update date last import
        self.write([self], {'esale_from_orders': now, 'esale_to_orders': None})
        Transaction().commit()

        if order_ids:
            sales = Sale.search([
                ('number_external', 'in', order_ids),
                ('shop', '=', self.id),
                ])
            if sales:
                # not import sales was imported
                sales_imported_ids = [s.number_external for s in sales]
                order_ids = list(set(order_ids)-set(sales_imported_ids))
                if sales_imported_ids:
                    logger.warning(
                        'Magento %s. Skip sales was imported %s'
                        % (self.name, ', '.join(sales_imported_ids)))

        if not order_ids:
            logger.info('Magento %s. Not sales to import.' % (self.name))
            return

        logger.info(
            'Magento %s. Start import %s sales.' % (self.name, len(order_ids)))

        mgnapp = self.magento_website.magento_app

        context = Transaction().context
        if not context.get('shop'): # reload context when run cron user
            user = self.get_shop_user()
            if not user:
                return
            context = User._get_preferences(user, context_only=True)
        context['shop'] = self.id # force current shop
        context['explode_kit'] = self.esale_explode_kit or False # explode sale lines
        context['esale'] = True

        with Transaction().set_context(context):
            for grouped_order_ids in grouped_slice(order_ids, MAX_CONNECTIONS):
                with magento.Order(mgnapp.uri, mgnapp.username, mgnapp.password) \
                        as order_api:
                    for order in order_api.info_multi(grouped_order_ids):
                        self.create_mgn_order(order)
                        Transaction().commit()

        logger.info(
            'Magento %s. End import %s sales' % (self.name, len(order_ids)))

    def create_mgn_order(self, magento_data):
        Sale = Pool().get('sale.sale')

        # Convert Magento order to dict
        sale_values = self.mgn2order_values(magento_data)
        lines_values = self.mgn2lines_values(magento_data, party_values)
        extralines_values = self.mgn2extralines_values(magento_data)
        party_values = self.mgn2party_values(magento_data)
        invoice_values = self.mgn2invoice_values(magento_data)
        shipment_values = self.mgn2shipment_values(magento_data)

        # Create order, lines, party and address
        Sale.create_external_order(self, sale_values,
            lines_values, extralines_values, party_values,
            invoice_values, shipment_values)

    def export_state_magento(self):
        '''Export State sale to Magento'''
        pool = Pool()
        Sale = pool.get('sale.sale')

        now = datetime.datetime.now()
        date = self.esale_last_state_orders or now

        sales = self.get_sales_from_date(date)

        #~ Update date last import
        self.write([self], {'esale_last_state_orders': now})
        Transaction().commit()

        if not sales:
            logger.info('Magento %s. Not sales to export state' % (self.name))
            return

        logger.info('Magento %s. Start export %s state orders' % (
            self.name, len(sales)))

        mgnapp = self.magento_website.magento_app

        if not self.esale_states:
            logger.error('%s: Configure esale states before export status' % (
                self.name))
            return

        with magento.Order(mgnapp.uri, mgnapp.username, mgnapp.password) \
                as order_api:
            for sale in sales:
                number_external = sale.number_external
                status, notify, cancel = sale.convert_magento_status()
                comment = None

                if not status or status == sale.status:
                    logger.info(
                        'Magento %s. Not status or not update state %s' % (
                        self.name, number_external))
                    continue

                try:
                    if cancel:
                        order_api.cancel(number_external)
                    else:
                        order_api.addcomment(number_external, status,
                            comment, notify)

                    Sale.write([sale], {
                        'status': status,
                        'status_history': '%s\n%s - %s' % (
                            sale.status_history,
                            str(datetime.datetime.now()),
                            status),
                        })
                    Transaction().commit()
                    logger.info(
                        'Magento %s. Export state %s - %s' % (
                        self.name, number_external, status))
                except:
                    logger.error(
                        'Magento %s. Not export state %s' % (
                        self.name, sale.number_external))

        logger.info('Magento %s. End export state' % (self.name))

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
