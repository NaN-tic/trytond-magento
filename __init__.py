# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.pool import Pool
from . import magento_core
from . import magento_referential
from . import product
from . import sale
from . import shop


def register():
    Pool.register(
        magento_core.MagentoApp,
        magento_core.MagentoWebsite,
        magento_core.MagentoStoreGroup,
        magento_core.MagentoStoreView,
        magento_core.MagentoCustomerGroup,
        magento_core.MagentoRegion,
        magento_core.MagentoAppCustomer,
        magento_core.MagentoShopStatus,
        magento_core.MagentoAppCustomerMagentoStoreview,
        magento_core.MagentoAppCountry,
        magento_core.MagentoAppLanguage,
        magento_core.MagentoApp2,
        magento_core.MagentoStoreGroup2,
        magento_core.MagentoTax,
        magento_core.MagentoAppDefaultTax,
        magento_referential.MagentoExternalReferential,
        product.Product,
        sale.Sale,
        sale.SaleLine,
        shop.SaleShop,
        module='magento', type_='model')
