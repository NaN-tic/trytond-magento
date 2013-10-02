#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from magento import Product as ProductMgn
from decimal import Decimal

import logging

__all__ = ['Product']
__metaclass__ = PoolMeta

def base_price_without_tax(price, percentage):
    '''
    Return base price - without tax
    :param price: total price
    :param percentatge: percentatge tax
    '''
    price = price/(1+percentage/100)
    return '%.4f' % (price)

class Product:
    "Product Variant"
    __name__ = "product.product"

    @classmethod
    def magento_template_dict2vals(self, shop, values):
        '''
        Convert Magento values to Template
        :param shop: obj
        :param values: dict from Magento Product API
        return dict
        '''
        vals = {
            'name': values.get('name'),
            'list_price': Decimal(values.get('price')),
            'cost_price': Decimal(values.get('price')),
            'esale_shortdescription': values.get('short_description'),
            }
        return vals

    @classmethod
    def magento_product_dict2vals(self, shop, values):
        '''
        Convert Magento values to Product
        :param shop: obj
        :param values: dict from Magento Product API
        return dict
        '''
        vals = {
            'code': values.get('sku'),
            }
        return vals

    @classmethod
    def create_product_magento(self, shop, code):
        '''
        Get Magento product info and create
        :param shop: obj
        :param code: str
        return obj
        '''
        Template = Pool().get('product.template')
        MagentoWebsite = Pool().get('magento.website')
        MagentoExternalReferential = Pool().get('magento.external.referential')

        mgnapp = shop.magento_website.magento_app

        store_view = mgnapp.magento_default_storeview or None
        if store_view:
            mgn_storeview = MagentoExternalReferential.get_try2mgn(mgnapp, 
            'magento.storeview', store_view.id)
            store_view = mgn_storeview.mgn_id

        if mgnapp.product_options:
            codes = code.split('-')
            if codes:
                logging.getLogger('magento sale').warning(
                    'Magento %s. Not split product %s' % (shop.name, code))

        with ProductMgn(mgnapp.uri, mgnapp.username, mgnapp.password) as product_api:
            try:
                product_info = product_api.info(code, store_view)
            except:
                logging.getLogger('magento sale').error(
                    'Magento %s. Not found product %s' % (shop.name, code))
                return None

            tvals = self.magento_template_dict2vals(shop, product_info)
            pvals = self.magento_product_dict2vals(shop, product_info)

            #Shops - websites
            shops = []
            websites = []
            for website in product_info.get('websites'):
                website_ref = MagentoExternalReferential.get_mgn2try(mgnapp, 
                'magento.website', website)
                websites.append(website_ref.try_id)
            if websites:
                magento_websites = MagentoWebsite.browse(websites)
                for website in magento_websites:
                    shops.append(website.sale_shop[0].id)
            if shops:
                tvals['esale_saleshops'] = [('add', shops)]

            #Taxes
            tax = None
            tax_id = product_info.get('tax_class_id')
            if tax_id:
                taxs = Pool().get('magento.tax').search([
                    ('magento_app', '=', mgnapp.id),
                    ('tax_id', '=', tax_id),
                    ], limit=1)
                if taxs:
                    tvals['customer_taxes'] = [('add', [taxs[0].tax.id])]
                if shop.esale_tax_include:
                    price = tvals.get('list_price')
                    percentage = taxs[0].tax.percentage #TODO review 2.9 rate percentage
                    base_price = base_price_without_tax(price, percentage)
                    tvals['list_price'] = base_price
                    tvals['cost_price'] = base_price
            elif mgnapp.default_taxes:
                taxs = []
                for tax in mgnapp.default_taxes:
                    taxs.append(tax.id)
                tvals['customer_taxes'] = [('add', taxs)]
                if shop.esale_tax_include:
                    # Get first tax to get base price -not all default taxes-
                    price = tvals.get('list_price')
                    percentage = mgnapp.default_taxes[0].percentage #TODO review 2.9 rate percentage
                    base_price = base_price_without_tax(price, percentage)
                    tvals['list_price'] = base_price
                    tvals['cost_price'] = base_price

            return Template.create_esale_product(shop, tvals, pvals)
