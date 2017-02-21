# This file is part of the magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal
from mock import patch
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.modules.esale.tests.tools import sale_configuration
from . import tools


class MagentoTestCase(ModuleTestCase):
    'Test Magento module'
    module = 'magento'

    def test010magento_app(self):
        User = POOL.get('res.user')
        APP = POOL.get('magento.app')
        Country = POOL.get('country.country')
        MagentoCustomerGroup = POOL.get('magento.customer.group')
        MagentoRegion = POOL.get('magento.region')
        MagentoWebsite = POOL.get('magento.website')

        with Transaction().start(DB_NAME, USER, context=CONTEXT) as transaction:
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
            user = User(USER)
            user.shops = [shop]
            user.shop = shop
            user.save()

            transaction.cursor.commit()

    def test020import_orders(self):
        Shop = POOL.get('sale.shop')
        Sale = POOL.get('sale.sale')
        Uom = POOL.get('product.uom')
        Category = POOL.get('product.category')
        Template = POOL.get('product.template')
        Product = POOL.get('product.product')

        with Transaction().start(DB_NAME, USER, context=CONTEXT) as transaction:
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
                ts.category = category
                ts.list_price = Decimal('0.0')
                ts.cost_price = Decimal('0.0')
                ts.default_uom = unit
                ts.sale_uom = unit
                ts.account_category = True
                ts.taxes_category = True
                ps = Product()
                ps.code = pcode
                ts.products = [ps]
                ts.save()

            shop = Shop(1)

            magento_data = tools.load_json('orders', '100000001')
            shop.create_mgn_order(magento_data)

            sale, = Sale.search([('reference', '=', '100000001')])
            self.assertEqual(sale.reference, '100000001')

            transaction.cursor.commit()


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    from trytond.modules.account.tests import test_account
    for test in test_account.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        MagentoTestCase))
    return suite
