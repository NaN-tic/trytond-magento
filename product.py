#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from magento import Product as ProductMgn
from decimal import Decimal

import logging

__all__ = ['Product']
__metaclass__ = PoolMeta


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
            'description': values.get('short_description'),
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

        mgnapp = shop.magento_website.magento_app
        store_view = mgnapp.magento_default_storeview or None

        with ProductMgn(mgnapp.uri, mgnapp.username, mgnapp.password) as product_api:
            try:
                product_info = product_api.info(code, store_view)
            except:
                logging.getLogger('magento sale').error(
                    'Magento %s. Not found product %s.' % (shop.name, code))
                return None

            tvals = self.magento_template_dict2vals(shop, product_info)
            pvals = self.magento_product_dict2vals(shop, product_info)

            # Tax
            tax = None
            tax_id = product_info.get('tax_class_id')
            if tax_id:
                taxs = Pool().get('magento.tax').search([
                    ('magento_app', '=', mgnapp.id),
                    ('tax_id', '=', tax_id),
                    ], limit=1)
                if taxs:
                    tvals['customer_taxes'] = [('add', [taxs[0].tax.id])]

            #Default values
            tvals['default_uom'] = shop.esale_uom_product
            tvals['category'] = shop.esale_category
            tvals['salable'] = True
            tvals['sale_uom'] = shop.esale_uom_product
            tvals['account_category'] = True
            tvals['products'] = [('create', [pvals])]

            template = Template.create([tvals])[0]
            logging.getLogger('magento sale').info(
                'Magento %s. Create product %s.' % (shop.name, pvals['code']))
            return template.products[0]
