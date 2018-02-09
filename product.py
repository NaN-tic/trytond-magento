# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from decimal import Decimal
from trytond.modules.magento.tools import base_price_without_tax
import magento
import logging

__all__ = ['Product']

logger = logging.getLogger(__name__)


class Product:
    __metaclass__ = PoolMeta
    __name__ = "product.product"

    @classmethod
    def magento_product_domain(cls, shops):
        'Domain filter Products'
        return [
                ('esale_available', '=', True),
                ('shops', 'in', shops),
                ('code', '!=', None),
                ]

    @classmethod
    def magento_product_type_simple(self, app, item, price, product, sequence=1):
        '''Convert item data (magento lines) according product type'''
        values = {
            'product': item.get('sku'),
            'quantity': float(item.get('qty_ordered')),
            'description': item.get('description') or item.get('name'),
            'unit_price': price,
            'note': item.get('gift_message'),
            'sequence': sequence,
            }
        return values

    @classmethod
    def magento_import_product(self, values, shop=None):
        '''
        Convert Magento values to product (template + products)
        :param values: dict from Magento Product API
        :param shop: obj
        return dict
        '''
        vals = {}
        vals['name'] = values.get('name')
        vals['list_price'] = Decimal(values.get('price'))
        vals['cost_price'] = Decimal(values.get('price'))
        vals['products'] = [('create', [{'code': values.get('sku')}])]
        vals['esale_available'] = True
        vals['esale_active'] = True
        vals['salable'] = True
        vals['account_category'] = True
        vals['type'] = 'goods'
        return vals

    @classmethod
    def magento_product_shops(self, app, product_info):
        '''
        Get sale shops (websites)
        :param app: object
        :product_info: dict
        return shops (list)
        '''
        pool = Pool()
        MagentoWebsite = pool.get('magento.website')
        MagentoExternalReferential = pool.get('magento.external.referential')

        shops = []
        websites = []
        for website in product_info.get('websites'):
            website_ref = MagentoExternalReferential.get_mgn2try(app,
            'magento.website', website)
            websites.append(website_ref.try_id)
        if websites:
            magento_websites = MagentoWebsite.browse(websites)
            for website in magento_websites:
                shops.append(website.sale_shop[0].id)

        return shops

    @classmethod
    def magento_product_esale_taxes(self, app, product_info,
            tax_include=False):
        '''
        Get customer taxes and list price and cost price (with or without tax)
        :param app: object
        :product_info: dict
        return customer_taxes (list), list_price, cost_price
        '''
        pool = Pool()
        MagentoTax = pool.get('magento.tax')

        customer_taxes = []
        list_price = None
        cost_price = None

        tax_id = product_info.get('tax_class_id')
        if tax_id:
            taxs = MagentoTax.search([
                ('magento_app', '=', app.id),
                ('tax_id', '=', tax_id),
                ], limit=1)
            if taxs:
                customer_taxes.append(taxs[0].tax.id)
                if tax_include:
                    price = Decimal(product_info.get('price'))
                    rate = taxs[0].tax.rate
                    base_price = base_price_without_tax(price, rate)
                    list_price = base_price
                    cost_price = base_price

        if not customer_taxes and app.default_taxes:
            for tax in app.default_taxes:
                customer_taxes.append(tax.id)
            if tax_include:
                # Get first tax to get base price -not all default taxes-
                price = Decimal(product_info.get('price'))
                rate = app.default_taxes[0].rate
                base_price = base_price_without_tax(price, rate)
                list_price = base_price
                cost_price = base_price

        return customer_taxes, list_price, cost_price

    @classmethod
    def create_product_magento(self, shop, code):
        '''
        Get Magento product info and create
        :param shop: obj
        :param code: str
        return obj
        '''
        Template = Pool().get('product.template')
        MagentoExternalReferential = Pool().get('magento.external.referential')

        mgnapp = shop.magento_website.magento_app
        tax_include = shop.esale_tax_include

        store_view = mgnapp.magento_default_storeview or None
        if store_view:
            mgn_storeview = MagentoExternalReferential.get_try2mgn(mgnapp,
            'magento.storeview', store_view.id)
            store_view = mgn_storeview.mgn_id

        # TODO: Improve Product Options from Magento Orders
        #~ if mgnapp.product_options:
            #~ codes = code.split('-')

        with magento.Product(mgnapp.uri, mgnapp.username, mgnapp.password) \
                as product_api:
            try:
                product_info = product_api.info(code, store_view,
                        identifierType=mgnapp.identifier_type)
            except:
                logger.error(
                    'Magento %s. Not found product %s' % (shop.name, code))
                return

            vals = self.magento_import_product(product_info, shop)

            # Shops - websites
            shops = self.magento_product_shops(mgnapp, product_info)
            if shops:
                vals['shops'] = [('add', shops)]

            # Taxes and list price and cost price with or without taxes
            customer_taxes, list_price, cost_price = \
                self.magento_product_esale_taxes(mgnapp, product_info,
                    tax_include)
            if customer_taxes:
                vals['customer_taxes'] = [('add', customer_taxes)]
            if list_price:
                vals['list_price'] = list_price
            if cost_price:
                vals['cost_price'] = cost_price

            return Template.create_esale_product(shop, vals)
