# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from decimal import Decimal
from mock import patch
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.esale.tests.tools import sale_configuration
from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart
from . import tools


class MagentoTestCase(ModuleTestCase):
    'Test Magento module'
    module = 'magento'

    @with_transaction()
    def test_magento_app(self):
        pool = Pool()
        User = pool.get('res.user')
        APP = pool.get('magento.app')
        Country = pool.get('country.country')
        MagentoCustomerGroup = pool.get('magento.customer.group')
        MagentoRegion = pool.get('magento.region')
        MagentoWebsite = pool.get('magento.website')
        Shop = pool.get('sale.shop')
        Sale = pool.get('sale.sale')
        Uom = pool.get('product.uom')
        Category = pool.get('product.category')
        Template = pool.get('product.template')
        Product = pool.get('product.product')

        company = create_company()
        with set_company(company):
            create_chart(company)

            # update sale configuration
            sale_configuration()

            country = Country()
            country.name = 'Spain'
            country.code = 'ES'
            country.save()

            app = APP()
            app.name = 'Test Magento'
            app.uri = 'http://localhost'
            app.username = 'test'
            app.password = 'test'
            app.magento_countries = [country]
            app.save()

            # core store
            website = MagentoWebsite()
            website.name = 'Magento Test'
            website.code = 'test'
            website.magento_app = app
            website.save()
            # TODO store group + store view

            shop = app.get_sale_shop(name='Magento Test')
            shop.magento_website = website
            shop.save()
            self.assertEqual(shop.id, 1)

            # customer group
            with patch('magento.CustomerGroup', tools.mock_customer_group_api(), create=True):
                APP.core_customer_group([app])
            mgn_groups = MagentoCustomerGroup.search([])
            self.assertEqual(len(mgn_groups), 4)

            # regions
            with patch('magento.Region', tools.mock_region_api(), create=True):
                APP.core_regions([app])
            mgn_regions = MagentoRegion.search([])
            self.assertEqual(len(mgn_regions), 52)

            # set user shop
            user = User(Transaction().user)
            user.shops = [shop]
            user.shop = shop
            user.save()

            # create products
            category, = Category.search([('name', '=', 'Category')], limit=1)
            unit, = Uom.search([('name', '=', 'Unit')])

            pcodes = ['HTC Touch Diamond', 'micronmouse5000', 'VGN-TXN27N-B',
                'VGN-TXN27N-BW', '2yr_p_l']
            for pcode in pcodes:
                ts = Template()
                ts.name = pcode
                ts.type = 'goods'
                ts.salable = True

                ts.list_price = Decimal('0.0')
                ts.cost_price = Decimal('0.0')
                ts.default_uom = unit
                ts.sale_uom = unit
                ts.account_category = category
                ps = Product()
                ps.code = pcode
                ts.products = [ps]
                ts.save()

            shop = Shop(1)

            magento_data = tools.load_json('orders', '100000001')
            shop.create_mgn_order(magento_data)

            sale, = Sale.search([('number', '=', '100000001')])
            self.assertEqual(sale.number, '100000001')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        MagentoTestCase))
    return suite
